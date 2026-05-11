from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any

from tests.schema_utils import validate_schema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "source_pack.schema.json"
TEMPLATE_PATH = ROOT / "examples" / "source_pack_template.json"


class SourcePackSchemaTests(unittest.TestCase):
    def test_template_matches_public_schema(self):
        schema = _load_schema()
        payload = _load_template()

        validate_schema(payload, schema, schema)

    def test_schema_describes_source_pack_contract(self):
        schema = _load_schema()
        source_required = schema["$defs"]["source"]["required"]
        scoring_required = schema["$defs"]["scoring_inputs"]["required"]

        self.assertEqual(schema["title"], "NarrativeDesk Source Pack")
        self.assertEqual(schema["required"], ["case_metadata", "sources"])
        self.assertIn("validation_rows", json.dumps(schema["not"]))
        self.assertIn("content_hash", source_required)
        self.assertIn("independence_cluster_id", source_required)
        self.assertIn("unsupported_claim_penalty", scoring_required)

    def test_schema_rejects_embedded_validation_rows(self):
        schema = _load_schema()
        payload = _load_template()
        payload["validation_rows"] = []

        with self.assertRaisesRegex(AssertionError, "must not match"):
            validate_schema(payload, schema, schema)

    def test_schema_rejects_bad_content_hash_shape(self):
        schema = _load_schema()
        payload = _load_template()
        payload["sources"][0]["content_hash"] = "sha256:not-a-real-hash"

        with self.assertRaisesRegex(AssertionError, "content_hash expected pattern"):
            validate_schema(payload, schema, schema)

    def test_schema_rejects_score_outside_unit_range(self):
        schema = _load_schema()
        payload = _load_template()
        payload["narratives"][0]["scoring_inputs"]["evidence_strength"] = 1.2

        with self.assertRaisesRegex(AssertionError, "expected <= 1"):
            validate_schema(payload, schema, schema)

    def test_schema_rejects_naive_datetimes(self):
        schema = _load_schema()
        payload = _load_template()
        payload["case_metadata"]["event_timestamp"] = "2025-01-02T10:00:00"

        with self.assertRaisesRegex(AssertionError, "timezone offset"):
            validate_schema(payload, schema, schema)

    def test_schema_rejects_market_bar_without_replay_timestamp(self):
        schema = _load_schema()
        payload = _load_template()
        del payload["market_snapshot"]["event_bar"]["timestamp"]

        with self.assertRaisesRegex(AssertionError, "did not match anyOf"):
            validate_schema(payload, schema, schema)

    def test_schema_rejects_missing_replay_required_source_field(self):
        schema = _load_schema()
        payload = _load_template()
        del payload["sources"][0]["supported_narrative_ids"]

        with self.assertRaisesRegex(AssertionError, "supported_narrative_ids is required"):
            validate_schema(payload, schema, schema)

    def test_schema_rejects_unknown_source_fields(self):
        schema = _load_schema()
        payload = _load_template()
        payload["sources"][0]["api_key"] = "private-token"

        with self.assertRaisesRegex(AssertionError, "additional properties: api_key"):
            validate_schema(payload, schema, schema)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text())


def _load_template() -> dict[str, Any]:
    return copy.deepcopy(json.loads(TEMPLATE_PATH.read_text()))


if __name__ == "__main__":
    unittest.main()
