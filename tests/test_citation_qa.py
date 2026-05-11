import unittest
from pathlib import Path

from narrativedesk.citation_qa import run_citation_qa
from narrativedesk.pipeline import ledger_export, run_replay

ROOT = Path(__file__).resolve().parents[1]
ORION_EVENT = ROOT / "data" / "fixtures" / "synthetic_event.json"
AURORA_EVENT = ROOT / "data" / "fixtures" / "synthetic_event_aurora.json"
LYRA_EVENT = ROOT / "data" / "fixtures" / "synthetic_event_lyra.json"


class CitationQaTests(unittest.TestCase):
    def test_orion_citation_qa_flags_synthetic_provenance_gaps(self):
        _event, narratives, audit, _validation = run_replay(ORION_EVENT)
        summary = run_citation_qa(narratives, audit)

        self.assertTrue(summary.replay_filter_pass)
        self.assertTrue(summary.support_coverage_pass)
        self.assertTrue(summary.event_time_integrity_pass)
        self.assertFalse(summary.citation_qa_pass)
        self.assertFalse(summary.provenance_ready)
        self.assertEqual(summary.returned_blocked_source_count, 0)
        self.assertEqual(summary.allowed_source_count, 8)
        self.assertEqual(summary.blocked_future_source_count, 1)
        self.assertEqual(summary.narratives_with_support_count, 4)
        self.assertEqual(summary.missing_url_count, 8)
        self.assertEqual(summary.missing_content_hash_count, 8)
        self.assertEqual(summary.low_quality_evidence_count, 1)

    def test_aurora_citation_qa_has_placeholder_provenance(self):
        _event, narratives, audit, _validation = run_replay(AURORA_EVENT)
        summary = run_citation_qa(narratives, audit)

        self.assertTrue(summary.replay_filter_pass)
        self.assertTrue(summary.support_coverage_pass)
        self.assertTrue(summary.event_time_integrity_pass)
        self.assertTrue(summary.provenance_ready)
        self.assertTrue(summary.citation_qa_pass)
        self.assertEqual(summary.allowed_source_count, 8)
        self.assertEqual(summary.missing_url_count, 0)
        self.assertEqual(summary.missing_content_hash_count, 0)

    def test_lyra_citation_qa_hard_case_is_provenance_ready(self):
        _event, narratives, audit, _validation = run_replay(LYRA_EVENT)
        summary = run_citation_qa(narratives, audit)

        self.assertTrue(summary.replay_filter_pass)
        self.assertTrue(summary.support_coverage_pass)
        self.assertTrue(summary.event_time_integrity_pass)
        self.assertTrue(summary.provenance_ready)
        self.assertTrue(summary.citation_qa_pass)
        self.assertEqual(summary.allowed_source_count, 8)
        self.assertEqual(summary.blocked_future_source_count, 1)
        self.assertEqual(summary.returned_blocked_source_count, 0)
        self.assertEqual(summary.missing_url_count, 0)
        self.assertEqual(summary.missing_content_hash_count, 0)
        self.assertEqual(summary.low_quality_evidence_count, 0)

    def test_ledger_export_includes_citation_qa(self):
        event, narratives, audit, _validation = run_replay(ORION_EVENT)
        ledger = ledger_export(event, narratives, audit)

        self.assertIn("citation_qa", ledger)
        self.assertTrue(ledger["citation_qa"]["replay_filter_pass"])
        self.assertEqual(ledger["citation_qa"]["blocked_future_source_count"], 1)


if __name__ == "__main__":
    unittest.main()
