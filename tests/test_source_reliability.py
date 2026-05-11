import unittest
from pathlib import Path

from narrativedesk.pipeline import ledger_export, run_replay
from narrativedesk.source_reliability import compute_source_reliability

ROOT = Path(__file__).resolve().parents[1]
ORION_EVENT = ROOT / "data" / "fixtures" / "synthetic_event.json"
AURORA_EVENT = ROOT / "data" / "fixtures" / "synthetic_event_aurora.json"
LYRA_EVENT = ROOT / "data" / "fixtures" / "synthetic_event_lyra.json"


def bucket_by_key(buckets):
    return {bucket.key: bucket for bucket in buckets}


class SourceReliabilityTests(unittest.TestCase):
    def test_orion_reliability_summarizes_allowed_and_blocked_sources(self):
        _event, narratives, audit, _validation = run_replay(ORION_EVENT)
        artifact = compute_source_reliability(narratives, audit)

        self.assertEqual(artifact.overall.allowed_source_count, 8)
        self.assertEqual(artifact.overall.blocked_future_count, 1)
        self.assertEqual(artifact.overall.low_quality_source_count, 1)
        self.assertEqual(artifact.overall.blocked_future_source_ids, ["SRC-009"])
        self.assertAlmostEqual(artifact.overall.average_evidence_quality, 0.7975)
        self.assertAlmostEqual(artifact.overall.average_independence, 0.8213)
        self.assertAlmostEqual(artifact.overall.average_originality_score, 0.5)

        publishers = bucket_by_key(artifact.by_publisher)
        self.assertEqual(publishers["Orion Streaming Holdings"].allowed_source_count, 5)
        self.assertEqual(publishers["Orion Streaming Holdings"].blocked_future_count, 0)
        self.assertAlmostEqual(
            publishers["Orion Streaming Holdings"].average_evidence_quality,
            0.84,
        )
        self.assertAlmostEqual(publishers["Orion Streaming Holdings"].average_independence, 0.878)
        self.assertEqual(publishers["unknown"].allowed_source_count, 0)
        self.assertEqual(publishers["unknown"].blocked_future_count, 1)
        self.assertIsNone(publishers["unknown"].average_evidence_quality)
        self.assertEqual(
            publishers["unknown"].blocked_future_source_ids,
            ["SRC-009"],
        )
        self.assertEqual(publishers["Synthetic Market News"].low_quality_source_count, 1)

        source_types = bucket_by_key(artifact.by_source_type)
        self.assertEqual(source_types["earnings_transcript"].source_ids, ["SRC-002"])
        self.assertEqual(source_types["analyst_revision"].blocked_future_count, 1)

    def test_aurora_reliability_uses_explicit_originality_scores(self):
        _event, narratives, audit, _validation = run_replay(AURORA_EVENT)
        artifact = compute_source_reliability(narratives, audit)

        self.assertEqual(artifact.overall.allowed_source_count, 8)
        self.assertEqual(artifact.overall.blocked_future_count, 1)
        self.assertEqual(artifact.overall.low_quality_source_count, 1)
        self.assertAlmostEqual(artifact.overall.average_originality_score, 0.6)
        self.assertEqual(artifact.overall.blocked_future_source_ids, ["AUR-SRC-009"])

        publishers = bucket_by_key(artifact.by_publisher)
        self.assertEqual(publishers["Aurora Commerce Cloud"].allowed_source_count, 5)
        self.assertAlmostEqual(publishers["Aurora Commerce Cloud"].average_originality_score, 0.6)

    def test_lyra_reliability_summarizes_hard_case_sources(self):
        _event, narratives, audit, _validation = run_replay(LYRA_EVENT)
        artifact = compute_source_reliability(narratives, audit)

        self.assertEqual(artifact.overall.allowed_source_count, 8)
        self.assertEqual(artifact.overall.blocked_future_count, 1)
        self.assertEqual(artifact.overall.low_quality_source_count, 0)
        self.assertEqual(artifact.overall.blocked_future_source_ids, ["LYR-SRC-009"])
        self.assertAlmostEqual(artifact.overall.average_evidence_quality, 0.8175)
        self.assertAlmostEqual(artifact.overall.average_originality_score, 0.675)

        publishers = bucket_by_key(artifact.by_publisher)
        self.assertEqual(publishers["Lyra Security Systems"].allowed_source_count, 5)
        self.assertEqual(publishers["unknown"].blocked_future_count, 1)
        self.assertEqual(publishers["Synthetic Market News"].low_quality_source_count, 0)

    def test_ledger_export_includes_source_reliability_artifact(self):
        event, narratives, audit, _validation = run_replay(ORION_EVENT)
        ledger = ledger_export(event, narratives, audit)

        self.assertIn("source_reliability", ledger)
        self.assertEqual(ledger["source_reliability"]["overall"]["allowed_source_count"], 8)
        self.assertEqual(ledger["source_reliability"]["overall"]["blocked_future_count"], 1)
        self.assertIn("by_publisher", ledger["source_reliability"])
        self.assertIn("by_source_type", ledger["source_reliability"])


if __name__ == "__main__":
    unittest.main()
