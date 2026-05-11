import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from narrativedesk.real_data import build_real_source_pack, validate_real_case_config
from narrativedesk.real_provenance import (
    RealProvenanceError,
    draft_real_case,
    fetch_real_data,
    normalize_real_data_fetch,
)
from narrativedesk.source_pack import validate_source_pack

ROOT = Path(__file__).resolve().parents[1]


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
        self.assertEqual(config["narratives"], [])
        self.assertTrue(any(source["availability_status"] == "blocked_future" for source in config["manual_sources"]))
        self.assertEqual(config["market_data"]["provider"], "local_csv")

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


if __name__ == "__main__":
    unittest.main()
