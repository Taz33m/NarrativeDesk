import json
import tempfile
import unittest
from pathlib import Path

from narrativedesk.pipeline import ledger_export, load_case_index, load_validation_fixture, run_replay

ROOT = Path(__file__).resolve().parents[1]
EVENT_FIXTURE = ROOT / "data" / "fixtures" / "synthetic_event.json"
VALIDATION_FIXTURE = ROOT / "data" / "fixtures" / "synthetic_validation.json"


class PipelineTests(unittest.TestCase):
    def test_replay_ranks_orion_and_blocks_future_source(self):
        event, narratives, audit, validation = run_replay(EVENT_FIXTURE)

        self.assertEqual(event.ticker, "ORION")
        self.assertEqual(event.daily_return, -0.114)
        self.assertEqual(event.peer_median_return, -0.012)
        self.assertEqual(event.abnormal_return, -0.102)
        self.assertEqual(event.volume_ratio, 2.4)
        self.assertEqual(validation, {})
        self.assertEqual(len(narratives), 4)
        self.assertEqual([narrative.rank for narrative in narratives], [1, 2, 3, 4])
        self.assertEqual(narratives[0].title, "Forward demand slowdown")
        self.assertAlmostEqual(narratives[0].overall_narrative_score, 0.7838888889)
        self.assertEqual(audit.blocked_source_ids, ["SRC-009"])
        self.assertEqual(audit.removed_evidence_by_narrative, {"NARR-001": ["SRC-009"]})
        self.assertEqual(audit.blocked_evidence[0]["source_id"], "SRC-009")
        self.assertEqual(audit.blocked_evidence[0]["replay_status"], "blocked_future")
        for leaked_key in ["claim", "title", "url", "content_hash", "publisher", "evidence_quality"]:
            self.assertNotIn(leaked_key, audit.blocked_evidence[0])

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
        self.assertIn("citation_qa", ledger)
        self.assertIn("source_clustering", ledger)
        self.assertIn("narratives", ledger)
        self.assertNotIn("validation", ledger)
        self.assertEqual(ledger["event"]["case_id"], "EVT-ORION-2025-08-07")
        self.assertEqual(ledger["replay_audit"]["blocked_source_ids"], ["SRC-009"])
        blocked = ledger["replay_audit"]["blocked_evidence"][0]
        self.assertEqual(blocked["source_id"], "SRC-009")
        self.assertNotIn("claim", blocked)
        self.assertNotIn("url", blocked)
        self.assertTrue(ledger["citation_qa"]["event_time_integrity_pass"])
        self.assertFalse(ledger["citation_qa"]["citation_qa_pass"])
        self.assertEqual(ledger["source_clustering"]["blocked_future_source_ids"], ["SRC-009"])

    def test_validation_fixture_is_separate(self):
        validation = load_validation_fixture(VALIDATION_FIXTURE)

        self.assertEqual(validation["event_id"], "EVT-ORION-2025-08-07")
        self.assertEqual(validation["future_source_ids"], ["SRC-009"])
        self.assertEqual([row["window"] for row in validation["rows"]], ["T+5", "T+20", "T+60"])
        self.assertEqual(validation["rows"][1]["label"], "validated")
        self.assertEqual(validation["rows"][1]["future_source_ids"], ["SRC-009"])

    def test_load_case_index_rejects_malformed_cases_shape(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case_index.json"
            path.write_text(json.dumps({"default_case_id": "EVT-BAD", "cases": {"case_id": "EVT-BAD"}}))

            with self.assertRaisesRegex(ValueError, "cases must be a list"):
                load_case_index(path)

    def test_replay_rejects_market_snapshot_after_event_lock(self):
        fixture = {
            "event": {
                "event_id": "EVT-LOCK-TEST",
                "ticker": "LOCK",
                "company_name": "Lock Test Co",
                "event_date": "2025-08-07",
                "event_timestamp": "2025-08-07T10:00:00-04:00",
                "event_type": "earnings",
                "case_id": "EVT-LOCK-TEST",
            },
            "market_snapshot": {
                "event_bar": {
                    "symbol": "LOCK",
                    "open": 100,
                    "close": 90,
                    "timestamp": "2025-08-07T10:01:00-04:00",
                }
            },
            "narratives": [],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "future_market_fixture.json"
            path.write_text(json.dumps(fixture))

            with self.assertRaisesRegex(ValueError, "LOCK market bar timestamp .* after replay timestamp"):
                run_replay(path)


if __name__ == "__main__":
    unittest.main()
