from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from narrativedesk.prior_art import extract_mktmind_market_bars, inspect_prior_art_repos

ROOT = Path(__file__).resolve().parents[1]


class PriorArtInspectionTests(unittest.TestCase):
    def test_extract_mktmind_market_bars_writes_scratch_csv_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            dataset = workspace / "marketmind_qml_dataset.csv"
            with dataset.open("w", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["date", "ticker", "close", "volume", "ret_1d"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "date": "2024-05-02",
                        "ticker": "XLK",
                        "close": "97.29266357421875",
                        "volume": "13340000",
                        "ret_1d": "0.01441363986805344",
                    }
                )
                writer.writerow(
                    {
                        "date": "2024-05-03",
                        "ticker": "XLY",
                        "close": "86.0",
                        "volume": "1000",
                        "ret_1d": "0.01",
                    }
                )
            out_dir = workspace / "out"

            result = extract_mktmind_market_bars(
                dataset,
                output_dir=out_dir,
                tickers=["XLK"],
                date_from="2024-05-01",
                date_to="2024-05-03",
            )
            with result.market_bars_path.open() as handle:
                market_rows = list(csv.DictReader(handle))
            manifest = json.loads(result.manifest_path.read_text())

        self.assertEqual(len(market_rows), 1)
        self.assertEqual(market_rows[0]["date"], "2024-05-02")
        self.assertEqual(market_rows[0]["ticker"], "XLK")
        self.assertEqual(market_rows[0]["close"], "97.292664")
        self.assertAlmostEqual(float(market_rows[0]["open"]), 95.91024780273438, places=6)
        self.assertEqual(manifest["row_count"], 1)
        self.assertEqual(manifest["input_row_count"], 2)
        self.assertEqual(manifest["filtered_row_count"], 1)
        self.assertEqual(manifest["invalid_row_count"], 0)
        self.assertEqual(manifest["tickers"], ["XLK"])
        self.assertIn("previous close", manifest["derivation"])

    def test_inspection_maps_targets_and_extracts_only_provenanced_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            applecapital = workspace / "applecapital"
            log_dir = applecapital / "test-logs"
            log_dir.mkdir(parents=True)
            (log_dir / "AAPL_research.json").write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "published_at": "2025-01-31T16:15:00-05:00",
                                "url": "https://sec.example.com/aapl-10q",
                                "publisher": "SEC EDGAR",
                                "claim": "Apple filed a timestamped quarterly report.",
                            },
                            {
                                "published_at": "2025-01-31T16:20:00-05:00",
                                "publisher": "Model output without source URL",
                                "claim": "This should not become a manual source.",
                            },
                        ]
                    }
                )
            )

            inspection = inspect_prior_art_repos(
                {"applecapital": applecapital},
                output_dir=workspace / "out",
            )

        manual_sources = inspection.manual_sources_payload["manual_sources"]
        apple_targets = next(
            repo for repo in inspection.map_payload["repos"] if repo["repo"] == "applecapital"
        )["targets"]
        matched = next(target for target in apple_targets if target["path"] == "test-logs/*AAPL*.json")

        self.assertEqual(len(manual_sources), 1)
        self.assertEqual(manual_sources[0]["publisher"], "SEC EDGAR")
        self.assertEqual(manual_sources[0]["source_type"], "prior_art_manual_source")
        self.assertEqual(manual_sources[0]["prior_art_path"], "test-logs/AAPL_research.json")
        self.assertEqual(matched["candidate_record_count"], 2)
        self.assertEqual(matched["manual_source_count"], 1)
        self.assertEqual(matched["skipped_record_count"], 1)
        self.assertEqual(matched["missing_field_counts"]["url"], 1)
        self.assertEqual(matched["skipped_record_examples"][0]["missing_fields"], ["url"])
        self.assertEqual(inspection.manual_sources_payload["skipped_record_count"], 1)
        self.assertEqual(inspection.map_payload["missing_field_counts"]["url"], 1)

    def test_csv_records_require_timezone_aware_timestamp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            mktmind = workspace / "mktmind-qtm"
            data_dir = mktmind / "data"
            data_dir.mkdir(parents=True)
            with (data_dir / "marketmind_qml_dataset.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["published_at", "url", "publisher", "claim"])
                writer.writeheader()
                writer.writerow({
                    "published_at": "2025-01-31T21:15:00Z",
                    "url": "https://data.example.com/aapl",
                    "publisher": "Prior Art Dataset",
                    "claim": "Timestamped dataset row with provenance.",
                })
                writer.writerow({
                    "published_at": "2025-01-31",
                    "url": "https://data.example.com/no-time",
                    "publisher": "Prior Art Dataset",
                    "claim": "Date-only rows are skipped.",
                })

            inspection = inspect_prior_art_repos(
                {"mktmind-qtm": mktmind},
                output_dir=workspace / "out",
            )

        self.assertEqual(inspection.manual_sources_payload["manual_source_count"], 1)
        self.assertEqual(inspection.manual_sources_payload["skipped_record_count"], 1)
        self.assertEqual(inspection.map_payload["missing_field_counts"]["timezone_timestamp"], 1)

    def test_market_observation_csv_is_summarized_not_treated_as_claim_sources(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            mktmind = workspace / "mktmind-qtm"
            data_dir = mktmind / "data"
            data_dir.mkdir(parents=True)
            with (data_dir / "marketmind_qml_dataset.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["date", "ticker", "close", "volume", "ret_1d"])
                writer.writeheader()
                writer.writerow(
                    {
                        "date": "2024-05-02",
                        "ticker": "XLK",
                        "close": "97.29266357421875",
                        "volume": "13340000",
                        "ret_1d": "0.01441363986805344",
                    }
                )

            inspection = inspect_prior_art_repos(
                {"mktmind-qtm": mktmind},
                output_dir=workspace / "out",
            )

        mktmind_targets = next(
            repo for repo in inspection.map_payload["repos"] if repo["repo"] == "mktmind-qtm"
        )["targets"]
        dataset_target = next(target for target in mktmind_targets if target["path"] == "data/marketmind_qml_dataset.csv")

        self.assertEqual(inspection.manual_sources_payload["manual_source_count"], 0)
        self.assertEqual(inspection.manual_sources_payload["skipped_record_count"], 0)
        self.assertEqual(dataset_target["candidate_record_count"], 0)
        self.assertEqual(dataset_target["skipped_record_count"], 0)
        self.assertEqual(dataset_target["market_data_row_count"], 1)
        self.assertEqual(dataset_target["market_data_summaries"][0]["tickers"], ["XLK"])
        self.assertIn("not converted", dataset_target["market_data_summaries"][0]["conversion_rule"])

    def test_metric_summary_csv_is_summarized_not_treated_as_claim_sources(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            mktmind = workspace / "mktmind-qtm"
            results_dir = mktmind / "results"
            results_dir.mkdir(parents=True)
            with (results_dir / "metrics_summary.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["model", "split_id", "cutoff_date", "balanced_accuracy", "f1"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "model": "logistic_regression",
                        "split_id": "split_00",
                        "cutoff_date": "2024-05-02",
                        "balanced_accuracy": "0.51",
                        "f1": "0.42",
                    }
                )
                writer.writerow(
                    {
                        "model": "quantum_kernel_svm",
                        "split_id": "split_01",
                        "cutoff_date": "2024-05-03",
                        "balanced_accuracy": "0.59",
                        "f1": "0.50",
                    }
                )

            inspection = inspect_prior_art_repos(
                {"mktmind-qtm": mktmind},
                output_dir=workspace / "out",
            )

        mktmind_targets = next(
            repo for repo in inspection.map_payload["repos"] if repo["repo"] == "mktmind-qtm"
        )["targets"]
        metrics_target = next(target for target in mktmind_targets if target["path"] == "results/metrics_summary.csv")

        self.assertEqual(inspection.manual_sources_payload["manual_source_count"], 0)
        self.assertEqual(inspection.manual_sources_payload["skipped_record_count"], 0)
        self.assertEqual(metrics_target["candidate_record_count"], 0)
        self.assertEqual(metrics_target["skipped_record_count"], 0)
        self.assertEqual(metrics_target["metric_row_count"], 2)
        self.assertEqual(metrics_target["metric_summaries"][0]["models"], ["logistic_regression", "quantum_kernel_svm"])
        self.assertEqual(metrics_target["metric_summaries"][0]["best_balanced_accuracy"], 0.59)

    def test_script_writes_only_scratch_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            citadail = workspace / "citadail"
            out_dir = workspace / "out"
            output_dir = citadail / "frontend" / "outputs" / "equity-demo" / "aapl-buy-long"
            output_dir.mkdir(parents=True)
            (output_dir / "sources.json").write_text(
                json.dumps(
                    [
                        {
                            "published_at": "2025-01-31T21:15:00Z",
                            "url": "https://ir.example.com/aapl",
                            "publisher": "Company IR",
                            "summary": "Timestamped investor relations source.",
                        }
                    ]
                )
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "inspect_prior_art.py"),
                    "--repo-root",
                    f"citadail={citadail}",
                    "--out-dir",
                    str(out_dir),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
            response = json.loads(result.stdout)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue((out_dir / "prior-art-map.json").exists())
            self.assertTrue((out_dir / "prior-art-manual-sources.json").exists())
            self.assertEqual(len(list(out_dir.iterdir())), 2)
            self.assertEqual(response["manual_source_count"], 1)
            self.assertIn("missing_field_counts", response)

    def test_market_bars_script_writes_only_scratch_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            dataset = workspace / "marketmind_qml_dataset.csv"
            with dataset.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["date", "ticker", "close", "volume", "ret_1d"])
                writer.writeheader()
                writer.writerow(
                    {
                        "date": "2024-05-03",
                        "ticker": "XLK",
                        "close": "100.0",
                        "volume": "2000",
                        "ret_1d": "0.025",
                    }
                )
            out_dir = workspace / "out"

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "extract_prior_art_market_bars.py"),
                    "--mktmind-csv",
                    str(dataset),
                    "--out-dir",
                    str(out_dir),
                    "--tickers",
                    "XLK",
                    "--from",
                    "2024-05-01",
                    "--to",
                    "2024-05-03",
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
            response = json.loads(result.stdout)
            market_exists = (out_dir / "market_bars.csv").exists()
            manifest_exists = (out_dir / "market_bars_manifest.json").exists()
            output_count = len(list(out_dir.iterdir()))

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(response["ok"])
        self.assertEqual(response["row_count"], 1)
        self.assertTrue(market_exists)
        self.assertTrue(manifest_exists)
        self.assertEqual(output_count, 2)


if __name__ == "__main__":
    unittest.main()
