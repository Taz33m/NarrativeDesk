import unittest
from datetime import datetime

from narrativedesk.models import EvidenceItem, Narrative, ScoreInputs
from narrativedesk.replay import filter_narratives_for_replay, is_source_allowed, split_evidence_for_replay


class ReplayTests(unittest.TestCase):
    def test_sources_after_replay_timestamp_are_blocked(self):
        replay_timestamp = datetime.fromisoformat("2025-08-07T10:00:00-04:00")
        before = EvidenceItem(
            source_id="SRC-BEFORE",
            claim="Allowed claim.",
            published_at=datetime.fromisoformat("2025-08-07T09:59:00-04:00"),
            source_type="news",
            relation="support",
        )
        after = EvidenceItem(
            source_id="SRC-AFTER",
            claim="Future claim.",
            published_at=datetime.fromisoformat("2025-08-07T10:01:00-04:00"),
            source_type="news",
            relation="support",
        )

        self.assertTrue(is_source_allowed(before, replay_timestamp))
        self.assertFalse(is_source_allowed(after, replay_timestamp))

        allowed, blocked = split_evidence_for_replay([before, after], replay_timestamp)
        self.assertEqual([item.source_id for item in allowed], ["SRC-BEFORE"])
        self.assertEqual([item.source_id for item in blocked], ["SRC-AFTER"])

    def test_explicit_blocked_future_status_is_blocked_even_before_lock(self):
        replay_timestamp = datetime.fromisoformat("2025-08-07T10:00:00-04:00")
        future_only = EvidenceItem(
            source_id="SRC-MARKED-FUTURE",
            claim="Validation-only estimate revision.",
            published_at=datetime.fromisoformat("2025-08-07T09:59:00-04:00"),
            source_type="estimate_revision",
            relation="support",
            availability_status="blocked_future",
        )
        narrative = Narrative(
            narrative_id="NARR-LOCK",
            event_id="EVT-LOCK",
            ticker="LOCK",
            timestamp_created=replay_timestamp,
            title="Future-only support",
            narrative="Future-only support should not score.",
            mechanism="Explicit source status gates replay availability.",
            directional_implication="bearish",
            time_horizon="20 trading days",
            expected_observables=[],
            scoring_inputs=ScoreInputs.from_dict({}),
            supporting_evidence=[future_only],
        )

        self.assertFalse(is_source_allowed(future_only, replay_timestamp))

        filtered, audit = filter_narratives_for_replay([narrative], replay_timestamp)

        self.assertEqual(filtered[0].supporting_evidence, [])
        self.assertEqual(audit.blocked_source_ids, ["SRC-MARKED-FUTURE"])
        self.assertEqual(audit.blocked_evidence[0]["blocked_reason"], "marked_blocked_future")

    def test_naive_replay_timestamps_fail(self):
        evidence = EvidenceItem(
            source_id="SRC-NAIVE",
            claim="Naive claim.",
            published_at=datetime.fromisoformat("2025-08-07T09:59:00"),
            source_type="news",
            relation="support",
        )

        with self.assertRaisesRegex(ValueError, "replay timestamp must include a timezone offset"):
            is_source_allowed(evidence, "2025-08-07T10:00:00")

        with self.assertRaisesRegex(ValueError, "SRC-NAIVE published_at must include a timezone offset"):
            is_source_allowed(evidence, "2025-08-07T10:00:00-04:00")


if __name__ == "__main__":
    unittest.main()
