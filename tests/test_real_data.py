import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from narrativedesk.case_index import validate_case_index
from narrativedesk.real_data import (
    RealDataError,
    build_real_source_pack,
    load_real_case_config,
    preview_real_case_config,
    validate_real_case_config,
)
from narrativedesk.source_pack import preview_source_pack, validate_source_pack

ROOT = Path(__file__).resolve().parents[1]


class FakeFetcher:
    def __init__(self):
        self.calls = []

    def get_json(self, url, *, params=None, headers=None):
        self.calls.append({"url": url, "params": params or {}, "headers": headers or {}})
        if url.endswith("/stock/candle"):
            symbol = params["symbol"]
            return _candles_for(symbol)
        if url.endswith("/company-news"):
            return [
                {
                    "id": 11,
                    "datetime": _epoch("2025-01-02T14:00:00+00:00"),
                    "headline": "Example shares fall after guidance update",
                    "summary": "Management commentary focused on slower future expansion.",
                    "source": "Example Wire",
                    "url": "https://news.example.com/example-guidance",
                },
                {
                    "id": 12,
                    "datetime": _epoch("2025-01-07T13:00:00+00:00"),
                    "headline": "Analysts cut estimates after replay window",
                    "summary": "Later commentary is useful for validation, not event-time ranking.",
                    "source": "Example Wire",
                    "url": "https://news.example.com/example-estimate-cut",
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
            return {
                "entityName": "Example Co",
                "facts": {
                    "us-gaap": {
                        "RevenueFromContractWithCustomerExcludingAssessedTax": {
                            "units": {
                                "USD": [
                                    {
                                        "val": 1000000,
                                        "end": "2024-12-31",
                                        "filed": "2025-01-02",
                                        "form": "8-K",
                                        "fy": 2024,
                                        "fp": "FY",
                                        "accn": "0001234567-25-000001",
                                    }
                                ]
                            }
                        }
                    }
                },
            }
        raise AssertionError(f"Unexpected URL: {url}")

    def get_text(self, url, *, params=None, headers=None):
        self.calls.append({"url": url, "params": params or {}, "headers": headers or {}})
        if url == "https://www.sec.gov/Archives/edgar/data/1234567/000123456725000001/exmpl-20250102.htm":
            return """
            <html>
              <head><style>body { color: black; }</style></head>
              <body>
                <h1>Example Co 8-K</h1>
                <p>Management lowered full-year net addition guidance and described slower expansion.</p>
              </body>
            </html>
            """
        raise AssertionError(f"Unexpected text URL: {url}")


def _epoch(value):
    return int(datetime.fromisoformat(value).timestamp())


def _candles_for(symbol):
    close = {
        "EXMPL": 94.0,
        "PEER": 98.0,
        "SECTOR": 99.0,
    }[symbol]
    return {
        "s": "ok",
        "t": [
            _epoch("2024-12-31T00:00:00+00:00"),
            _epoch("2025-01-02T00:00:00+00:00"),
        ],
        "o": [100.0, 100.0],
        "c": [101.0, close],
        "h": [102.0, max(101.0, close)],
        "l": [99.0, min(99.0, close)],
        "v": [1000.0, 2000.0],
    }


def _config():
    return {
        "case_metadata": {
            "case_id": "EVT-REAL-EXMPL-2025-01-02",
            "ticker": "EXMPL",
            "company_name": "Example Co",
            "event_timestamp": "2025-01-02T17:00:00-05:00",
            "event_type": "earnings/guidance",
        },
        "event": {
            "event_type": "earnings/guidance",
            "event_summary": "Curated real-data replay scaffold.",
        },
        "market_data": {
            "provider": "finnhub",
            "resolution": "D",
            "peers": ["PEER"],
            "sector_symbol": "SECTOR",
        },
        "news": {
            "provider": "finnhub",
            "from": "2025-01-02",
            "to": "2025-01-07",
            "max_articles": 2,
        },
        "sec_filings": {
            "forms": ["8-K"],
            "count": 1,
            "include_document_text": True,
            "document_text_max_chars": 500,
        },
        "sec_facts": {
            "concepts": [
                {
                    "taxonomy": "us-gaap",
                    "tag": "RevenueFromContractWithCustomerExcludingAssessedTax",
                    "unit": "USD",
                    "label": "Revenue",
                }
            ],
            "max_facts_per_concept": 1,
        },
    }


class RealDataTests(unittest.TestCase):
    def test_example_real_case_config_template_is_loadable(self):
        config = load_real_case_config(ROOT / "examples" / "real_case_config_template.json")

        self.assertEqual(config["case_metadata"]["data_provenance_mode"], "real-curated")
        self.assertEqual(config["market_data"]["provider"], "finnhub")
        self.assertTrue(config["sec_filings"]["include_document_text"])
        self.assertEqual(validate_real_case_config(config), [])
        preview = preview_real_case_config(config)
        self.assertEqual(preview["ticker"], "REPLACE_WITH_TICKER")
        self.assertIn("FINNHUB_API_KEY", preview["provider_requirements"])
        self.assertIn("SEC_USER_AGENT", preview["provider_requirements"])

    def test_validate_real_case_config_reports_missing_local_files_when_requested(self):
        config = {
            "case_metadata": {
                "case_id": "EVT-LOCAL-EXMPL-2025-01-02",
                "ticker": "EXMPL",
                "company_name": "Example Co",
                "event_timestamp": "2025-01-02T10:00:00-05:00",
            },
            "market_data": {
                "provider": "csv",
                "path": "missing-prices.csv",
            },
            "transcripts": {
                "items": [
                    {
                        "path": "missing-transcript.txt",
                        "published_at": "2025-01-02T09:20:00-05:00",
                    }
                ]
            },
        }

        errors = validate_real_case_config(config, base_path=ROOT, check_files=True)

        self.assertTrue(any("market_data.path does not exist" in error for error in errors))
        self.assertTrue(any("transcripts[0].path does not exist" in error for error in errors))

    def test_validate_real_case_config_rejects_metadata_and_provider_gaps(self):
        config = {
            "case_metadata": {
                "case_id": "EVT-BAD",
                "ticker": "BAD",
                "company_name": "Bad Co",
                "event_timestamp": "2025-01-02T10:00:00-05:00",
                "data_provenance_mode": "synthetic",
            },
            "market_data": {
                "provider": "finnhub",
                "resolution": "D",
            },
            "news": {
                "provider": "unsupported",
            },
        }

        errors = validate_real_case_config(config)

        self.assertIn("case_metadata.data_provenance_mode must be real-curated for real-data configs", errors)
        self.assertTrue(any("Daily Finnhub candles cannot safely represent" in error for error in errors))
        self.assertIn("Unsupported news provider: unsupported", errors)

    def test_cli_real_pack_check_returns_preview_without_fetching(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "narrativedesk.cli",
                "real-pack-check",
                str(ROOT / "examples" / "real_case_config_template.json"),
            ],
            cwd=ROOT,
            env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        response = json.loads(result.stdout)
        self.assertTrue(response["ok"])
        self.assertEqual(response["preview"]["ticker"], "REPLACE_WITH_TICKER")

    def test_builds_real_curated_pack_from_finnhub_and_sec_sources(self):
        fetcher = FakeFetcher()

        payload = build_real_source_pack(
            _config(),
            finnhub_token="test-token",
            sec_user_agent="NarrativeDesk Tests test@example.com",
            fetcher=fetcher,
            retrieved_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
        )

        self.assertEqual(validate_source_pack(payload), [])
        preview = preview_source_pack(payload)
        self.assertEqual(preview["provenance_mode"], "real-curated")
        self.assertEqual(preview["source_counts"]["allowed"], 3)
        self.assertEqual(preview["source_counts"]["blocked_future"], 1)
        self.assertEqual(preview["blocked_future_source_ids"], ["NEWS-002"])
        self.assertEqual(
            preview["source_type_counts"],
            {
                "news_article": 2,
                "sec_filing": 1,
                "sec_xbrl_fact": 1,
            },
        )
        self.assertEqual(payload["market_snapshot"]["event_bar"]["close"], 94.0)
        self.assertEqual(payload["market_snapshot"]["peer_bars"][0]["symbol"], "PEER")
        self.assertEqual(payload["sources"][0]["source_id"], "NEWS-001")
        self.assertEqual(payload["sources"][1]["availability_status"], "blocked_future")
        self.assertEqual(payload["sources"][2]["source_type"], "sec_filing")
        self.assertIn("Management lowered full-year net addition guidance", payload["sources"][2]["document_text"])
        self.assertNotIn("<p>", payload["sources"][2]["document_text"])
        self.assertEqual(payload["sources"][3]["source_type"], "sec_xbrl_fact")
        self.assertIn("reported Revenue of 1000000 USD", payload["sources"][3]["claim_extracted"])
        sec_call = next(call for call in fetcher.calls if call["url"].startswith("https://data.sec.gov"))
        self.assertEqual(sec_call["headers"]["User-Agent"], "NarrativeDesk Tests test@example.com")
        sec_text_call = next(call for call in fetcher.calls if "/Archives/edgar/data/" in call["url"])
        self.assertEqual(sec_text_call["headers"]["User-Agent"], "NarrativeDesk Tests test@example.com")

    def test_builds_market_snapshot_from_frozen_csv_prices(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "prices.csv"
            csv_path.write_text(
                "\n".join(
                    [
                        "date,ticker,open,close,volume",
                        "2025-01-01,EXMPL,100,101,1000",
                        "2025-01-02,EXMPL,100,94,2000",
                        "2025-01-01,PEER,100,100,500",
                        "2025-01-02,PEER,100,98,800",
                        "2025-01-01,SECTOR,100,100,700",
                        "2025-01-02,SECTOR,100,99,900",
                    ]
                )
                + "\n"
            )
            config = {
                "case_metadata": {
                    "case_id": "EVT-CSV-EXMPL-2025-01-02",
                    "ticker": "EXMPL",
                    "company_name": "Example Co",
                    "event_timestamp": "2025-01-02T17:30:00-05:00",
                },
                "market_data": {
                    "provider": "csv",
                    "path": "prices.csv",
                    "peers": ["PEER"],
                    "sector_symbol": "SECTOR",
                },
                "manual_sources": [
                    {
                        "source_id": "MANUAL-001",
                        "source_type": "curated_source",
                        "publisher": "Curator",
                        "title": "Replay setup note",
                        "url": "https://example.com/replay-note",
                        "published_at": "2025-01-02T13:00:00Z",
                        "claim_extracted": "The replay case uses frozen historical price rows.",
                    }
                ],
            }

            payload = build_real_source_pack(
                config,
                base_path=tmpdir,
                retrieved_at="2026-05-10T00:00:00Z",
            )

        self.assertEqual(validate_source_pack(payload), [])
        self.assertEqual(payload["market_snapshot"]["event_bar"]["close"], 94.0)
        self.assertEqual(payload["market_snapshot"]["event_bar"]["average_volume"], 1000.0)
        self.assertEqual(payload["market_snapshot"]["peer_bars"][0]["close"], 98.0)
        self.assertEqual(payload["market_snapshot"]["sector_bar"]["symbol"], "SECTOR")

    def test_builds_transcript_and_estimate_revision_sources_from_local_exports(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            transcript_path = Path(tmpdir) / "transcript.txt"
            transcript_path.write_text(
                "Operator: Welcome.\nManagement: We are seeing slower net additions and higher churn.\n"
            )
            estimates_path = Path(tmpdir) / "estimate_revisions.csv"
            estimates_path.write_text(
                "\n".join(
                    [
                        "published_at,metric,period,old_estimate,new_estimate,unit,publisher,title,url",
                        "2025-01-02T14:40:00Z,Net additions,FY2025,12.0,10.5,million,Example Consensus,Pre-lock net adds trim,https://estimates.example.com/pre-lock",
                        "2025-01-07T13:00:00Z,Revenue,FY2025,100.0,94.0,USD million,Example Consensus,Post-lock revenue cut,https://estimates.example.com/post-lock",
                    ]
                )
                + "\n"
            )
            config = {
                "case_metadata": {
                    "case_id": "EVT-LOCAL-EXMPL-2025-01-02",
                    "ticker": "EXMPL",
                    "company_name": "Example Co",
                    "event_timestamp": "2025-01-02T10:00:00-05:00",
                },
                "transcripts": {
                    "items": [
                        {
                            "path": "transcript.txt",
                            "publisher": "Example Co investor relations",
                            "title": "Example Co earnings call transcript",
                            "url": "https://ir.example.com/transcript",
                            "published_at": "2025-01-02T14:20:00Z",
                        }
                    ]
                },
                "estimate_revisions": {
                    "provider": "csv",
                    "path": "estimate_revisions.csv",
                    "max_rows": 2,
                },
            }

            payload = build_real_source_pack(
                config,
                base_path=tmpdir,
                retrieved_at="2026-05-10T00:00:00Z",
            )

        self.assertEqual(validate_source_pack(payload), [])
        self.assertEqual(payload["sources"][0]["source_id"], "TRN-001")
        self.assertEqual(payload["sources"][0]["source_type"], "earnings_transcript")
        self.assertIn("slower net additions", payload["sources"][0]["document_text"])
        self.assertEqual(payload["sources"][1]["availability_status"], "allowed")
        self.assertEqual(payload["sources"][2]["availability_status"], "blocked_future")
        self.assertIn("changed from 100.0 to 94.0", payload["sources"][2]["claim_extracted"])

    def test_daily_candles_reject_intraday_replay_lock_without_override(self):
        config = _config()
        config["case_metadata"]["event_timestamp"] = "2025-01-02T10:00:00-05:00"

        with self.assertRaisesRegex(RealDataError, "Daily Finnhub candles cannot safely represent"):
            build_real_source_pack(
                config,
                finnhub_token="test-token",
                sec_user_agent="NarrativeDesk Tests test@example.com",
                fetcher=FakeFetcher(),
                retrieved_at="2026-05-10T00:00:00Z",
            )

    def test_cli_real_pack_build_reports_missing_provider_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "real_case.json"
            out_path = Path(tmpdir) / "source_pack.json"
            config_path.write_text(json.dumps(_config()))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "narrativedesk.cli",
                    "real-pack-build",
                    str(config_path),
                    "--out",
                    str(out_path),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("FINNHUB_API_KEY is required", result.stdout)

    def test_cli_real_pack_bundle_builds_local_replay_bundle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "prices.csv").write_text(
                "\n".join(
                    [
                        "date,ticker,open,close,volume",
                        "2025-01-02T09:55:00-05:00,EXMPL,100,94,2000",
                        "2025-01-02T09:55:00-05:00,PEER,100,98,1200",
                        "2025-01-02T09:55:00-05:00,SPY,100,99.5,5000",
                    ]
                )
                + "\n"
            )
            (tmp_path / "estimate_revisions.csv").write_text(
                "\n".join(
                    [
                        "published_at,metric,period,old_estimate,new_estimate,unit,publisher,title,url",
                        "2025-01-07T13:00:00Z,Revenue,FY2025,100.0,94.0,USD million,Example Consensus,Post-lock revenue cut,https://estimates.example.com/post-lock",
                    ]
                )
                + "\n"
            )
            config = {
                "case_metadata": {
                    "case_id": "EVT-BUNDLE-EXMPL-2025-01-02",
                    "ticker": "EXMPL",
                    "company_name": "Example Co",
                    "event_timestamp": "2025-01-02T10:00:00-05:00",
                    "event_type": "earnings/guidance",
                },
                "market_data": {
                    "provider": "csv",
                    "path": "prices.csv",
                    "peers": ["PEER"],
                    "sector_symbol": "SPY",
                },
                "manual_sources": [
                    {
                        "source_id": "MANUAL-001",
                        "source_type": "curated_source",
                        "publisher": "Curator",
                        "title": "Replay setup note",
                        "url": "https://example.com/replay-note",
                        "published_at": "2025-01-02T09:30:00-05:00",
                        "claim_extracted": "Management commentary pointed to slower forward demand.",
                        "supported_narrative_ids": ["BUNDLE-NARR-001"],
                    }
                ],
                "estimate_revisions": {
                    "provider": "csv",
                    "path": "estimate_revisions.csv",
                    "default_supported_narrative_ids": ["BUNDLE-NARR-001"],
                },
                "narratives": [
                    {
                        "narrative_id": "BUNDLE-NARR-001",
                        "title": "Forward demand slowdown",
                        "narrative": "The move reflects concern that forward demand is slowing.",
                        "mechanism": "Lower expected demand reduces forward revenue estimates.",
                        "directional_implication": "bearish",
                        "time_horizon": "20 trading days",
                        "expected_observables": ["Analysts reduce forward revenue estimates."],
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
                ],
            }
            config_path = tmp_path / "real_case_config.json"
            out_dir = tmp_path / "bundle"
            config_path.write_text(json.dumps(config))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "narrativedesk.cli",
                    "real-pack-bundle",
                    str(config_path),
                    "--out-dir",
                    str(out_dir),
                    "--retrieved-at",
                    "2026-05-10T00:00:00Z",
                    "--label",
                    "EXMPL local bundle",
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
            response = json.loads(result.stdout)
            source_pack = json.loads((out_dir / "source_pack.json").read_text())
            validation = json.loads((out_dir / "validation_fixture.json").read_text())
            manifest = json.loads((out_dir / "manifest.json").read_text())
            case_index_check = validate_case_index(out_dir / "case_index.json")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(response["ok"])
        self.assertEqual(response["case_id"], "EVT-BUNDLE-EXMPL-2025-01-02")
        self.assertEqual(source_pack["sources"][1]["availability_status"], "blocked_future")
        self.assertEqual(validation["future_source_ids"], ["EST-001"])
        self.assertEqual(manifest["case_id"], "EVT-BUNDLE-EXMPL-2025-01-02")
        self.assertEqual(manifest["replay_integrity"]["blocked_future_source_ids"], ["EST-001"])
        self.assertTrue(any(artifact["path"] == "source_pack.json" for artifact in manifest["artifacts"]))
        self.assertTrue(case_index_check["ok"], case_index_check["errors"])
