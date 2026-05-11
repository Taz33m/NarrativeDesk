from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any

from narrativedesk.source_pack import build_validation_fixture_template_from_source_pack, load_source_pack
from tests.schema_utils import validate_schema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "validation_fixture.schema.json"
VALIDATION_FIXTURES = [
    ROOT / "data" / "fixtures" / "synthetic_validation.json",
    ROOT / "data" / "fixtures" / "synthetic_validation_aurora.json",
    ROOT / "data" / "fixtures" / "synthetic_validation_lyra.json",
]


class ValidationFixtureSchemaTests(unittest.TestCase):
    def test_schema_describes_validation_fixture_contract(self):
        schema = _load_schema()
        row_schema = schema["$defs"]["validation_row"]

        self.assertEqual(schema["title"], "NarrativeDesk Validation Fixture")
        self.assertEqual(schema["required"], ["event_id", "rows"])
        self.assertIn("future_source_ids", schema["properties"])
        self.assertIn("document_text", json.dumps(row_schema["not"]))
        self.assertIn("future_source_ids", row_schema["properties"])

    def test_synthetic_validation_fixtures_match_public_schema(self):
        schema = _load_schema()
        for fixture in VALIDATION_FIXTURES:
            with self.subTest(fixture=fixture.name):
                validate_schema(json.loads(fixture.read_text()), schema, schema)

    def test_generated_validation_template_matches_public_schema(self):
        schema = _load_schema()
        source_pack = load_source_pack(ROOT / "examples" / "source_pack_template.json")
        validation = build_validation_fixture_template_from_source_pack(source_pack)

        validate_schema(validation, schema, schema)

    def test_schema_rejects_embedded_source_payload(self):
        schema = _load_schema()
        validation = _generated_validation()
        validation["rows"][0]["document_text"] = "Future source body should not live here."

        with self.assertRaisesRegex(AssertionError, "must not match"):
            validate_schema(validation, schema, schema)

    def test_schema_rejects_invalid_label(self):
        schema = _load_schema()
        validation = _generated_validation()
        validation["rows"][0]["label"] = "certain"

        with self.assertRaisesRegex(AssertionError, "expected one of"):
            validate_schema(validation, schema, schema)

    def test_schema_rejects_bad_future_source_count_shape(self):
        schema = _load_schema()
        validation = _generated_validation()
        validation["future_source_count"] = "1"

        with self.assertRaisesRegex(AssertionError, "expected type"):
            validate_schema(validation, schema, schema)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text())


def _generated_validation() -> dict[str, Any]:
    source_pack = load_source_pack(ROOT / "examples" / "source_pack_template.json")
    return copy.deepcopy(build_validation_fixture_template_from_source_pack(source_pack))


if __name__ == "__main__":
    unittest.main()
