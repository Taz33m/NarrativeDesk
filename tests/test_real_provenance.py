import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from narrativedesk.real_data import build_real_source_pack, validate_real_case_config
from narrativedesk.real_provenance import (
    RealProvenanceError,
    _normalize_text,
    _sec_filing_excerpt,
    apply_curated_narratives,
    draft_real_case,
    fetch_real_data,
    inspect_market_bars,
    normalize_real_data_fetch,
    rehearse_real_case,
    write_curated_narratives_template,
)
from narrativedesk.source_pack import validate_source_pack

ROOT = Path(__file__).resolve().parents[1]


def _load_aapl_rehearsal_runner():
    spec = importlib.util.spec_from_file_location(
        "run_aapl_rehearsal",
        ROOT / "scripts" / "run_aapl_rehearsal.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class FakeProvenanceFetcher:
    def __init__(self, *, fail_candles: bool = False):
        self.calls = []
        self.fail_candles = fail_candles

    def get_json(self, url, *, params=None, headers=None):
        self.calls.append({"url": url, "params": params or {}, "headers": headers or {}})
        if url.endswith("/stock/candle"):
            if self.fail_candles:
                raise RuntimeError("provider rejected token=secret-token")
            return {
                "s": "ok",
                "t": [
                    _epoch("2025-01-01T00:00:00+00:00"),
                    _epoch("2025-01-02T00:00:00+00:00"),
                ],
                "o": [100.0, 100.0],
                "c": [101.0, 94.0],
                "v": [1000, 2000],
            }
        if url.endswith("/company-news"):
            return [
                {
                    "id": 1,
                    "datetime": _epoch("2025-01-02T14:00:00+00:00"),
                    "headline": "Example shares fall after guidance update",
                    "summary": "Management commentary focused on slower future expansion.",
                    "source": "Example Wire",
                    "url": "https://news.example.com/example-guidance",
                },
                {
                    "id": 2,
                    "datetime": _epoch("2025-01-07T13:00:00+00:00"),
                    "headline": "Analysts cut estimates after replay window",
                    "summary": "Later commentary is validation-only evidence.",
                    "source": "Example Wire",
                    "url": "https://news.example.com/example-estimate-cut",
                },
                {
                    "id": 3,
                    "datetime": _epoch("2025-01-02T14:10:00+00:00"),
                    "headline": "Unusable article without stable URL",
                    "summary": "This should be rejected.",
                    "source": "Example Wire",
                },
            ]
        if url == "https://www.sec.gov/files/company_tickers.json":
            return {"0": {"ticker": "EXMPL", "cik_str": 1234567, "title": "Example Co"}}
        if url == "https://data.sec.gov/submissions/CIK0001234567.json":
            return {
                "name": "Example Co",
                "filings": {
                    "recent": {
                        "form": ["8-K", "10-Q"],
                        "accessionNumber": ["0001234567-25-000001", "0001234567-24-000099"],
                        "primaryDocument": ["exmpl-20250102.htm", "exmpl-20240930.htm"],
                        "filingDate": ["2025-01-02", "2024-10-31"],
                        "acceptanceDateTime": ["2025-01-02T13:10:00.000Z", "2024-10-31T20:30:00.000Z"],
                    }
                },
            }
        if url == "https://data.sec.gov/api/xbrl/companyfacts/CIK0001234567.json":
            return {"entityName": "Example Co", "facts": {}}
        if url == "https://newsapi.org/v2/everything":
            return {
                "status": "ok",
                "totalResults": 1,
                "articles": [
                    {
                        "source": {"id": None, "name": "Market Desk"},
                        "author": "Reporter",
                        "title": "Example shares react to guidance",
                        "description": "Investors focused on next-quarter demand indicators.",
                        "url": "https://market.example.com/example-guidance",
                        "publishedAt": "2025-01-02T14:20:00Z",
                        "content": "Truncated discovery snippet [+100 chars]",
                    }
                ],
            }
        raise AssertionError(f"Unexpected URL: {url}")

    def get_text(self, url, *, params=None, headers=None):
        self.calls.append({"url": url, "params": params or {}, "headers": headers or {}})
        if url == "https://www.sec.gov/Archives/edgar/data/1234567/000123456725000001/exmpl-20250102.htm":
            return """
            <html><body>
              <p>Management lowered full-year net addition guidance and described slower expansion.</p>
            </body></html>
            """
        raise AssertionError(f"Unexpected text URL: {url}")


def _epoch(value):
    return int(datetime.fromisoformat(value).timestamp())


class RealProvenanceTests(unittest.TestCase):
    def test_normalize_text_drops_inline_xbrl_hidden_blocks(self):
        raw = """
        <html><body>
          <ix:header>
            <ix:hidden><ix:nonNumeric>hidden xbrl noise</ix:nonNumeric></ix:hidden>
            <ix:resources><xbrli:context>context noise</xbrli:context></ix:resources>
          </ix:header>
          <p>Apple reported second quarter results.</p>
        </body></html>
        """

        text = _normalize_text(raw)

        self.assertIn("Apple reported second quarter results.", text)
        self.assertNotIn("hidden xbrl noise", text)
        self.assertNotIn("context noise", text)

    def test_normalize_text_unescapes_html_entities(self):
        text = _normalize_text("<p>Apple&#39;s services&nbsp;revenue</p>")

        self.assertEqual(text, "Apple's services revenue")

    def test_sec_filing_excerpt_focuses_on_financial_or_event_sections(self):
        raw = """
        <html><body>
          <p>UNITED STATES SECURITIES AND EXCHANGE COMMISSION cover page boilerplate.</p>
          <p>Registrant address and phone number.</p>
          <p>Item 2.02 Results of Operations and Financial Condition.</p>
          <p>Net sales were discussed in the earnings release exhibit.</p>
        </body></html>
        """

        excerpt = _sec_filing_excerpt(raw, fallback="Apple filed an 8-K.")

        self.assertIn("Item 2.02", excerpt)
        self.assertIn("Net sales", excerpt)
        self.assertNotIn("UNITED STATES SECURITIES AND EXCHANGE COMMISSION", excerpt)

    def test_sec_filing_excerpt_prefers_actual_results_section_over_table_of_contents(self):
        raw = """
        <html><body>
          <p>Results of Operations 13 Item 3. Quantitative and Qualitative Disclosures About Market Risk 18</p>
          <p>More table of contents rows.</p>
          <p>Results of Operations This Item contains management discussion and analysis.</p>
          <p>Segment Operating Performance net sales were discussed here.</p>
        </body></html>
        """

        excerpt = _sec_filing_excerpt(raw, fallback="Apple filed a 10-Q.")

        self.assertTrue(excerpt.startswith("Segment Operating Performance"))
        self.assertIn("Segment Operating Performance", excerpt)
        self.assertNotIn("Quantitative and Qualitative Disclosures", excerpt)

    def test_fetch_real_data_writes_manifest_and_redacts_secrets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "fetch"
            fetcher = FakeProvenanceFetcher()

            manifest = fetch_real_data(
                ticker="EXMPL",
                company_name="Example Co",
                date_from="2025-01-01",
                date_to="2025-01-07",
                providers=["finnhub", "sec"],
                out_dir=out_dir,
                finnhub_token="secret-token",
                sec_user_agent="NarrativeDesk Tests test@example.com",
                fetcher=fetcher,
                retrieved_at=datetime(2026, 5, 11, tzinfo=timezone.utc),
                forms=["8-K"],
                sec_count=1,
                include_sec_document_text=True,
                sec_throttle_seconds=0,
            )

            manifest_path = out_dir / "fetch_manifest.json"
            saved_manifest = json.loads(manifest_path.read_text())
            manifest_text = manifest_path.read_text()

        self.assertTrue(manifest["ok"])
        self.assertEqual(saved_manifest["artifacts"][0]["params"]["token"], "[REDACTED]")
        self.assertNotIn("secret-token", manifest_text)
        self.assertTrue(any(artifact["endpoint"] == "filing_document" for artifact in saved_manifest["artifacts"]))
        sec_call = next(call for call in fetcher.calls if call["url"].startswith("https://data.sec.gov"))
        self.assertEqual(sec_call["headers"]["User-Agent"], "NarrativeDesk Tests test@example.com")

    def test_normalize_real_data_fetch_builds_candidates_and_rejections(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "fetch"
            fetch_real_data(
                ticker="EXMPL",
                company_name="Example Co",
                date_from="2025-01-01",
                date_to="2025-01-07",
                providers=["finnhub", "sec", "newsapi"],
                out_dir=out_dir,
                finnhub_token="secret-token",
                sec_user_agent="NarrativeDesk Tests test@example.com",
                news_api_key="news-secret",
                fetcher=FakeProvenanceFetcher(),
                retrieved_at="2026-05-11T00:00:00Z",
                forms=["8-K"],
                sec_count=1,
                include_sec_document_text=True,
                sec_throttle_seconds=0,
            )

            summary = normalize_real_data_fetch(
                out_dir,
                replay_lock="2025-01-02T10:00:00-05:00",
                generated_at="2026-05-11T00:00:00Z",
            )
            candidates = json.loads((out_dir / "normalized" / "source_candidates.json").read_text())["candidates"]
            rejected = json.loads((out_dir / "normalized" / "rejected_candidates.json").read_text())[
                "rejected_candidates"
            ]
            market_bars = (out_dir / "normalized" / "market_bars.csv").read_text()

        self.assertEqual(summary["eligible_candidates"], 3)
        self.assertEqual(summary["blocked_future_candidates"], 1)
        self.assertEqual(summary["rejected_candidates"], 1)
        self.assertIn("2025-01-01,EXMPL,100.0,101.0,1000", market_bars)
        self.assertNotIn("2025-01-02,EXMPL,100.0,94.0,2000", market_bars)
        self.assertTrue(any(item["provider"] == "newsapi" for item in candidates))
        self.assertTrue(any(item["source_type"] == "filing" for item in candidates))
        self.assertTrue(any(item["replay_status"] == "blocked_future" for item in candidates))
        self.assertIn("url", rejected[0]["rejection_reason"])

    def test_draft_real_case_emits_curator_ready_config_and_quality_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fetch_dir = root / "fetch"
            fetch_real_data(
                ticker="EXMPL",
                company_name="Example Co",
                date_from="2025-01-01",
                date_to="2025-01-07",
                providers=["finnhub", "sec"],
                out_dir=fetch_dir,
                finnhub_token="secret-token",
                sec_user_agent="NarrativeDesk Tests test@example.com",
                fetcher=FakeProvenanceFetcher(),
                retrieved_at="2026-05-11T00:00:00Z",
                forms=["8-K"],
                sec_count=1,
                include_sec_document_text=True,
                sec_throttle_seconds=0,
            )
            normalize_real_data_fetch(
                fetch_dir,
                replay_lock="2025-01-02T10:00:00-05:00",
                generated_at="2026-05-11T00:00:00Z",
            )

            draft_dir = root / "draft"
            response = draft_real_case(
                ticker="EXMPL",
                company_name="Example Co",
                event_type="earnings/guidance",
                event_date="2025-01-02",
                replay_lock="2025-01-02T10:00:00-05:00",
                normalized_dir=fetch_dir / "normalized",
                out_dir=draft_dir,
            )
            config = json.loads((draft_dir / "real_case_config.json").read_text())
            summary = json.loads((draft_dir / "draft_summary.json").read_text())
            errors = validate_real_case_config(config, base_path=draft_dir, check_files=True)
            source_pack = build_real_source_pack(
                config,
                base_path=draft_dir,
                retrieved_at="2026-05-11T00:00:00Z",
            )

        self.assertTrue(response["ok"])
        self.assertEqual(errors, [])
        self.assertEqual(validate_source_pack(source_pack), [])
        self.assertEqual(summary["case_readiness"], "curator_ready")
        self.assertEqual(summary["accepted_sources"], 2)
        self.assertEqual(summary["blocked_future_sources"], 1)
        self.assertEqual(summary["rejected_sources"], 1)
        self.assertTrue(summary["market_bars_check"]["ok"])
        self.assertEqual(summary["market_bars_check"]["selected_row"]["ticker"], "EXMPL")
        self.assertEqual(config["narratives"], [])
        self.assertTrue(any(source["availability_status"] == "blocked_future" for source in config["manual_sources"]))
        self.assertEqual(config["market_data"]["provider"], "local_csv")

    def test_draft_real_case_omits_empty_market_data_from_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            normalized = root / "normalized"
            normalized.mkdir()
            (normalized / "market_bars.csv").write_text("date,ticker,open,close,volume\n")
            (normalized / "source_candidates.json").write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "source_id": "SEC-001",
                                "provider": "sec",
                                "publisher": "SEC EDGAR",
                                "title": "Example Co 8-K filed 2025-01-02",
                                "url": "https://www.sec.gov/example",
                                "published_at": "2025-01-02T13:00:00Z",
                                "retrieved_at": "2026-05-11T00:00:00Z",
                                "source_type": "filing",
                                "excerpt": "Example Co filed an 8-K.",
                                "raw_artifact_path": "raw/sec/submissions.json",
                                "content_hash": "sha256:14cdba325e2bc0b7cbb92a74aba5a268f8734599d27646cc556d0fe58182f5cd",
                                "replay_status": "eligible",
                                "rejection_reason": None,
                            }
                        ]
                    }
                )
            )
            (normalized / "rejected_candidates.json").write_text(
                json.dumps({"rejected_candidates": []})
            )

            draft_dir = root / "draft"
            response = draft_real_case(
                ticker="EXMPL",
                company_name="Example Co",
                event_type="earnings/guidance",
                event_date="2025-01-02",
                replay_lock="2025-01-02T10:00:00-05:00",
                normalized_dir=normalized,
                out_dir=draft_dir,
            )
            config = json.loads((draft_dir / "real_case_config.json").read_text())

        self.assertTrue(response["ok"])
        self.assertEqual(response["case_readiness"], "needs_sources")
        self.assertFalse(response["market_bars_available"])
        self.assertFalse(response["market_bars_check"]["ok"])
        self.assertTrue(any("No rows found for ticker EXMPL" in error for error in response["market_bars_check"]["errors"]))
        self.assertIn("No rows found for ticker EXMPL", response["recommended_next_action"])
        self.assertNotIn("market_data", config)

    def test_draft_real_case_accepts_explicit_frozen_market_bars(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            normalized = root / "normalized"
            normalized.mkdir()
            (normalized / "market_bars.csv").write_text("date,ticker,open,close,volume\n")
            (normalized / "source_candidates.json").write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "source_id": "SEC-001",
                                "provider": "sec",
                                "publisher": "SEC EDGAR",
                                "title": "Example Co 8-K filed 2025-01-02",
                                "url": "https://www.sec.gov/example",
                                "published_at": "2025-01-02T13:00:00Z",
                                "retrieved_at": "2026-05-11T00:00:00Z",
                                "source_type": "filing",
                                "excerpt": "Example Co filed an 8-K.",
                                "raw_artifact_path": "raw/sec/submissions.json",
                                "content_hash": "sha256:14cdba325e2bc0b7cbb92a74aba5a268f8734599d27646cc556d0fe58182f5cd",
                                "replay_status": "eligible",
                                "rejection_reason": None,
                            }
                        ]
                    }
                )
            )
            (normalized / "rejected_candidates.json").write_text(json.dumps({"rejected_candidates": []}))
            market_bars = root / "curated_market_bars.csv"
            market_bars.write_text(
                "\n".join(
                    [
                        "date,ticker,open,close,volume",
                        "2025-01-02T10:00:00-05:00,EXMPL,100.0,94.0,2000",
                    ]
                )
                + "\n"
            )

            draft_dir = root / "draft"
            response = draft_real_case(
                ticker="EXMPL",
                company_name="Example Co",
                event_type="earnings/guidance",
                event_date="2025-01-02",
                replay_lock="2025-01-02T10:00:00-05:00",
                normalized_dir=normalized,
                out_dir=draft_dir,
                market_bars_path=market_bars,
            )
            config = json.loads((draft_dir / "real_case_config.json").read_text())
            copied_bars = (draft_dir / "market_bars.csv").read_text()

        self.assertTrue(response["ok"])
        self.assertEqual(response["case_readiness"], "curator_ready")
        self.assertTrue(response["market_bars_available"])
        self.assertEqual(response["missing_requirements"], [])
        self.assertEqual(config["market_data"]["path"], "market_bars.csv")
        self.assertIn("2025-01-02T10:00:00-05:00,EXMPL,100.0,94.0,2000", copied_bars)

    def test_draft_real_case_rejects_future_market_bar_override_for_readiness(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            normalized = root / "normalized"
            normalized.mkdir()
            (normalized / "market_bars.csv").write_text("date,ticker,open,close,volume\n")
            (normalized / "source_candidates.json").write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "source_id": "SEC-001",
                                "provider": "sec",
                                "publisher": "SEC EDGAR",
                                "title": "Example Co 8-K filed 2025-01-02",
                                "url": "https://www.sec.gov/example",
                                "published_at": "2025-01-02T13:00:00Z",
                                "retrieved_at": "2026-05-11T00:00:00Z",
                                "source_type": "filing",
                                "excerpt": "Example Co filed an 8-K.",
                                "raw_artifact_path": "raw/sec/submissions.json",
                                "content_hash": "sha256:14cdba325e2bc0b7cbb92a74aba5a268f8734599d27646cc556d0fe58182f5cd",
                                "replay_status": "eligible",
                                "rejection_reason": None,
                            }
                        ]
                    }
                )
            )
            (normalized / "rejected_candidates.json").write_text(json.dumps({"rejected_candidates": []}))
            market_bars = root / "future_market_bars.csv"
            market_bars.write_text(
                "\n".join(
                    [
                        "date,ticker,open,close,volume",
                        "2025-01-03T10:00:00-05:00,EXMPL,100.0,94.0,2000",
                    ]
                )
                + "\n"
            )

            draft_dir = root / "draft"
            response = draft_real_case(
                ticker="EXMPL",
                company_name="Example Co",
                event_type="earnings/guidance",
                event_date="2025-01-02",
                replay_lock="2025-01-02T10:00:00-05:00",
                normalized_dir=normalized,
                out_dir=draft_dir,
                market_bars_path=market_bars,
            )
            config = json.loads((draft_dir / "real_case_config.json").read_text())

        self.assertEqual(response["case_readiness"], "needs_sources")
        self.assertFalse(response["market_bars_available"])
        self.assertEqual(response["market_bars_check"]["after_lock_row_count"], 1)
        self.assertTrue(
            any("No replay-eligible rows found" in error for error in response["market_bars_check"]["errors"])
        )
        self.assertIn("No replay-eligible rows found", response["recommended_next_action"])
        self.assertNotIn("market_data", config)

    def test_cli_real_case_status_uses_market_bar_diagnostics_for_stale_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            draft_dir = Path(tmpdir) / "draft"
            draft_dir.mkdir()
            (draft_dir / "real_case_config.json").write_text(
                json.dumps(
                    {
                        "case_metadata": {"case_id": "EVT-EXMPL", "ticker": "EXMPL"},
                        "manual_sources": [{"availability_status": "allowed"}],
                    }
                )
            )
            (draft_dir / "draft_summary.json").write_text(
                json.dumps(
                    {
                        "case_readiness": "needs_sources",
                        "accepted_sources": 1,
                        "blocked_future_sources": 0,
                        "rejected_sources": 0,
                        "market_bars_available": False,
                        "market_bars_check": {
                            "ok": False,
                            "errors": ["No replay-eligible rows found for EXMPL at or before the replay lock."],
                        },
                        "missing_requirements": [
                            "Frozen market_bars.csv with at least one replay-eligible ticker row"
                        ],
                        "recommended_next_action": (
                            "Fetch or curate additional timestamped sources before narrative curation."
                        ),
                    }
                )
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "narrativedesk.cli",
                    "real-case-status",
                    "--draft-dir",
                    str(draft_dir),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
            response = json.loads(result.stdout)

        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertEqual(response["status"], "needs_sources")
        self.assertIn("Provide replay-eligible market bars", response["next_action"])
        self.assertIn("No replay-eligible rows found", response["next_action"])

    def test_inspect_market_bars_rejects_same_day_daily_row_before_close(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            market_bars = Path(tmpdir) / "market_bars.csv"
            market_bars.write_text(
                "\n".join(
                    [
                        "date,ticker,open,close,volume",
                        "2025-01-01,EXMPL,100.0,101.0,1000",
                        "2025-01-02,EXMPL,101.0,94.0,2000",
                    ]
                )
                + "\n"
            )

            response = inspect_market_bars(
                market_bars,
                ticker="EXMPL",
                replay_lock="2025-01-02T10:00:00-05:00",
            )

        self.assertTrue(response["ok"])
        self.assertEqual(response["row_count"], 2)
        self.assertEqual(response["ticker_row_count"], 2)
        self.assertEqual(response["eligible_row_count"], 1)
        self.assertEqual(response["after_lock_row_count"], 1)
        self.assertEqual(response["selected_row"]["date"], "2025-01-01")

    def test_cli_real_market_bars_check_reports_missing_ticker(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            market_bars = Path(tmpdir) / "market_bars.csv"
            market_bars.write_text(
                "\n".join(
                    [
                        "date,ticker,open,close,volume",
                        "2025-01-01,XLK,100.0,101.0,1000",
                    ]
                )
                + "\n"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "narrativedesk.cli",
                    "real-market-bars-check",
                    str(market_bars),
                    "--ticker",
                    "AAPL",
                    "--replay-lock",
                    "2025-01-02T10:00:00-05:00",
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
            response = json.loads(result.stdout)

        self.assertEqual(result.returncode, 1)
        self.assertFalse(response["ok"])
        self.assertEqual(response["available_tickers"], ["XLK"])
        self.assertTrue(any("No rows found for ticker AAPL" in error for error in response["errors"]))

    def test_rehearse_real_case_runs_fetch_normalize_draft_and_worksheet(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            response = rehearse_real_case(
                ticker="EXMPL",
                company_name="Example Co",
                event_type="earnings/guidance",
                event_date="2025-01-02",
                replay_lock="2025-01-02T10:00:00-05:00",
                date_from="2025-01-01",
                date_to="2025-01-07",
                out_root=root,
                providers=["finnhub", "sec"],
                finnhub_token="secret-token",
                sec_user_agent="NarrativeDesk Tests test@example.com",
                fetcher=FakeProvenanceFetcher(),
                retrieved_at="2026-05-11T00:00:00Z",
                forms=["8-K"],
                sec_count=1,
                include_sec_document_text=True,
                sec_throttle_seconds=0,
            )

            manifest = json.loads(Path(response["manifest_out"]).read_text())
            config = json.loads(Path(response["real_case_config_out"]).read_text())
            summary = json.loads(Path(response["draft_summary_out"]).read_text())
            worksheet = Path(response["worksheet_out"]).read_text()
            curation_template = json.loads(Path(response["curation_template_out"]).read_text())
            source_candidates_exists = Path(response["source_candidates_out"]).exists()
            rejected_candidates_exists = Path(response["rejected_candidates_out"]).exists()

        self.assertTrue(response["ok"])
        self.assertEqual(response["stage"], "complete")
        self.assertEqual(response["case_readiness"], "curator_ready")
        self.assertEqual(response["accepted_sources"], 2)
        self.assertEqual(response["blocked_future_sources"], 1)
        self.assertTrue(source_candidates_exists)
        self.assertTrue(rejected_candidates_exists)
        self.assertEqual(manifest["artifacts"][0]["params"]["token"], "[REDACTED]")
        self.assertEqual(config["case_metadata"]["ticker"], "EXMPL")
        self.assertEqual(summary["recommended_next_action"], "Add 3-5 human-curated competing narratives.")
        self.assertIn("No winning narrative has been asserted", worksheet)
        self.assertEqual(len(curation_template["narratives"]), 5)
        self.assertEqual(curation_template["source_pool"]["allowed"][0]["availability_status"], "allowed")
        self.assertIn("supporting_source_ids", curation_template["narratives"][0])

    def test_write_curated_narratives_template_exposes_source_pools_and_slots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            rehearsal = rehearse_real_case(
                ticker="EXMPL",
                company_name="Example Co",
                event_type="earnings/guidance",
                event_date="2025-01-02",
                replay_lock="2025-01-02T10:00:00-05:00",
                date_from="2025-01-01",
                date_to="2025-01-07",
                out_root=root,
                providers=["finnhub", "sec"],
                finnhub_token="secret-token",
                sec_user_agent="NarrativeDesk Tests test@example.com",
                fetcher=FakeProvenanceFetcher(),
                retrieved_at="2026-05-11T00:00:00Z",
                forms=["8-K"],
                sec_count=1,
                include_sec_document_text=True,
                sec_throttle_seconds=0,
                curation_template=False,
            )
            draft_dir = Path(rehearsal["draft_dir"])

            response = write_curated_narratives_template(
                draft_dir,
                narrative_count=3,
                allowed_limit=1,
                blocked_limit=1,
            )
            payload = json.loads(Path(response["out"]).read_text())

        self.assertTrue(response["ok"])
        self.assertEqual(response["narrative_slot_count"], 3)
        self.assertEqual(response["rendered_allowed_source_count"], 1)
        self.assertEqual(response["rendered_blocked_future_source_count"], 1)
        self.assertIn("Do not treat this file as a real financial claim", payload["_note"])
        self.assertEqual(len(payload["narratives"]), 3)
        self.assertEqual(payload["narratives"][0]["narrative_id"], "NARR-EXMPL-001")
        self.assertEqual(payload["narratives"][0]["supporting_source_ids"], [])
        self.assertEqual(len(payload["source_pool"]["allowed"]), 1)
        self.assertEqual(len(payload["source_pool"]["blocked_future"]), 1)

    def test_apply_curated_narratives_rejects_unedited_template_placeholders(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            rehearsal = rehearse_real_case(
                ticker="EXMPL",
                company_name="Example Co",
                event_type="earnings/guidance",
                event_date="2025-01-02",
                replay_lock="2025-01-02T10:00:00-05:00",
                date_from="2025-01-01",
                date_to="2025-01-07",
                out_root=root,
                providers=["finnhub", "sec"],
                finnhub_token="secret-token",
                sec_user_agent="NarrativeDesk Tests test@example.com",
                fetcher=FakeProvenanceFetcher(),
                retrieved_at="2026-05-11T00:00:00Z",
                forms=["8-K"],
                sec_count=1,
                include_sec_document_text=True,
                sec_throttle_seconds=0,
            )

            with self.assertRaisesRegex(RealProvenanceError, "TBD placeholder"):
                apply_curated_narratives(
                    rehearsal["draft_dir"],
                    rehearsal["curation_template_out"],
                )

    def test_apply_curated_narratives_links_sources_and_writes_curated_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            rehearsal = rehearse_real_case(
                ticker="EXMPL",
                company_name="Example Co",
                event_type="earnings/guidance",
                event_date="2025-01-02",
                replay_lock="2025-01-02T10:00:00-05:00",
                date_from="2025-01-01",
                date_to="2025-01-07",
                out_root=root,
                providers=["finnhub", "sec"],
                finnhub_token="secret-token",
                sec_user_agent="NarrativeDesk Tests test@example.com",
                fetcher=FakeProvenanceFetcher(),
                retrieved_at="2026-05-11T00:00:00Z",
                forms=["8-K"],
                sec_count=1,
                include_sec_document_text=True,
                sec_throttle_seconds=0,
            )
            draft_dir = Path(rehearsal["draft_dir"])
            draft_config = json.loads((draft_dir / "real_case_config.json").read_text())
            allowed_ids = [
                source["source_id"]
                for source in draft_config["manual_sources"]
                if source["availability_status"] == "allowed"
            ]
            future_ids = [
                source["source_id"]
                for source in draft_config["manual_sources"]
                if source["availability_status"] == "blocked_future"
            ]
            narratives_path = draft_dir / "curated_narratives.json"
            narratives_path.write_text(
                json.dumps(
                    {
                        "narratives": [
                            {
                                "narrative_id": "NARR-REAL-001",
                                "title": "Forward demand slowdown",
                                "narrative": "The move reflects concern that forward demand is slowing.",
                                "mechanism": "Lower expected demand reduces forward revenue estimates.",
                                "directional_implication": "bearish",
                                "time_horizon": "20 trading days",
                                "expected_observables": ["Forward estimates fall after the replay window."],
                                "supporting_source_ids": [allowed_ids[0]],
                                "contradicting_source_ids": [allowed_ids[1]],
                                "future_supporting_source_ids": [future_ids[0]],
                                "scoring_inputs": {
                                    "evidence_strength": 0.75,
                                    "mechanism_specificity": 0.8,
                                    "source_independence": 0.65,
                                    "cross_sectional_fit": 0.7,
                                    "contradiction_resistance": 0.6,
                                    "timestamp_advantage": 0.8,
                                    "forward_observable_quality": 0.78,
                                    "crowding_risk": 0.25,
                                    "unsupported_claim_penalty": 0.03,
                                },
                            }
                        ]
                    }
                )
            )

            response = apply_curated_narratives(draft_dir, narratives_path)
            curated_config = json.loads(Path(response["out"]).read_text())
            source_pack = build_real_source_pack(
                curated_config,
                base_path=draft_dir,
                retrieved_at="2026-05-11T00:00:00Z",
            )
            config_errors = validate_real_case_config(curated_config, base_path=draft_dir, check_files=True)
            source_pack_errors = validate_source_pack(source_pack, require_narratives=True)
            source_by_id = {source["source_id"]: source for source in curated_config["manual_sources"]}

        self.assertTrue(response["ok"])
        self.assertEqual(response["narrative_count"], 1)
        self.assertEqual(response["allowed_source_link_count"], 2)
        self.assertEqual(response["future_source_link_count"], 1)
        self.assertEqual(config_errors, [])
        self.assertEqual(source_pack_errors, [])
        self.assertNotIn("supporting_source_ids", curated_config["narratives"][0])
        self.assertIn("NARR-REAL-001", source_by_id[allowed_ids[0]]["supported_narrative_ids"])
        self.assertIn("NARR-REAL-001", source_by_id[allowed_ids[1]]["contradicted_narrative_ids"])
        self.assertIn("NARR-REAL-001", source_by_id[future_ids[0]]["supported_narrative_ids"])

    def test_cli_real_case_curated_bundle_applies_curation_and_verifies_bundle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            rehearsal = rehearse_real_case(
                ticker="EXMPL",
                company_name="Example Co",
                event_type="earnings/guidance",
                event_date="2025-01-02",
                replay_lock="2025-01-02T10:00:00-05:00",
                date_from="2025-01-01",
                date_to="2025-01-07",
                out_root=root,
                providers=["finnhub", "sec"],
                finnhub_token="secret-token",
                sec_user_agent="NarrativeDesk Tests test@example.com",
                fetcher=FakeProvenanceFetcher(),
                retrieved_at="2026-05-11T00:00:00Z",
                forms=["8-K"],
                sec_count=1,
                include_sec_document_text=True,
                sec_throttle_seconds=0,
            )
            draft_dir = Path(rehearsal["draft_dir"])
            draft_config = json.loads((draft_dir / "real_case_config.json").read_text())
            allowed_ids = [
                source["source_id"]
                for source in draft_config["manual_sources"]
                if source["availability_status"] == "allowed"
            ]
            future_ids = [
                source["source_id"]
                for source in draft_config["manual_sources"]
                if source["availability_status"] == "blocked_future"
            ]
            narratives_path = draft_dir / "curated_narratives.json"
            narratives_path.write_text(
                json.dumps(
                    {
                        "narratives": [
                            {
                                "narrative_id": "NARR-REAL-001",
                                "title": "Forward demand slowdown",
                                "narrative": "The move reflects concern that forward demand is slowing.",
                                "mechanism": "Lower expected demand reduces forward revenue estimates.",
                                "directional_implication": "bearish",
                                "time_horizon": "20 trading days",
                                "expected_observables": ["Forward estimates fall after the replay window."],
                                "supporting_source_ids": [allowed_ids[0]],
                                "contradicting_source_ids": [allowed_ids[1]],
                                "future_supporting_source_ids": [future_ids[0]],
                                "scoring_inputs": {
                                    "evidence_strength": 0.75,
                                    "mechanism_specificity": 0.8,
                                    "source_independence": 0.65,
                                    "cross_sectional_fit": 0.7,
                                    "contradiction_resistance": 0.6,
                                    "timestamp_advantage": 0.8,
                                    "forward_observable_quality": 0.78,
                                    "crowding_risk": 0.25,
                                    "unsupported_claim_penalty": 0.03,
                                },
                            }
                        ]
                    }
                )
            )
            bundle_dir = root / "bundle"
            env_file = root / ".env.local"
            env_file.write_text(
                "\n".join(
                    [
                        "FINNHUB_API_KEY=file-secret-token",
                        "SEC_USER_AGENT=AppleAnalyst (contact@example.com)",
                    ]
                )
                + "\n"
            )

            status_before = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "narrativedesk.cli",
                    "real-case-status",
                    "--draft-dir",
                    str(draft_dir),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "narrativedesk.cli",
                    "real-case-curated-bundle",
                    "--draft-dir",
                    str(draft_dir),
                    "--narratives",
                    str(narratives_path),
                    "--out-dir",
                    str(bundle_dir),
                    "--retrieved-at",
                    "2026-05-11T00:00:00Z",
                    "--label",
                    "EXMPL curated rehearsal",
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
            status_after = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "narrativedesk.cli",
                    "real-case-status",
                    "--draft-dir",
                    str(draft_dir),
                    "--narratives",
                    str(narratives_path),
                    "--bundle-dir",
                    str(bundle_dir),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
            preflight_after = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "narrativedesk.cli",
                    "real-case-preflight",
                    "--ticker",
                    "EXMPL",
                    "--event-date",
                    "2025-01-02",
                    "--out-root",
                    str(root),
                    "--env-file",
                    str(env_file),
                    "--narratives",
                    str(narratives_path),
                    "--bundle-dir",
                    str(bundle_dir),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
            status_before_response = json.loads(status_before.stdout)
            response = json.loads(result.stdout)
            status_after_response = json.loads(status_after.stdout)
            preflight_after_response = json.loads(preflight_after.stdout)
            verification = json.loads((bundle_dir / "bundle_verify.json").read_text())
            source_pack = json.loads((bundle_dir / "source_pack.json").read_text())
            report_exists = (bundle_dir / "report.md").exists()
            manifest_exists = (bundle_dir / "manifest.json").exists()
            curated_config_exists = Path(response["curated_config_out"]).exists()

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(response["ok"])
        self.assertTrue(response["bundle_verify"]["ok"])
        self.assertEqual(status_before.returncode, 0, status_before.stderr + status_before.stdout)
        self.assertEqual(status_before_response["status"], "ready_to_bundle")
        self.assertTrue(status_before_response["draft"]["market_bars_check"]["ok"])
        self.assertEqual(status_after.returncode, 0, status_after.stderr + status_after.stdout)
        self.assertEqual(status_after_response["status"], "bundle_verified")
        self.assertTrue(status_after_response["bundle"]["ok"])
        self.assertEqual(preflight_after.returncode, 0, preflight_after.stderr + preflight_after.stdout)
        self.assertEqual(preflight_after_response["status"], "bundle_verified")
        self.assertNotIn("file-secret-token", preflight_after.stdout)
        self.assertNotIn("contact@example.com", preflight_after.stdout)
        self.assertTrue(verification["ok"])
        self.assertEqual(source_pack["narratives"][0]["narrative_id"], "NARR-REAL-001")
        self.assertTrue(report_exists)
        self.assertTrue(manifest_exists)
        self.assertTrue(curated_config_exists)

    def test_provider_error_is_manifested_and_normalization_continues(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "fetch"
            manifest = fetch_real_data(
                ticker="EXMPL",
                company_name="Example Co",
                date_from="2025-01-01",
                date_to="2025-01-07",
                providers=["finnhub", "sec"],
                out_dir=out_dir,
                finnhub_token="secret-token",
                sec_user_agent="NarrativeDesk Tests test@example.com",
                fetcher=FakeProvenanceFetcher(fail_candles=True),
                retrieved_at="2026-05-11T00:00:00Z",
                forms=["8-K"],
                sec_count=1,
                sec_throttle_seconds=0,
            )
            summary = normalize_real_data_fetch(
                out_dir,
                replay_lock="2025-01-02T10:00:00-05:00",
                generated_at="2026-05-11T00:00:00Z",
            )
            manifest_text = (out_dir / "fetch_manifest.json").read_text()

        self.assertFalse(manifest["ok"])
        self.assertIn("[REDACTED]", json.dumps(manifest))
        self.assertNotIn("secret-token", json.dumps(manifest))
        self.assertNotIn("secret-token", manifest_text)
        self.assertGreaterEqual(summary["eligible_candidates"], 1)

    def test_normalize_rejects_manifest_paths_that_escape_fetch_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fetch_dir = Path(tmpdir) / "fetch"
            fetch_dir.mkdir()
            (fetch_dir / "fetch_manifest.json").write_text(
                json.dumps(
                    {
                        "ok": True,
                        "ticker": "EXMPL",
                        "retrieved_at": "2026-05-11T00:00:00Z",
                        "artifacts": [
                            {
                                "provider": "finnhub",
                                "endpoint": "company_news",
                                "path": "../escape.json",
                                "status": "ok",
                            }
                        ],
                        "errors": [],
                    }
                )
            )

            with self.assertRaisesRegex(RealProvenanceError, "inside fetch directory"):
                normalize_real_data_fetch(fetch_dir, replay_lock="2025-01-02T10:00:00-05:00")

    def test_cli_normalize_and_draft_commands_write_expected_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fetch_dir = root / "fetch"
            fetch_real_data(
                ticker="EXMPL",
                company_name="Example Co",
                date_from="2025-01-01",
                date_to="2025-01-07",
                providers=["finnhub", "sec"],
                out_dir=fetch_dir,
                finnhub_token="secret-token",
                sec_user_agent="NarrativeDesk Tests test@example.com",
                fetcher=FakeProvenanceFetcher(),
                retrieved_at="2026-05-11T00:00:00Z",
                forms=["8-K"],
                sec_count=1,
                include_sec_document_text=True,
                sec_throttle_seconds=0,
            )
            env = {"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
            normalize_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "narrativedesk.cli",
                    "real-data-normalize",
                    str(fetch_dir),
                    "--replay-lock",
                    "2025-01-02T10:00:00-05:00",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            draft_dir = root / "draft"
            draft_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "narrativedesk.cli",
                    "real-case-draft",
                    "--ticker",
                    "EXMPL",
                    "--company-name",
                    "Example Co",
                    "--event-type",
                    "earnings/guidance",
                    "--event-date",
                    "2025-01-02",
                    "--replay-lock",
                    "2025-01-02T10:00:00-05:00",
                    "--normalized-dir",
                    str(fetch_dir / "normalized"),
                    "--out-dir",
                    str(draft_dir),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            normalize_response = json.loads(normalize_result.stdout)
            draft_response = json.loads(draft_result.stdout)

        self.assertEqual(normalize_result.returncode, 0, normalize_result.stderr + normalize_result.stdout)
        self.assertEqual(draft_result.returncode, 0, draft_result.stderr + draft_result.stdout)
        self.assertTrue(normalize_response["ok"])
        self.assertTrue(draft_response["ok"])
        self.assertEqual(draft_response["case_readiness"], "curator_ready")

    def test_cli_real_case_rehearse_reports_missing_env_without_network(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "narrativedesk.cli",
                    "real-case-rehearse",
                    "--ticker",
                    "EXMPL",
                    "--company-name",
                    "Example Co",
                    "--event-type",
                    "earnings/guidance",
                    "--event-date",
                    "2025-01-02",
                    "--replay-lock",
                    "2025-01-02T10:00:00-05:00",
                    "--from",
                    "2025-01-01",
                    "--to",
                    "2025-01-07",
                    "--providers",
                    "finnhub,sec",
                    "--fetch-dir",
                    str(root / "fetch"),
                    "--draft-dir",
                    str(root / "draft"),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
            response = json.loads(result.stdout)

        self.assertEqual(result.returncode, 1)
        self.assertFalse(response["ok"])
        self.assertEqual(response["stage"], "fetch")
        self.assertIn("FINNHUB_API_KEY is required", json.dumps(response))
        self.assertIn("SEC_USER_AGENT is required", json.dumps(response))
        self.assertFalse((root / "draft").exists())

    def test_aapl_rehearsal_runner_preflight_reports_missing_env_without_network(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/run_aapl_rehearsal.py",
                    "--preflight-only",
                    "--env-file",
                    str(root / ".env.local"),
                    "--fetch-dir",
                    str(root / "fetch"),
                    "--draft-dir",
                    str(root / "draft"),
                    "--bundle-dir",
                    str(root / "bundle"),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
            response = json.loads(result.stdout)

        self.assertEqual(result.returncode, 1)
        self.assertFalse(response["ok"])
        self.assertEqual(response["status"], "missing_env")
        self.assertEqual(response["stages"]["preflight"]["json"]["status"], "missing_env")
        self.assertIn("create local entries", response["next_action"])
        self.assertEqual(
            response["stages"]["preflight"]["json"]["env"]["missing_env"],
            ["FINNHUB_API_KEY", "SEC_USER_AGENT"],
        )
        self.assertEqual(response["stages"]["preflight"]["json"]["env"]["empty_env"], [])
        self.assertFalse((root / "fetch").exists())
        self.assertFalse((root / "draft").exists())

    def test_aapl_rehearsal_runner_preflight_reports_empty_env_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            env_file = root / ".env.local"
            env_file.write_text("FINNHUB_API_KEY=\nSEC_USER_AGENT=''\n")
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/run_aapl_rehearsal.py",
                    "--preflight-only",
                    "--env-file",
                    str(env_file),
                    "--fetch-dir",
                    str(root / "fetch"),
                    "--draft-dir",
                    str(root / "draft"),
                    "--bundle-dir",
                    str(root / "bundle"),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
            response = json.loads(result.stdout)

        self.assertEqual(result.returncode, 1)
        self.assertFalse(response["ok"])
        env_state = response["stages"]["preflight"]["json"]["env"]
        self.assertEqual(env_state["missing_env"], [])
        self.assertEqual(env_state["empty_env"], ["FINNHUB_API_KEY", "SEC_USER_AGENT"])
        self.assertIn("fill non-empty local values", response["next_action"])
        self.assertNotIn("''", result.stdout)

    def test_aapl_rehearsal_runner_resumes_from_curated_draft_to_bundle(self):
        runner = _load_aapl_rehearsal_runner()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            draft_dir = root / "draft"
            draft_dir.mkdir()
            (draft_dir / "curated_narratives.json").write_text("{}\n")
            args = SimpleNamespace(
                ticker="EXMPL",
                company_name="Example Co",
                event_type="earnings/guidance",
                event_date="2025-01-02",
                replay_lock="2025-01-02T10:00:00-05:00",
                date_from="2025-01-01",
                date_to="2025-01-07",
                providers="finnhub,sec",
                env_file=str(root / ".env.local"),
                fetch_dir=str(root / "fetch"),
                draft_dir=str(draft_dir),
                bundle_dir=str(root / "bundle"),
                narratives=None,
                sec_count=5,
                forms="8-K,10-Q,10-K",
                no_sec_document_text=False,
                preflight_only=False,
                build_bundle=False,
                market_bars=None,
            )
            calls = []

            def fake_run_cli(command, **_kwargs):
                calls.append(command)
                if command[0] == "real-case-preflight":
                    return {
                        "returncode": 1,
                        "json": {
                            "ok": False,
                            "status": "missing_bundle",
                            "next_action": "Run real-case-curated-bundle with this bundle directory.",
                        },
                    }
                if command[0] == "real-case-curated-bundle":
                    return {"returncode": 0, "json": {"ok": True}}
                if command[0] == "real-case-quality":
                    return {
                        "returncode": 0,
                        "json": {
                            "ok": True,
                            "next_action": "Review the report and decide whether this private case is demo-worthy.",
                        },
                    }
                raise AssertionError(f"Unexpected command: {command}")

            with patch.object(runner, "_run_cli", side_effect=fake_run_cli):
                response = runner.run_rehearsal(args)

        self.assertTrue(response["ok"])
        self.assertEqual(response["status"], "quality_ready")
        self.assertEqual([call[0] for call in calls], ["real-case-preflight", "real-case-curated-bundle", "real-case-quality"])
        self.assertNotIn("real-case-rehearse", [call[0] for call in calls])

    def test_aapl_rehearsal_runner_resumes_from_frozen_fetch_without_env(self):
        runner = _load_aapl_rehearsal_runner()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            draft_dir = root / "draft"
            draft_dir.mkdir()
            calls = []

            def fake_run_cli(command, **_kwargs):
                calls.append(command)
                if command[0] == "real-case-preflight":
                    return {
                        "returncode": 0,
                        "command": command,
                        "json": {"ok": True, "status": "ready_to_normalize"},
                    }
                if command[0] == "real-data-normalize":
                    return {
                        "returncode": 0,
                        "command": command,
                        "json": {"ok": True, "out_dir": str(root / "fetch" / "normalized")},
                    }
                if command[0] == "real-case-draft":
                    return {"returncode": 0, "command": command, "json": {"ok": True}}
                if command[0] == "real-case-worksheet":
                    return {"returncode": 0, "command": command, "json": {"ok": True}}
                if command[0] == "real-case-curation-template":
                    (draft_dir / "curated_narratives.template.json").write_text("{}\n")
                    return {"returncode": 0, "command": command, "json": {"ok": True}}
                if command[0] == "real-case-status":
                    return {
                        "returncode": 0,
                        "command": command,
                        "json": {"ok": True, "status": "ready_to_bundle"},
                    }
                raise AssertionError(f"Unexpected command: {command}")

            args = SimpleNamespace(
                ticker="AAPL",
                company_name="Apple Inc.",
                event_type="earnings/guidance",
                event_date="2024-05-02",
                replay_lock="2024-05-03T10:00:00-04:00",
                date_from="2024-05-01",
                date_to="2024-05-20",
                providers="finnhub,sec",
                env_file=str(root / ".env.local"),
                fetch_dir=str(root / "fetch"),
                draft_dir=str(draft_dir),
                bundle_dir=str(root / "bundle"),
                narratives=None,
                sec_count=5,
                forms="8-K,10-Q,10-K",
                no_sec_document_text=False,
                preflight_only=False,
                build_bundle=False,
                market_bars=None,
            )
            with patch.object(runner, "_run_cli", side_effect=fake_run_cli):
                response = runner.run_rehearsal(args)

        self.assertFalse(response["ok"])
        self.assertEqual(response["status"], "needs_curation")
        self.assertEqual(
            [call[0] for call in calls],
            [
                "real-case-preflight",
                "real-data-normalize",
                "real-case-draft",
                "real-case-worksheet",
                "real-case-curation-template",
                "real-case-status",
            ],
        )
        self.assertNotIn("real-case-rehearse", [call[0] for call in calls])

    def test_aapl_rehearsal_runner_preserves_needs_sources_status(self):
        runner = _load_aapl_rehearsal_runner()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            draft_dir = root / "draft"
            draft_dir.mkdir()
            calls = []

            def fake_run_cli(command, **_kwargs):
                calls.append(command)
                if command[0] == "real-case-preflight":
                    return {
                        "returncode": 0,
                        "command": command,
                        "json": {"ok": True, "status": "ready_to_draft"},
                    }
                if command[0] == "real-case-draft":
                    return {"returncode": 0, "command": command, "json": {"ok": True}}
                if command[0] == "real-case-worksheet":
                    return {"returncode": 0, "command": command, "json": {"ok": True}}
                if command[0] == "real-case-curation-template":
                    (draft_dir / "curated_narratives.template.json").write_text("{}\n")
                    return {"returncode": 0, "command": command, "json": {"ok": True}}
                if command[0] == "real-case-status":
                    return {
                        "returncode": 1,
                        "command": command,
                        "json": {
                            "ok": False,
                            "status": "needs_sources",
                            "next_action": "Fetch or curate additional timestamped sources before narrative curation.",
                        },
                    }
                raise AssertionError(f"Unexpected command: {command}")

            args = SimpleNamespace(
                ticker="AAPL",
                company_name="Apple Inc.",
                event_type="earnings/guidance",
                event_date="2024-05-02",
                replay_lock="2024-05-03T10:00:00-04:00",
                date_from="2024-05-01",
                date_to="2024-05-20",
                providers="finnhub,sec",
                env_file=str(root / ".env.local"),
                fetch_dir=str(root / "fetch"),
                draft_dir=str(draft_dir),
                bundle_dir=str(root / "bundle"),
                narratives=None,
                sec_count=5,
                forms="8-K,10-Q,10-K",
                no_sec_document_text=False,
                preflight_only=False,
                build_bundle=False,
                market_bars=None,
            )
            with patch.object(runner, "_run_cli", side_effect=fake_run_cli):
                response = runner.run_rehearsal(args)

        self.assertFalse(response["ok"])
        self.assertEqual(response["status"], "needs_sources")
        self.assertEqual(
            [call[0] for call in calls],
            [
                "real-case-preflight",
                "real-case-draft",
                "real-case-worksheet",
                "real-case-curation-template",
                "real-case-status",
            ],
        )
        self.assertNotIn("real-case-curated-bundle", [call[0] for call in calls])

    def test_aapl_rehearsal_runner_repairs_needs_sources_with_market_bars(self):
        runner = _load_aapl_rehearsal_runner()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            draft_dir = root / "draft"
            draft_dir.mkdir()
            calls = []

            def fake_run_cli(command, **_kwargs):
                calls.append(command)
                if command[0] == "real-case-preflight":
                    return {
                        "returncode": 1,
                        "command": command,
                        "json": {
                            "ok": False,
                            "status": "needs_sources",
                            "next_action": "Fetch or curate additional timestamped sources before narrative curation.",
                        },
                    }
                if command[0] == "real-market-bars-check":
                    return {"returncode": 0, "command": command, "json": {"ok": True}}
                if command[0] == "real-case-draft":
                    return {"returncode": 0, "command": command, "json": {"ok": True}}
                if command[0] == "real-case-worksheet":
                    return {"returncode": 0, "command": command, "json": {"ok": True}}
                if command[0] == "real-case-curation-template":
                    (draft_dir / "curated_narratives.template.json").write_text("{}\n")
                    return {"returncode": 0, "command": command, "json": {"ok": True}}
                if command[0] == "real-case-status":
                    return {
                        "returncode": 0,
                        "command": command,
                        "json": {"ok": True, "status": "ready_to_bundle"},
                    }
                raise AssertionError(f"Unexpected command: {command}")

            args = SimpleNamespace(
                ticker="AAPL",
                company_name="Apple Inc.",
                event_type="earnings/guidance",
                event_date="2024-05-02",
                replay_lock="2024-05-03T10:00:00-04:00",
                date_from="2024-05-01",
                date_to="2024-05-20",
                providers="finnhub,sec",
                env_file=str(root / ".env.local"),
                fetch_dir=str(root / "fetch"),
                draft_dir=str(draft_dir),
                bundle_dir=str(root / "bundle"),
                narratives=None,
                sec_count=5,
                forms="8-K,10-Q,10-K",
                no_sec_document_text=False,
                preflight_only=False,
                build_bundle=False,
                market_bars=str(root / "market_bars.csv"),
            )
            with patch.object(runner, "_run_cli", side_effect=fake_run_cli):
                response = runner.run_rehearsal(args)

        self.assertFalse(response["ok"])
        self.assertEqual(response["status"], "needs_curation")
        self.assertEqual(calls[1][0], "real-market-bars-check")
        draft_call = next(call for call in calls if call[0] == "real-case-draft")
        self.assertIn("--market-bars", draft_call)
        self.assertIn(str(root / "market_bars.csv"), draft_call)

    def test_aapl_rehearsal_runner_rejects_bad_market_bars_before_drafting(self):
        runner = _load_aapl_rehearsal_runner()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            calls = []

            def fake_run_cli(command, **_kwargs):
                calls.append(command)
                if command[0] == "real-case-preflight":
                    return {
                        "returncode": 1,
                        "command": command,
                        "json": {
                            "ok": False,
                            "status": "needs_sources",
                            "next_action": "Fetch or curate additional timestamped sources before narrative curation.",
                        },
                    }
                if command[0] == "real-market-bars-check":
                    return {
                        "returncode": 1,
                        "command": command,
                        "json": {
                            "ok": False,
                            "errors": ["No replay-eligible rows found for AAPL at or before the replay lock."],
                        },
                    }
                raise AssertionError(f"Unexpected command: {command}")

            args = SimpleNamespace(
                ticker="AAPL",
                company_name="Apple Inc.",
                event_type="earnings/guidance",
                event_date="2024-05-02",
                replay_lock="2024-05-03T10:00:00-04:00",
                date_from="2024-05-01",
                date_to="2024-05-20",
                providers="finnhub,sec",
                env_file=str(root / ".env.local"),
                fetch_dir=str(root / "fetch"),
                draft_dir=str(root / "draft"),
                bundle_dir=str(root / "bundle"),
                narratives=None,
                sec_count=5,
                forms="8-K,10-Q,10-K",
                no_sec_document_text=False,
                preflight_only=False,
                build_bundle=False,
                market_bars=str(root / "market_bars.csv"),
            )
            with patch.object(runner, "_run_cli", side_effect=fake_run_cli):
                response = runner.run_rehearsal(args)

        self.assertFalse(response["ok"])
        self.assertEqual(response["status"], "market_bars_failed")
        self.assertIn("No replay-eligible rows found", response["next_action"])
        self.assertEqual([call[0] for call in calls], ["real-case-preflight", "real-market-bars-check"])

    def test_aapl_rehearsal_runner_redacts_sensitive_child_output(self):
        runner = _load_aapl_rehearsal_runner()
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env.local"
            env_file.write_text(
                "\n".join(
                    [
                        "FINNHUB_API_KEY=fake-finnhub-secret",
                        "SEC_USER_AGENT='Private User Agent (contact@example.com)'",
                        "UNRELATED_VALUE=leave-visible",
                    ]
                )
            )
            redaction_values = runner._redaction_values(str(env_file))
            json_response = runner._json_or_error(
                json.dumps(
                    {
                        "ok": False,
                        "errors": [
                            "provider echoed fake-finnhub-secret",
                            "SEC said Private User Agent (contact@example.com)",
                        ],
                    }
                ),
                "",
                redaction_values,
            )
            text_response = runner._json_or_error(
                "stdout fake-finnhub-secret",
                "stderr contact@example.com",
                redaction_values,
            )
            env_file_text = env_file.read_text()

        combined = json.dumps({"json": json_response, "text": text_response})
        self.assertIn("[REDACTED]", combined)
        self.assertNotIn("fake-finnhub-secret", combined)
        self.assertNotIn("contact@example.com", combined)
        self.assertIn("leave-visible", env_file_text)

    def test_cli_real_case_worksheet_writes_curation_markdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            draft_dir = Path(tmpdir) / "draft"
            draft_dir.mkdir()
            (draft_dir / "draft_summary.json").write_text(
                json.dumps(
                    {
                        "ticker": "EXMPL",
                        "event_date": "2025-01-02",
                        "replay_lock": "2025-01-02T10:00:00-05:00",
                        "accepted_sources": 1,
                        "rejected_sources": 0,
                        "blocked_future_sources": 1,
                        "market_bars_available": True,
                        "filings_available": True,
                        "news_available": True,
                        "case_readiness": "curator_ready",
                        "missing_requirements": [],
                    }
                )
            )
            (draft_dir / "real_case_config.json").write_text(
                json.dumps(
                    {
                        "manual_sources": [
                            {
                                "source_id": "SRC-ALLOWED",
                                "availability_status": "allowed",
                                "title": "Allowed source",
                                "url": "https://example.com/allowed",
                                "published_at": "2025-01-02T14:00:00Z",
                                "claim_extracted": "Allowed evidence includes a pipe | character.",
                            },
                            {
                                "source_id": "SRC-FUTURE",
                                "availability_status": "blocked_future",
                                "title": "Future source",
                                "url": "https://example.com/future",
                                "published_at": "2025-01-07T14:00:00Z",
                                "claim_extracted": "Future validation evidence.",
                            },
                        ]
                    }
                )
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "narrativedesk.cli",
                    "real-case-worksheet",
                    "--draft-dir",
                    str(draft_dir),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
            response = json.loads(result.stdout)
            worksheet = (draft_dir / "curation_worksheet.md").read_text()

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(response["ok"])
        self.assertIn("# EXMPL Real-Case Replay Curation Worksheet", worksheet)
        self.assertIn("SRC-ALLOWED", worksheet)
        self.assertIn("SRC-FUTURE", worksheet)
        self.assertIn("pipe \\| character", worksheet)
        self.assertIn("No winning narrative has been asserted", worksheet)

    def test_cli_real_case_preflight_reports_missing_env_without_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "narrativedesk.cli",
                    "real-case-preflight",
                    "--ticker",
                    "AAPL",
                    "--event-date",
                    "2024-05-02",
                    "--providers",
                    "finnhub,sec",
                    "--out-root",
                    str(root),
                ],
                cwd=ROOT,
                env={
                    "PYTHONPATH": str(ROOT / "src"),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "FINNHUB_API_KEY": "secret-token",
                },
                capture_output=True,
                text=True,
                check=False,
            )
            response = json.loads(result.stdout)

        self.assertEqual(result.returncode, 1)
        self.assertFalse(response["ok"])
        self.assertEqual(response["status"], "missing_env")
        self.assertEqual(response["env"]["present_env"], ["FINNHUB_API_KEY"])
        self.assertEqual(response["env"]["missing_env"], ["SEC_USER_AGENT"])
        self.assertEqual(response["env"]["empty_env"], [])
        self.assertIn("create local entries for SEC_USER_AGENT", response["next_action"])
        self.assertIn("aapl-2024-05-02-rehearsal", response["paths"]["draft_dir"])
        self.assertNotIn("secret-token", result.stdout)

    def test_cli_real_case_preflight_resumes_frozen_fetch_without_env_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            env_file = root / ".env.local"
            fetch_dir = root / "fetch"
            draft_dir = root / "draft"
            bundle_dir = root / "bundle"
            fetch_dir.mkdir()
            env_file.write_text("FINNHUB_API_KEY=\nSEC_USER_AGENT=\n")
            (fetch_dir / "fetch_manifest.json").write_text("{}\n")
            first = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "narrativedesk.cli",
                    "real-case-preflight",
                    "--ticker",
                    "AAPL",
                    "--event-date",
                    "2024-05-02",
                    "--providers",
                    "finnhub,sec",
                    "--env-file",
                    str(env_file),
                    "--fetch-dir",
                    str(fetch_dir),
                    "--draft-dir",
                    str(draft_dir),
                    "--bundle-dir",
                    str(bundle_dir),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
            normalized = fetch_dir / "normalized"
            normalized.mkdir()
            (normalized / "source_candidates.json").write_text("{}\n")
            second = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "narrativedesk.cli",
                    "real-case-preflight",
                    "--ticker",
                    "AAPL",
                    "--event-date",
                    "2024-05-02",
                    "--providers",
                    "finnhub,sec",
                    "--env-file",
                    str(env_file),
                    "--fetch-dir",
                    str(fetch_dir),
                    "--draft-dir",
                    str(draft_dir),
                    "--bundle-dir",
                    str(bundle_dir),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
            first_response = json.loads(first.stdout)
            second_response = json.loads(second.stdout)

        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        self.assertEqual(first_response["status"], "ready_to_normalize")
        self.assertEqual(first_response["env"]["empty_env"], ["FINNHUB_API_KEY", "SEC_USER_AGENT"])
        self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
        self.assertEqual(second_response["status"], "ready_to_draft")
        self.assertEqual(second_response["env"]["empty_env"], ["FINNHUB_API_KEY", "SEC_USER_AGENT"])

    def test_cli_real_data_env_check_reports_names_without_values(self):
        env = {
            "PYTHONPATH": str(ROOT / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "FINNHUB_API_KEY": "secret-token",
        }
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "narrativedesk.cli",
                "real-data-env-check",
                "--providers",
                "finnhub,sec,newsapi",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        response = json.loads(result.stdout)

        self.assertEqual(result.returncode, 1)
        self.assertFalse(response["ok"])
        self.assertEqual(response["present_env"], ["FINNHUB_API_KEY"])
        self.assertEqual(response["missing_env"], ["SEC_USER_AGENT", "NEWS_API_KEY"])
        self.assertEqual(response["empty_env"], [])
        self.assertIn("create local entries for SEC_USER_AGENT, NEWS_API_KEY", response["next_action"])
        self.assertNotIn("secret-token", result.stdout)

    def test_cli_real_data_env_check_reports_empty_env_file_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env.local"
            env_file.write_text("FINNHUB_API_KEY=\nSEC_USER_AGENT=''\n")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "narrativedesk.cli",
                    "real-data-env-check",
                    "--providers",
                    "finnhub,sec",
                    "--env-file",
                    str(env_file),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
            response = json.loads(result.stdout)

        self.assertEqual(result.returncode, 1)
        self.assertFalse(response["ok"])
        self.assertEqual(response["present_env"], [])
        self.assertEqual(response["missing_env"], [])
        self.assertEqual(response["empty_env"], ["FINNHUB_API_KEY", "SEC_USER_AGENT"])
        self.assertIn("fill non-empty local values for FINNHUB_API_KEY, SEC_USER_AGENT", response["next_action"])

    def test_cli_real_data_env_check_reads_env_file_without_sourcing_shell(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env.local"
            env_file.write_text(
                "\n".join(
                    [
                        "FINNHUB_API_KEY=file-secret-token",
                        "SEC_USER_AGENT=AppleAnalyst (contact@example.com)",
                        "export NEWS_API_KEY='news-secret-token'",
                    ]
                )
                + "\n"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "narrativedesk.cli",
                    "real-data-env-check",
                    "--providers",
                    "finnhub,sec,newsapi",
                    "--env-file",
                    str(env_file),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
            response = json.loads(result.stdout)

        self.assertEqual(result.returncode, 0)
        self.assertTrue(response["ok"])
        self.assertEqual(
            response["present_env"],
            ["FINNHUB_API_KEY", "SEC_USER_AGENT", "NEWS_API_KEY"],
        )
        self.assertEqual(response["missing_env"], [])
        self.assertEqual(response["empty_env"], [])
        self.assertNotIn("file-secret-token", result.stdout)
        self.assertNotIn("contact@example.com", result.stdout)
        self.assertNotIn("news-secret-token", result.stdout)


if __name__ == "__main__":
    unittest.main()
