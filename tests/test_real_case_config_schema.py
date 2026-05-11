from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from narrativedesk.real_data import load_real_case_config, validate_real_case_config
from tests.schema_utils import validate_schema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "real_case_config.schema.json"
TEMPLATE_PATH = ROOT / "examples" / "real_case_config_template.json"


class RealCaseConfigSchemaTests(unittest.TestCase):
    def test_template_matches_public_schema(self):
        schema = _load_schema()
        config = _load_template()

        validate_schema(config, schema, schema)

    def test_schema_describes_real_case_config_contract(self):
        schema = _load_schema()

        self.assertEqual(schema["title"], "NarrativeDesk Real Case Config")
        self.assertIn("market_data", schema["properties"])
        self.assertIn("manual_sources", schema["properties"])
        self.assertEqual(schema["$defs"]["case_metadata"]["required"], [
            "case_id",
            "ticker",
            "company_name",
            "event_timestamp",
        ])
        self.assertIn("claim_extracted", schema["$defs"]["manual_source"]["required"])
        self.assertIn("scoring_inputs", schema["$defs"]["narrative"]["required"])

    def test_schema_rejects_missing_replay_timestamp(self):
        schema = _load_schema()
        config = _load_template()
        del config["case_metadata"]["event_timestamp"]

        with self.assertRaisesRegex(AssertionError, "event_timestamp is required"):
            validate_schema(config, schema, schema)

    def test_schema_rejects_unsupported_provider(self):
        schema = _load_schema()
        config = _load_template()
        config["market_data"]["provider"] = "unsupported"

        with self.assertRaisesRegex(AssertionError, "expected one of"):
            validate_schema(config, schema, schema)

    def test_schema_rejects_invalid_manual_source(self):
        schema = _load_schema()
        config = _load_template()
        config["manual_sources"] = [{"published_at": "2025-01-02T09:00:00-05:00"}]

        with self.assertRaisesRegex(AssertionError, "claim_extracted is required"):
            validate_schema(config, schema, schema)

    def test_runtime_validation_reports_missing_local_files_when_requested(self):
        config = load_real_case_config(TEMPLATE_PATH)
        with tempfile.TemporaryDirectory() as tmpdir:
            errors = validate_real_case_config(config, base_path=tmpdir, check_files=True)

        self.assertTrue(any("transcripts[0].path does not exist" in error for error in errors))
        self.assertTrue(any("estimate_revisions.path does not exist" in error for error in errors))


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text())


def _load_template() -> dict[str, Any]:
    return copy.deepcopy(json.loads(TEMPLATE_PATH.read_text()))


if __name__ == "__main__":
    unittest.main()
