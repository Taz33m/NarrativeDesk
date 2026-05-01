import unittest
from datetime import datetime

from narrativedesk.models import EvidenceItem
from narrativedesk.replay import is_source_allowed, split_evidence_for_replay


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


if __name__ == "__main__":
    unittest.main()
