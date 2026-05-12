from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from narrativedesk.corpus_quality import assess_public_corpus_quality


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_CASE_INDEX = ROOT / "data" / "fixtures" / "public_case_index.json"


class PublicCorpusQualityTests(unittest.TestCase):
    def test_public_corpus_clears_serious_gate(self) -> None:
        result = assess_public_corpus_quality(PUBLIC_CASE_INDEX)

        self.assertTrue(result["ok"], result["next_action"])
        self.assertEqual(result["status"], "serious_corpus_ready")
        self.assertEqual(result["metrics"]["case_count"], 6)
        self.assertEqual(result["metrics"]["unique_ticker_count"], 6)
        self.assertEqual(result["metrics"]["unique_event_type_count"], 4)
        self.assertIn("operational/product incident", result["metrics"]["event_types"])
        self.assertIn("regulatory/antitrust shock", result["metrics"]["event_types"])
        self.assertIn("litigation settlement", result["metrics"]["event_types"])
        self.assertEqual(result["metrics"]["blocked_future_source_count"], 10)
        self.assertEqual(result["aggregate"]["top_ranked_validated_rate"], 1)
        self.assertGreater(
            result["aggregate"]["narrativedesk_tournament_validated_rate"],
            result["aggregate"]["headline_baseline_validated_rate"],
        )
        self.assertEqual(result["checks"]["provenance_clean"]["missing_url_count"], 0)
        save_case = next(case for case in result["cases"] if case["ticker"] == "SAVE")
        self.assertEqual(save_case["top_ranked_validation_status"], "validated")
        self.assertGreaterEqual(save_case["validation_source_count"], 1)
        self.assertEqual(save_case["bundle_status"], "verified")

    def test_public_corpus_reports_minimum_case_failure(self) -> None:
        result = assess_public_corpus_quality(PUBLIC_CASE_INDEX, min_cases=99)

        self.assertFalse(result["ok"])
        self.assertFalse(result["checks"]["minimum_case_count"]["ok"])
        self.assertEqual(result["checks"]["minimum_case_count"]["actual"], 6)

    def test_public_corpus_reports_event_type_breadth_failure(self) -> None:
        result = assess_public_corpus_quality(PUBLIC_CASE_INDEX, min_unique_event_types=99)

        self.assertFalse(result["ok"])
        self.assertFalse(result["checks"]["unique_event_type_breadth"]["ok"])
        self.assertEqual(result["checks"]["unique_event_type_breadth"]["actual"], 4)

    def test_public_corpus_quality_cli(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "narrativedesk.cli",
                "public-corpus-quality",
                str(PUBLIC_CASE_INDEX),
            ],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        self.assertIn("serious_corpus_ready", completed.stdout)


if __name__ == "__main__":
    unittest.main()
