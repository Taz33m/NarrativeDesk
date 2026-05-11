import json
import unittest
from pathlib import Path

from narrativedesk.pipeline import run_replay

ROOT = Path(__file__).resolve().parents[1]


class CaseFixtureTests(unittest.TestCase):
    def test_case_index_has_multiple_cases(self):
        payload = json.loads((ROOT / 'data/fixtures/case_index.json').read_text())
        self.assertGreaterEqual(len(payload['cases']), 3)
        self.assertEqual(payload['default_case_id'], 'EVT-ORION-2025-08-07')

    def test_source_provenance_fields_present(self):
        fixture = json.loads((ROOT / 'data/fixtures/synthetic_event_aurora.json').read_text())
        source = fixture['narratives'][0]['supporting_evidence'][0]
        required = [
            'source_id', 'source_type', 'publisher', 'title', 'url', 'published_at', 'retrieved_at',
            'content_hash', 'availability_status', 'originality_score', 'independence_cluster_id',
            'claim_extracted', 'supported_narrative_ids', 'contradicted_narrative_ids',
        ]
        for key in required:
            self.assertIn(key, source)

    def test_aurora_case_is_distinct_and_timestamp_locked(self):
        event, narratives, audit, _validation = run_replay(
            ROOT / 'data/fixtures/synthetic_event_aurora.json'
        )

        self.assertEqual(event.ticker, 'AURORA')
        self.assertEqual(event.case_id, 'EVT-AURORA-2025-10-22')
        self.assertEqual(event.daily_return, -0.097)
        self.assertEqual(event.peer_median_return, -0.013)
        self.assertEqual(event.abnormal_return, -0.084)
        self.assertEqual(event.volume_ratio, 2.1)
        self.assertEqual(audit.blocked_source_ids, ['AUR-SRC-009'])
        self.assertEqual(audit.removed_evidence_by_narrative, {'AUR-NARR-001': ['AUR-SRC-009']})

        returned_sources = [
            evidence.source_id
            for narrative in narratives
            for evidence in narrative.all_evidence()
        ]
        self.assertNotIn('AUR-SRC-009', returned_sources)

        serialized_claims = json.dumps(
            [evidence.to_dict() for narrative in narratives for evidence in narrative.all_evidence()]
        )
        self.assertNotIn('Orion', serialized_claims)
        self.assertIn('merchant', serialized_claims)

    def test_lyra_hard_case_has_validated_non_top_narrative(self):
        event, narratives, audit, _validation = run_replay(
            ROOT / 'data/fixtures/synthetic_event_lyra.json'
        )

        self.assertEqual(event.ticker, 'LYRA')
        self.assertEqual(event.case_id, 'EVT-LYRA-2025-11-13')
        self.assertEqual(event.daily_return, -0.082)
        self.assertEqual(event.peer_median_return, -0.017)
        self.assertEqual(event.abnormal_return, -0.065)
        self.assertEqual(event.volume_ratio, 2.25)
        self.assertEqual(audit.blocked_source_ids, ['LYR-SRC-009'])
        self.assertEqual(audit.removed_evidence_by_narrative, {'LYR-NARR-002': ['LYR-SRC-009']})
        self.assertEqual([narrative.narrative_id for narrative in narratives[:2]], ['LYR-NARR-001', 'LYR-NARR-002'])

        returned_sources = [
            evidence.source_id
            for narrative in narratives
            for evidence in narrative.all_evidence()
        ]
        self.assertNotIn('LYR-SRC-009', returned_sources)

        serialized_claims = json.dumps(
            [evidence.to_dict() for narrative in narratives for evidence in narrative.all_evidence()]
        )
        self.assertIn('renewal', serialized_claims)
        self.assertNotIn('Future validation fixture', serialized_claims)


if __name__ == '__main__':
    unittest.main()
