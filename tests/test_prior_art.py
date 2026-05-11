from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from narrativedesk.prior_art import inspect_prior_art_repos

ROOT = Path(__file__).resolve().parents[1]


class PriorArtInspectionTests(unittest.TestCase):
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

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue((out_dir / "prior-art-map.json").exists())
            self.assertTrue((out_dir / "prior-art-manual-sources.json").exists())
            self.assertEqual(len(list(out_dir.iterdir())), 2)
            response = json.loads(result.stdout)
            self.assertEqual(response["manual_source_count"], 1)
            self.assertIn("missing_field_counts", response)


if __name__ == "__main__":
    unittest.main()
