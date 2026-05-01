import unittest
from pathlib import Path

from narrativedesk.pipeline import ledger_export, load_validation_fixture, run_replay

ROOT = Path(__file__).resolve().parents[1]
EVENT_FIXTURE = ROOT / "data" / "fixtures" / "synthetic_event.json"
VALIDATION_FIXTURE = ROOT / "data" / "fixtures" / "synthetic_validation.json"


class PipelineTests(unittest.TestCase):
    def test_replay_ranks_orion_and_blocks_future_source(self):
        event, narratives, audit, validation = run_replay(EVENT_FIXTURE)

        self.assertEqual(event.ticker, "ORION")
        self.assertEqual(validation, {})
        self.assertEqual(len(narratives), 4)
        self.assertEqual([narrative.rank for narrative in narratives], [1, 2, 3, 4])
        self.assertEqual(narratives[0].title, "Forward demand slowdown")
        self.assertAlmostEqual(narratives[0].overall_narrative_score, 0.7838888889)
        self.assertEqual(audit.blocked_source_ids, ["SRC-009"])
        self.assertEqual(audit.removed_evidence_by_narrative, {"NARR-001": ["SRC-009"]})
        self.assertEqual(audit.blocked_evidence[0]["source_id"], "SRC-009")

        returned_sources = [
            evidence.source_id
            for narrative in narratives
            for evidence in narrative.all_evidence()
        ]
        self.assertNotIn("SRC-009", returned_sources)

    def test_ledger_export_excludes_future_validation(self):
        event, narratives, audit, _validation = run_replay(EVENT_FIXTURE)
        ledger = ledger_export(event, narratives, audit)

        self.assertIn("event", ledger)
        self.assertIn("replay_audit", ledger)
        self.assertIn("narratives", ledger)
        self.assertNotIn("validation", ledger)
        self.assertEqual(ledger["replay_audit"]["blocked_source_ids"], ["SRC-009"])

    def test_validation_fixture_is_separate(self):
        validation = load_validation_fixture(VALIDATION_FIXTURE)

        self.assertEqual(validation["event_id"], "EVT-ORION-2025-08-07")
        self.assertEqual([row["window"] for row in validation["rows"]], ["T+5", "T+20", "T+60"])
        self.assertEqual(validation["rows"][1]["label"], "validated")


if __name__ == "__main__":
    unittest.main()
