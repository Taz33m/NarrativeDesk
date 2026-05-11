from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any

from narrativedesk.pipeline import ledger_export, run_replay
from tests.schema_utils import validate_schema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "narrative_ledger.schema.json"
EVENT_FIXTURES = [
    ROOT / "data" / "fixtures" / "synthetic_event.json",
    ROOT / "data" / "fixtures" / "synthetic_event_aurora.json",
    ROOT / "data" / "fixtures" / "synthetic_event_lyra.json",
]


class LedgerSchemaTests(unittest.TestCase):
    def test_schema_describes_full_ledger_contract(self):
        schema = _load_schema()

        self.assertEqual(schema["title"], "NarrativeDesk Narrative Ledger")
        self.assertEqual(
            schema["required"],
            [
                "event",
                "replay_audit",
                "citation_qa",
                "source_reliability",
                "source_clustering",
                "narratives",
            ],
        )
        self.assertNotIn("narrative_id", schema["required"])
        self.assertIn("source_clustering", schema["properties"])

    def test_generated_ledgers_match_public_schema(self):
        schema = _load_schema()
        for fixture in EVENT_FIXTURES:
            with self.subTest(fixture=fixture.name):
                event, narratives, audit, _validation = run_replay(fixture)
                ledger = ledger_export(event, narratives, audit)

                validate_schema(ledger, schema, schema)

    def test_schema_rejects_unredacted_blocked_future_evidence(self):
        schema = _load_schema()
        event, narratives, audit, _validation = run_replay(EVENT_FIXTURES[0])
        ledger = ledger_export(event, narratives, audit)
        leaked = copy.deepcopy(ledger)
        leaked["replay_audit"]["blocked_evidence"][0]["claim"] = "leaked future claim"

        with self.assertRaisesRegex(AssertionError, "must not match"):
            validate_schema(leaked, schema, schema)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text())


if __name__ == "__main__":
    unittest.main()
