import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from narrativedesk.pipeline import load_validation_fixture
from narrativedesk.validation_fixture import validate_validation_fixture

ROOT = Path(__file__).resolve().parents[1]


class ValidationFixtureTests(unittest.TestCase):
    def test_synthetic_fixture_validates(self):
        payload = load_validation_fixture(ROOT / "data" / "fixtures" / "synthetic_validation.json")

        self.assertEqual(payload["event_id"], "EVT-ORION-2025-08-07")
        self.assertEqual(validate_validation_fixture(payload), [])

    def test_future_source_rows_must_be_declared_top_level(self):
        payload = {
            "event_id": "EVT-VALIDATION",
            "status": "pending",
            "rows": [
                {
                    "window": "T+20",
                    "label": "pending",
                    "narrative_id": "NARR-001",
                    "expected_observable": "Estimate revisions move in the expected direction.",
                    "future_source_ids": ["SRC-009"],
                    "what_happened": "Pending.",
                }
            ],
        }

        errors = validate_validation_fixture(payload)

        self.assertIn("rows[0].future_source_ids not declared at top level: SRC-009", errors)

    def test_future_source_count_must_match_unique_ids(self):
        payload = {
            "event_id": "EVT-VALIDATION",
            "status": "pending",
            "future_source_ids": ["SRC-009"],
            "future_source_count": 2,
            "rows": [
                {
                    "window": "T+20",
                    "label": "pending",
                    "narrative_id": "NARR-001",
                    "expected_observable": "Estimate revisions move in the expected direction.",
                    "future_source_ids": ["SRC-009"],
                    "what_happened": "Pending.",
                }
            ],
        }

        errors = validate_validation_fixture(payload)

        self.assertIn("future_source_count 2 does not match 1 future_source_ids", errors)

    def test_future_source_ids_must_be_unique(self):
        payload = {
            "event_id": "EVT-VALIDATION",
            "status": "pending",
            "future_source_ids": ["SRC-009", "SRC-009"],
            "rows": [],
        }

        errors = validate_validation_fixture(payload)

        self.assertIn("future_source_ids contains duplicates: SRC-009", errors)

    def test_rows_reject_embedded_source_payload_fields(self):
        payload = {
            "event_id": "EVT-VALIDATION",
            "status": "pending",
            "rows": [
                {
                    "window": "T+20",
                    "label": "validated",
                    "narrative_id": "NARR-001",
                    "expected_observable": "Estimate revisions move in the expected direction.",
                    "what_happened": "Validated by separate future-source IDs.",
                    "document_text": "Future analyst source text should stay in the source pack.",
                }
            ],
        }

        errors = validate_validation_fixture(payload)

        self.assertIn("rows[0] cannot contain source payload fields: document_text", errors)

    def test_loader_rejects_invalid_validation_fixture(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "validation.json"
            path.write_text(json.dumps({"event_id": "EVT-BAD", "rows": {"bad": True}}))

            with self.assertRaisesRegex(ValueError, "rows must be a list"):
                load_validation_fixture(path)

    def test_cli_validation_validate_returns_preview(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "narrativedesk.cli",
                "validation-validate",
                str(ROOT / "data" / "fixtures" / "synthetic_validation.json"),
            ],
            cwd=ROOT,
            env={"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": "src"},
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        response = json.loads(result.stdout)
        self.assertTrue(response["ok"])
        self.assertEqual(response["preview"]["event_id"], "EVT-ORION-2025-08-07")
        self.assertEqual(response["preview"]["row_count"], 3)
        self.assertEqual(response["preview"]["future_source_ids"], ["SRC-009"])

    def test_cli_validation_validate_reports_errors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "validation.json"
            path.write_text(json.dumps({"event_id": "EVT-BAD", "rows": {"bad": True}}))

            result = subprocess.run(
                [sys.executable, "-m", "narrativedesk.cli", "validation-validate", str(path)],
                cwd=ROOT,
                env={"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": "src"},
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        response = json.loads(result.stdout)
        self.assertFalse(response["ok"])
        self.assertIn("rows must be a list", response["errors"])


if __name__ == "__main__":
    unittest.main()
