import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from narrativedesk.case_index import validate_case_index
from narrativedesk.pipeline import run_replay
from narrativedesk.source_pack import (
    assess_real_case_quality,
    assess_source_pack_readiness,
    build_fixture_from_source_pack,
    build_validation_fixture_template_from_source_pack,
    load_source_pack,
    preview_source_pack,
    sanitize_source_record,
    source_content_hash,
    validate_source_pack,
)

ROOT = Path(__file__).resolve().parents[1]


def _score_inputs():
    return {
        "evidence_strength": 0.7,
        "mechanism_specificity": 0.7,
        "source_independence": 0.7,
        "cross_sectional_fit": 0.6,
        "contradiction_resistance": 0.6,
        "timestamp_advantage": 0.8,
        "forward_observable_quality": 0.7,
        "crowding_risk": 0.3,
        "unsupported_claim_penalty": 0.05,
    }


def _source(
    source_id,
    claim,
    published_at,
    status,
    supported=None,
    contradicted=None,
    *,
    publisher="Example Publisher",
    source_type="company_release",
    cluster_id="cluster-1",
):
    return {
        "source_id": source_id,
        "source_type": source_type,
        "publisher": publisher,
        "title": f"{source_id} title",
        "url": f"https://example.com/source-pack/{source_id.lower()}",
        "published_at": published_at,
        "retrieved_at": "2026-05-01T00:00:00Z",
        "content_hash": source_content_hash(claim),
        "availability_status": status,
        "originality_score": 0.7,
        "independence_cluster_id": cluster_id,
        "claim_extracted": claim,
        "supported_narrative_ids": supported or [],
        "contradicted_narrative_ids": contradicted or [],
        "support_strength": 0.7,
        "evidence_quality": 0.8,
        "independence": 0.75,
        "incentive_conflict": 0.1,
    }


def _ingest_pack():
    return {
        "case_metadata": {
            "case_id": "EVT-PACK-2025-01-02",
            "ticker": "PACK",
            "company_name": "Packaged Example Co",
            "event_timestamp": "2025-01-02T10:00:00-05:00",
            "data_provenance_mode": "real-curated",
        },
        "event": {
            "event_type": "earnings/guidance",
            "event_summary": "Curated replay scaffold for ingestion tests.",
        },
        "market_snapshot": {
            "event_bar": {
                "symbol": "PACK",
                "open": 100.0,
                "close": 94.0,
                "volume": 200,
                "average_volume": 100,
                "timestamp": "2025-01-02T10:00:00-05:00",
            },
            "peer_bars": [
                {"symbol": "PEER-A", "open": 100.0, "close": 98.0, "timestamp": "2025-01-02T10:00:00-05:00"},
                {"symbol": "PEER-B", "open": 100.0, "close": 99.0, "timestamp": "2025-01-02T10:00:00-05:00"},
                {"symbol": "PEER-C", "open": 100.0, "close": 97.0, "timestamp": "2025-01-02T10:00:00-05:00"},
            ],
            "sector_bar": {"symbol": "SECTOR", "open": 100.0, "close": 99.5, "as_of": "2025-01-02T10:00:00-05:00"},
        },
        "sources": [
            _source(
                "PK-SRC-001",
                "Management lowered near-term expansion guidance.",
                "2025-01-02T08:00:00-05:00",
                "allowed",
                supported=["PK-NARR-001"],
            ),
            _source(
                "PK-SRC-002",
                "Reported current-quarter revenue exceeded consensus.",
                "2025-01-02T08:00:00-05:00",
                "allowed",
                contradicted=["PK-NARR-001"],
            ),
            _source(
                "PK-SRC-003",
                "Full-year free cash flow guidance was maintained.",
                "2025-01-02T08:00:00-05:00",
                "allowed",
                supported=["PK-NARR-002"],
            ),
            _source(
                "PK-SRC-009",
                "Future analyst revisions later reduced expansion estimates.",
                "2025-01-09T08:00:00-05:00",
                "blocked_future",
                supported=["PK-NARR-001"],
            ),
        ],
        "narratives": [
            {
                "narrative_id": "PK-NARR-001",
                "title": "Forward expansion slowdown",
                "narrative": "The move reflects concern that forward expansion is slowing.",
                "mechanism": "Lower expansion assumptions would reduce forward revenue estimates.",
                "directional_implication": "bearish",
                "time_horizon": "20 trading days",
                "expected_observables": ["Analysts reduce expansion estimates within 30 days"],
                "scoring_inputs": _score_inputs(),
            },
            {
                "narrative_id": "PK-NARR-002",
                "title": "Overreaction to conservative guide",
                "narrative": "The market may be overreacting to conservative guidance.",
                "mechanism": "If guidance is conservative, estimates could stabilize.",
                "directional_implication": "bullish",
                "time_horizon": "20 trading days",
                "expected_observables": ["Revenue estimates stabilize after the first revision wave"],
                "scoring_inputs": {**_score_inputs(), "evidence_strength": 0.55},
            },
        ],
    }


def _quality_ready_pack():
    payload = _ingest_pack()
    payload["sources"].extend(
        [
            _source(
                "PK-SRC-004",
                "Customer expansion commentary remained a separate plausible explanation.",
                "2025-01-02T08:10:00-05:00",
                "allowed",
                supported=["PK-NARR-003"],
            ),
            _source(
                "PK-SRC-005",
                "Peer shares did not fall enough to explain the full company-specific move.",
                "2025-01-02T08:15:00-05:00",
                "allowed",
                supported=["PK-NARR-001", "PK-NARR-002"],
            ),
        ]
    )
    payload["narratives"].append(
        {
            "narrative_id": "PK-NARR-003",
            "title": "Company-specific demand reset",
            "narrative": "The move reflects a company-specific reset in forward demand assumptions.",
            "mechanism": "Company-specific demand pressure would reduce forward estimates more than peer beta.",
            "directional_implication": "bearish",
            "time_horizon": "20 trading days",
            "expected_observables": ["Company estimate cuts exceed peer estimate cuts"],
            "scoring_inputs": {**_score_inputs(), "evidence_strength": 0.62},
        }
    )
    return payload


def _demo_ready_pack():
    payload = _quality_ready_pack()
    source_overrides = {
        "PK-SRC-001": {"publisher": "Packaged Example IR", "source_type": "company_release"},
        "PK-SRC-002": {"publisher": "Event Transcript Co", "source_type": "transcript"},
        "PK-SRC-003": {"publisher": "SEC EDGAR", "source_type": "filing"},
        "PK-SRC-004": {"publisher": "Research Wire", "source_type": "news"},
        "PK-SRC-005": {"publisher": "Exchange Data", "source_type": "market_data"},
    }
    for source in payload["sources"]:
        if source["source_id"] in source_overrides:
            source.update(source_overrides[source["source_id"]])
    return payload


def _validated_fixture():
    return {
        "event_id": "EVT-PACK-2025-01-02",
        "status": "complete",
        "future_source_ids": ["PK-SRC-009"],
        "future_source_count": 1,
        "rows": [
            {
                "window": "T+20",
                "label": "validated",
                "narrative_id": "PK-NARR-001",
                "expected_observable": "Analysts reduce expansion estimates within 30 days",
                "future_source_ids": ["PK-SRC-009"],
                "what_happened": "Future validation source confirmed the selected narrative.",
            }
        ],
    }


class SourcePackTests(unittest.TestCase):
    def test_template_validates(self):
        payload = load_source_pack(ROOT / 'examples' / 'source_pack_template.json')
        self.assertEqual(validate_source_pack(payload), [])

    def test_preview_counts(self):
        payload = load_source_pack(ROOT / 'examples' / 'source_pack_template.json')
        preview = preview_source_pack(payload)
        self.assertEqual(preview['case_id'], 'EVT-EXAMPLE-2025-01-02')
        self.assertEqual(preview['source_counts']['allowed'], 3)
        self.assertEqual(preview['source_counts']['blocked_future'], 1)
        self.assertEqual(preview['narrative_count'], 2)
        self.assertEqual(preview['allowed_source_ids'], ['SRC-001', 'SRC-002', 'SRC-003'])
        self.assertEqual(preview['blocked_future_source_ids'], ['SRC-009'])
        self.assertEqual(
            preview['source_type_counts'],
            {
                'analyst_revision': 1,
                'company_release': 3,
            },
        )

    def test_source_pack_readiness_accepts_template(self):
        payload = load_source_pack(ROOT / 'examples' / 'source_pack_template.json')

        result = assess_source_pack_readiness(payload)

        self.assertTrue(result['ok'])
        self.assertEqual(result['status'], 'ready_to_ingest')
        self.assertTrue(result['checks']['preview_valid']['ok'])
        self.assertTrue(result['checks']['ingestion_ready']['ok'])
        self.assertEqual(result['checks']['replay_safe']['blocked_future_source_ids'], ['SRC-009'])
        self.assertEqual(result['checks']['narrative_linkage']['narratives_without_allowed_support'], [])

    def test_source_pack_readiness_flags_missing_allowed_support(self):
        payload = _ingest_pack()
        payload['sources'][0]['supported_narrative_ids'] = []

        result = assess_source_pack_readiness(payload)

        self.assertFalse(result['ok'])
        self.assertEqual(result['status'], 'needs_attention')
        self.assertTrue(result['checks']['ingestion_ready']['ok'])
        self.assertFalse(result['checks']['narrative_linkage']['ok'])
        self.assertEqual(result['checks']['narrative_linkage']['narratives_without_allowed_support'], ['PK-NARR-001'])

    def test_source_pack_readiness_flags_provenance_gaps(self):
        payload = _ingest_pack()
        payload['sources'][0]['url'] = 'https://...'
        payload['sources'][1]['content_hash'] = 'sha256:...'
        del payload['sources'][2]['retrieved_at']

        result = assess_source_pack_readiness(payload)

        self.assertFalse(result['ok'])
        self.assertEqual(
            result['checks']['provenance_ready']['missing_stable_url_source_ids'],
            ['PK-SRC-001'],
        )
        self.assertEqual(result['checks']['provenance_ready']['missing_hash_source_ids'], ['PK-SRC-002'])
        self.assertEqual(result['checks']['provenance_ready']['missing_retrieved_at_source_ids'], ['PK-SRC-003'])

    def test_real_case_quality_accepts_minimum_quality_pack(self):
        result = assess_real_case_quality(_quality_ready_pack())

        self.assertTrue(result['ok'])
        self.assertEqual(result['status'], 'quality_ready')
        self.assertEqual(result['gate'], 'quality')
        self.assertEqual(result['metrics']['narrative_count'], 3)
        self.assertEqual(result['metrics']['allowed_source_count'], 5)
        self.assertEqual(result['metrics']['blocked_future_source_count'], 1)
        self.assertTrue(result['checks']['contradiction_links']['ok'])

    def test_real_case_quality_accepts_demo_ready_pack(self):
        result = assess_real_case_quality(
            _demo_ready_pack(),
            require_demo_ready=True,
            validation_fixture=_validated_fixture(),
        )

        self.assertTrue(result['ok'])
        self.assertEqual(result['status'], 'demo_ready')
        self.assertEqual(result['gate'], 'demo')
        self.assertTrue(result['checks']['demo_market_context']['ok'])
        self.assertTrue(result['checks']['linked_replay_time_sources']['ok'])
        self.assertEqual(result['metrics']['linked_allowed_source_count'], 5)
        self.assertGreaterEqual(result['metrics']['linked_source_type_count'], 2)
        self.assertGreaterEqual(result['metrics']['linked_publisher_count'], 2)
        self.assertEqual(result['metrics']['validation_outcome_count'], 1)

    def test_real_case_quality_demo_gate_flags_private_rehearsal_gaps(self):
        result = assess_real_case_quality(_quality_ready_pack(), require_demo_ready=True)

        self.assertFalse(result['ok'])
        self.assertEqual(result['status'], 'needs_curation')
        self.assertTrue(result['checks']['demo_market_context']['ok'])
        self.assertTrue(result['checks']['linked_replay_time_sources']['ok'])
        self.assertFalse(result['checks']['source_type_diversity']['ok'])
        self.assertFalse(result['checks']['publisher_diversity']['ok'])
        self.assertFalse(result['checks']['validation_outcomes']['ok'])
        self.assertIn('independently sourced replay-time evidence', result['next_action'])

    def test_real_case_quality_demo_gate_requires_abnormal_move_context(self):
        payload = _demo_ready_pack()
        payload['market_snapshot']['peer_bars'] = []

        result = assess_real_case_quality(
            payload,
            require_demo_ready=True,
            validation_fixture=_validated_fixture(),
        )

        self.assertFalse(result['ok'])
        self.assertEqual(result['status'], 'needs_curation')
        self.assertFalse(result['checks']['demo_market_context']['ok'])
        self.assertIn('abnormal_return is not computable', result['checks']['demo_market_context']['errors'])
        self.assertIn('peer market bars', result['next_action'])

    def test_real_case_quality_flags_rehearsal_that_needs_more_curation(self):
        result = assess_real_case_quality(_ingest_pack())

        self.assertFalse(result['ok'])
        self.assertEqual(result['status'], 'needs_curation')
        self.assertFalse(result['checks']['narrative_count']['ok'])
        self.assertFalse(result['checks']['replay_time_sources']['ok'])
        self.assertIn('Curate 3-5 competing narratives', result['next_action'])

    def test_real_case_quality_prioritizes_missing_market_snapshot(self):
        payload = _ingest_pack()
        del payload['market_snapshot']

        result = assess_real_case_quality(payload)

        self.assertFalse(result['ok'])
        self.assertFalse(result['checks']['market_snapshot']['ok'])
        self.assertFalse(result['checks']['narrative_count']['ok'])
        self.assertIn('market snapshot', result['next_action'])

    def test_missing_fields_fail(self):
        payload = {"case_metadata": {}, "sources": [{}]}
        errors = validate_source_pack(payload)
        self.assertTrue(any('case_metadata.case_id' in err for err in errors))
        self.assertTrue(any('sources[0] missing required fields' in err for err in errors))

    def test_malformed_pack_shapes_return_validation_errors(self):
        payload = {"case_metadata": [], "sources": ["bad"]}
        errors = validate_source_pack(payload, require_narratives=True)

        self.assertIn("case_metadata must be an object", errors)
        self.assertIn("sources[0] must be an object", errors)

    def test_future_allowed_source_fails(self):
        payload = load_source_pack(ROOT / 'examples' / 'source_pack_template.json')
        payload['sources'][0]['published_at'] = '2025-01-03T08:00:00-05:00'

        errors = validate_source_pack(payload)

        self.assertTrue(any('must be blocked_future after event_timestamp' in err for err in errors))

    def test_market_snapshot_without_bar_timestamp_fails(self):
        payload = load_source_pack(ROOT / 'examples' / 'source_pack_template.json')
        del payload['market_snapshot']['event_bar']['timestamp']

        errors = validate_source_pack(payload)

        self.assertTrue(any('market_snapshot invalid: EXMPL market bar must include timestamp or as_of' in err for err in errors))

    def test_blocked_pre_event_source_fails(self):
        payload = load_source_pack(ROOT / 'examples' / 'source_pack_template.json')
        payload['sources'][0]['availability_status'] = 'blocked_future'

        errors = validate_source_pack(payload)

        self.assertTrue(any('cannot be blocked_future before event_timestamp' in err for err in errors))

    def test_naive_timestamps_fail(self):
        payload = load_source_pack(ROOT / 'examples' / 'source_pack_template.json')
        payload['case_metadata']['event_timestamp'] = '2025-01-02T10:00:00'
        payload['sources'][0]['published_at'] = '2025-01-02T08:00:00'
        payload['sources'][0]['retrieved_at'] = '2026-05-01T00:00:00'

        errors = validate_source_pack(payload)

        self.assertTrue(any('case_metadata.event_timestamp must include a timezone offset' in err for err in errors))
        self.assertTrue(any('sources[0].published_at must include a timezone offset' in err for err in errors))
        self.assertTrue(any('sources[0].retrieved_at must include a timezone offset' in err for err in errors))

    def test_duplicate_source_ids_fail(self):
        payload = load_source_pack(ROOT / 'examples' / 'source_pack_template.json')
        payload['sources'].append(dict(payload['sources'][0]))

        errors = validate_source_pack(payload)

        self.assertTrue(any('source_id duplicates SRC-001' in err for err in errors))

    def test_invalid_hash_shape_fails(self):
        payload = load_source_pack(ROOT / 'examples' / 'source_pack_template.json')
        payload['sources'][0]['content_hash'] = 'sha256:...'

        errors = validate_source_pack(payload)

        self.assertTrue(any('content_hash must be sha256' in err for err in errors))

    def test_source_scores_must_be_numbers_from_zero_to_one(self):
        payload = load_source_pack(ROOT / 'examples' / 'source_pack_template.json')
        payload['sources'][0]['originality_score'] = False
        payload['sources'][0]['support_strength'] = '0.5'
        payload['sources'][0]['evidence_quality'] = 1.2
        payload['sources'][0]['independence'] = -0.1
        payload['sources'][0]['incentive_conflict'] = True

        errors = validate_source_pack(payload)

        self.assertTrue(any('sources[0].originality_score must be a number from 0 to 1' in err for err in errors))
        self.assertTrue(any('sources[0].support_strength must be a number from 0 to 1' in err for err in errors))
        self.assertTrue(any('sources[0].evidence_quality must be a number from 0 to 1' in err for err in errors))
        self.assertTrue(any('sources[0].independence must be a number from 0 to 1' in err for err in errors))
        self.assertTrue(any('sources[0].incentive_conflict must be a number from 0 to 1' in err for err in errors))

    def test_real_curated_hash_must_match_claim_text(self):
        payload = _ingest_pack()
        payload['sources'][0]['content_hash'] = source_content_hash('different source text')

        errors = validate_source_pack(payload, require_narratives=True)

        self.assertTrue(any('content_hash does not match claim_extracted' in err for err in errors))

    def test_real_curated_hash_uses_document_text_when_present(self):
        payload = _ingest_pack()
        payload['sources'][0]['document_text'] = 'Longer source document text for archival hashing.'
        payload['sources'][0]['content_hash'] = source_content_hash(payload['sources'][0]['document_text'])

        errors = validate_source_pack(payload, require_narratives=True)

        self.assertEqual(errors, [])

    def test_template_ingests_and_round_trips(self):
        payload = load_source_pack(ROOT / 'examples' / 'source_pack_template.json')
        fixture = build_fixture_from_source_pack(payload)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'fixture.json'
            path.write_text(json.dumps(fixture))

            event, narratives, audit, _validation = run_replay(path)

        self.assertEqual(event.ticker, 'EXMPL')
        self.assertEqual(event.daily_return, -0.06)
        self.assertEqual(audit.blocked_source_ids, ['SRC-009'])
        self.assertEqual(len(narratives), 2)

    def test_source_pack_rejects_unsupported_source_fields(self):
        payload = _ingest_pack()
        payload['sources'][0]['api_key'] = 'secret-value'
        payload['sources'][1]['curator_note'] = 'private note'

        errors = validate_source_pack(payload, require_narratives=True)

        self.assertTrue(any('secret-like unsupported fields: api_key' in err for err in errors))
        self.assertTrue(any('unsupported public fields: curator_note' in err for err in errors))

    def test_source_record_sanitizer_drops_internal_fields(self):
        payload = _ingest_pack()
        source = payload['sources'][0]
        source['document_text'] = 'Longer source document.'
        source['content_hash'] = source_content_hash(source['document_text'])
        source['provider'] = 'sec'
        source['raw_artifact_path'] = '/tmp/private-source.json'

        evidence = sanitize_source_record(source)

        self.assertIn('document_text', evidence)
        self.assertEqual(evidence['claim_extracted'], 'Management lowered near-term expansion guidance.')
        self.assertNotIn('provider', evidence)
        self.assertNotIn('raw_artifact_path', evidence)

    def test_ingest_builds_event_fixture_shape(self):
        fixture = build_fixture_from_source_pack(_ingest_pack())

        self.assertEqual(fixture['event']['event_id'], 'EVT-PACK-2025-01-02')
        self.assertEqual(fixture['event']['event_date'], '2025-01-02')
        self.assertEqual(fixture['event']['data_provenance_mode'], 'real-curated')
        self.assertEqual(len(fixture['narratives']), 2)
        self.assertIn('market_snapshot', fixture)

    def test_ingest_builds_separate_pending_validation_scaffold(self):
        validation = build_validation_fixture_template_from_source_pack(_ingest_pack())

        self.assertEqual(validation['event_id'], 'EVT-PACK-2025-01-02')
        self.assertEqual(validation['status'], 'pending')
        self.assertEqual(validation['future_source_ids'], ['PK-SRC-009'])
        self.assertEqual(validation['future_source_count'], 1)
        self.assertEqual(len(validation['rows']), 2)
        self.assertEqual(validation['rows'][0]['label'], 'pending')
        self.assertEqual(validation['rows'][0]['window'], 'T+20')
        self.assertEqual(validation['rows'][0]['narrative_id'], 'PK-NARR-001')
        self.assertEqual(validation['rows'][0]['future_source_ids'], ['PK-SRC-009'])
        self.assertEqual(validation['rows'][1]['future_source_ids'], [])
        self.assertIn('separate from event-time replay evidence', validation['note'])

    def test_ingest_validation_scaffold_uses_event_id_override(self):
        payload = _ingest_pack()
        payload['event']['event_id'] = 'EVT-PACK-OVERRIDE'

        fixture = build_fixture_from_source_pack(payload)
        validation = build_validation_fixture_template_from_source_pack(payload)

        self.assertEqual(fixture['event']['event_id'], 'EVT-PACK-OVERRIDE')
        self.assertEqual(validation['event_id'], 'EVT-PACK-OVERRIDE')
        self.assertEqual(fixture['event']['case_id'], 'EVT-PACK-2025-01-02')

    def test_ingest_wires_sources_to_support_and_contradict_lists(self):
        fixture = build_fixture_from_source_pack(_ingest_pack())
        first = fixture['narratives'][0]

        self.assertEqual(
            [item['source_id'] for item in first['supporting_evidence']],
            ['PK-SRC-001', 'PK-SRC-009'],
        )
        self.assertEqual(
            [item['source_id'] for item in first['contradicting_evidence']],
            ['PK-SRC-002'],
        )
        self.assertEqual(first['supporting_evidence'][0]['claim'], 'Management lowered near-term expansion guidance.')

    def test_ingest_round_trips_through_run_replay_and_blocks_future_sources(self):
        fixture = build_fixture_from_source_pack(_ingest_pack())
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'fixture.json'
            path.write_text(json.dumps(fixture))

            event, narratives, audit, _validation = run_replay(path)

        self.assertEqual(event.ticker, 'PACK')
        self.assertEqual(event.daily_return, -0.06)
        self.assertEqual(event.abnormal_return, -0.04)
        self.assertEqual(audit.blocked_source_ids, ['PK-SRC-009'])
        returned_sources = [
            evidence.source_id
            for narrative in narratives
            for evidence in narrative.all_evidence()
        ]
        self.assertNotIn('PK-SRC-009', returned_sources)

    def test_ingest_rejects_unknown_narrative_reference(self):
        payload = _ingest_pack()
        payload['sources'][0]['supported_narrative_ids'] = ['MISSING']

        errors = validate_source_pack(payload, require_narratives=True)

        self.assertTrue(any('references unknown narrative IDs: MISSING' in err for err in errors))

    def test_ingest_rejects_linked_unavailable_sources(self):
        payload = _ingest_pack()
        payload['sources'][0]['availability_status'] = 'unavailable'

        errors = validate_source_pack(payload, require_narratives=True)

        self.assertTrue(any('supported_narrative_ids cannot link unavailable sources' in err for err in errors))

    def test_ingest_rejects_linked_placeholder_sources(self):
        payload = _ingest_pack()
        payload['sources'][1]['availability_status'] = 'placeholder'

        errors = validate_source_pack(payload, require_narratives=True)

        self.assertTrue(any('contradicted_narrative_ids cannot link placeholder sources' in err for err in errors))

    def test_ingest_rejects_duplicate_narrative_ids(self):
        payload = _ingest_pack()
        payload['narratives'][1]['narrative_id'] = 'PK-NARR-001'

        errors = validate_source_pack(payload, require_narratives=True)

        self.assertTrue(any('narrative_id duplicates PK-NARR-001' in err for err in errors))

    def test_ingest_rejects_validation_rows_in_source_pack(self):
        payload = _ingest_pack()
        payload['validation_rows'] = []

        errors = validate_source_pack(payload, require_narratives=True)

        self.assertTrue(any('validation_rows must stay in a separate validation fixture' in err for err in errors))

    def test_preview_rejects_validation_rows_in_source_pack(self):
        payload = _ingest_pack()
        payload['validation_rows'] = []

        errors = validate_source_pack(payload)

        self.assertTrue(any('validation_rows must stay in a separate validation fixture' in err for err in errors))

    def test_ingest_rejects_missing_scoring_input_key(self):
        payload = _ingest_pack()
        del payload['narratives'][0]['scoring_inputs']['evidence_strength']

        errors = validate_source_pack(payload, require_narratives=True)

        self.assertTrue(any('scoring_inputs missing required fields: evidence_strength' in err for err in errors))

    def test_ingest_rejects_bool_scoring_input(self):
        payload = _ingest_pack()
        payload['narratives'][0]['scoring_inputs']['evidence_strength'] = True

        errors = validate_source_pack(payload, require_narratives=True)

        self.assertTrue(
            any('scoring_inputs.evidence_strength must be a number from 0 to 1' in err for err in errors)
        )

    def test_cli_source_pack_ingest_writes_sorted_fixture_json(self):
        payload = _ingest_pack()
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / 'source_pack.json'
            output_path = Path(tmpdir) / 'fixture.json'
            validation_path = Path(tmpdir) / 'validation.json'
            source_path.write_text(json.dumps(payload))

            result = subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'narrativedesk.cli',
                    'source-pack-ingest',
                    str(source_path),
                    '--out',
                    str(output_path),
                    '--validation-out',
                    str(validation_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            response = json.loads(result.stdout)
            fixture = json.loads(output_path.read_text())
            validation = json.loads(validation_path.read_text())

        self.assertTrue(response['ok'])
        self.assertEqual(response['case_id'], 'EVT-PACK-2025-01-02')
        self.assertEqual(response['narrative_count'], 2)
        self.assertEqual(response['source_count'], 4)
        self.assertEqual(response['validation_row_count'], 2)
        self.assertEqual(response['validation_future_source_count'], 1)
        self.assertEqual(fixture['narratives'][0]['narrative_id'], 'PK-NARR-001')
        self.assertNotIn('validation', fixture)
        self.assertEqual(validation['future_source_ids'], ['PK-SRC-009'])
        self.assertEqual(validation['rows'][1]['narrative_id'], 'PK-NARR-002')

    def test_cli_source_pack_readiness_reports_ready_status(self):
        result = subprocess.run(
            [
                sys.executable,
                '-m',
                'narrativedesk.cli',
                'source-pack-readiness',
                str(ROOT / 'examples' / 'source_pack_template.json'),
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        response = json.loads(result.stdout)
        self.assertTrue(response['ok'])
        self.assertEqual(response['status'], 'ready_to_ingest')

    def test_cli_real_case_quality_reports_quality_ready_source_pack(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_pack_path = Path(tmpdir) / 'quality_pack.json'
            source_pack_path.write_text(json.dumps(_quality_ready_pack(), indent=2))
            result = subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'narrativedesk.cli',
                    'real-case-quality',
                    '--source-pack',
                    str(source_pack_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        response = json.loads(result.stdout)
        self.assertTrue(response['ok'])
        self.assertEqual(response['status'], 'quality_ready')

    def test_cli_real_case_quality_demo_gate_is_stricter_than_quality_gate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_pack_path = Path(tmpdir) / 'quality_pack.json'
            source_pack_path.write_text(json.dumps(_quality_ready_pack(), indent=2))
            result = subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'narrativedesk.cli',
                    'real-case-quality',
                    '--source-pack',
                    str(source_pack_path),
                    '--require-demo-ready',
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )

        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        response = json.loads(result.stdout)
        self.assertFalse(response['ok'])
        self.assertEqual(response['gate'], 'demo')
        self.assertEqual(response['status'], 'needs_curation')
        self.assertFalse(response['checks']['source_type_diversity']['ok'])
        self.assertFalse(response['checks']['validation_outcomes']['ok'])

    def test_cli_real_case_quality_checks_bundle_verification(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_pack_path = Path(tmpdir) / 'source_pack.json'
            bundle_dir = Path(tmpdir) / 'bundle'
            source_pack_path.write_text(json.dumps(_ingest_pack(), indent=2))
            bundle_result = subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'narrativedesk.cli',
                    'source-pack-bundle',
                    str(source_pack_path),
                    '--out-dir',
                    str(bundle_dir),
                    '--label',
                    'PACK bundled example',
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            quality_result = subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'narrativedesk.cli',
                    'real-case-quality',
                    '--bundle-dir',
                    str(bundle_dir),
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )

        self.assertEqual(bundle_result.returncode, 0, bundle_result.stderr + bundle_result.stdout)
        self.assertEqual(quality_result.returncode, 1, quality_result.stderr + quality_result.stdout)
        response = json.loads(quality_result.stdout)
        self.assertFalse(response['ok'])
        self.assertTrue(response['checks']['bundle_verified']['ok'])
        self.assertFalse(response['checks']['narrative_count']['ok'])

    def test_cli_source_pack_bundle_writes_self_contained_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / 'bundle'
            result = subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'narrativedesk.cli',
                    'source-pack-bundle',
                    str(ROOT / 'examples' / 'source_pack_template.json'),
                    '--out-dir',
                    str(out_dir),
                    '--label',
                    'EXMPL bundled example',
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            response = json.loads(result.stdout)
            case_index = json.loads((out_dir / 'case_index.json').read_text())
            manifest = json.loads((out_dir / 'manifest.json').read_text())
            case_index_check = validate_case_index(out_dir / 'case_index.json')
            event, narratives, audit, _validation = run_replay(out_dir / 'event_fixture.json')
            bundle_files_exist = {
                'source_pack': (out_dir / 'source_pack.json').exists(),
                'readiness': (out_dir / 'readiness.json').exists(),
                'validation': (out_dir / 'validation_fixture.json').exists(),
                'ledger': (out_dir / 'ledger.json').exists(),
                'report': (out_dir / 'report.md').exists(),
                'manifest': (out_dir / 'manifest.json').exists(),
            }

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(response['ok'])
        self.assertEqual(response['case_id'], 'EVT-EXAMPLE-2025-01-02')
        self.assertEqual(
            bundle_files_exist,
            {
                'source_pack': True,
                'readiness': True,
                'validation': True,
                'ledger': True,
                'report': True,
                'manifest': True,
            },
        )
        self.assertEqual(response['manifest_out'], str(out_dir / 'manifest.json'))
        self.assertEqual(case_index['cases'][0]['event_fixture'], 'event_fixture.json')
        self.assertEqual(case_index['cases'][0]['validation_fixture'], 'validation_fixture.json')
        self.assertEqual(case_index['cases'][0]['label'], 'EXMPL bundled example')
        self.assertEqual(manifest['case_id'], 'EVT-EXAMPLE-2025-01-02')
        self.assertEqual(manifest['replay_integrity']['blocked_future_source_ids'], ['SRC-009'])
        self.assertEqual(manifest['replay_integrity']['validation_future_source_ids'], ['SRC-009'])
        self.assertEqual(
            [artifact['path'] for artifact in manifest['artifacts']],
            [
                'source_pack.json',
                'readiness.json',
                'event_fixture.json',
                'validation_fixture.json',
                'ledger.json',
                'report.md',
                'case_index.json',
            ],
        )
        self.assertTrue(case_index_check['ok'], case_index_check['errors'])
        self.assertEqual(event.ticker, 'EXMPL')
        self.assertEqual(len(narratives), 2)
        self.assertEqual(audit.blocked_source_ids, ['SRC-009'])

    def test_cli_source_pack_bundle_accepts_curated_validation_fixture(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            out_dir = tmp_path / 'bundle'
            payload = load_source_pack(ROOT / 'examples' / 'source_pack_template.json')
            validation_fixture = build_validation_fixture_template_from_source_pack(payload)
            validation_fixture['status'] = 'validated'
            validation_fixture['rows'][0]['label'] = 'validated'
            validation_fixture['rows'][0]['what_happened'] = (
                'Held-out future source supported the observable after replay lock.'
            )
            validation_path = tmp_path / 'validation_outcomes.json'
            validation_path.write_text(json.dumps(validation_fixture, indent=2, sort_keys=True) + '\n')

            result = subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'narrativedesk.cli',
                    'source-pack-bundle',
                    str(ROOT / 'examples' / 'source_pack_template.json'),
                    '--out-dir',
                    str(out_dir),
                    '--label',
                    'EXMPL bundled example',
                    '--validation-fixture',
                    str(validation_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            response = json.loads(result.stdout)
            bundled_validation = json.loads((out_dir / 'validation_fixture.json').read_text())
            manifest = json.loads((out_dir / 'manifest.json').read_text())
            verify_result = subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'narrativedesk.cli',
                    'bundle-verify',
                    str(out_dir),
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            verify_response = json.loads(verify_result.stdout)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(response['ok'])
        self.assertEqual(response['validation_fixture_source'], str(validation_path))
        self.assertEqual(bundled_validation['status'], 'validated')
        self.assertEqual(bundled_validation['rows'][0]['label'], 'validated')
        self.assertEqual(manifest['replay_integrity']['validation_future_source_ids'], ['SRC-009'])
        self.assertEqual(verify_result.returncode, 0, verify_result.stderr + verify_result.stdout)
        self.assertTrue(verify_response['ok'])

    def test_cli_source_pack_bundle_rejects_validation_fixture_with_replay_time_future_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            out_dir = tmp_path / 'bundle'
            payload = load_source_pack(ROOT / 'examples' / 'source_pack_template.json')
            validation_fixture = build_validation_fixture_template_from_source_pack(payload)
            validation_fixture['future_source_ids'] = ['SRC-001']
            validation_fixture['future_source_count'] = 1
            validation_fixture['rows'][0]['future_source_ids'] = ['SRC-001']
            validation_path = tmp_path / 'invalid_validation_outcomes.json'
            validation_path.write_text(json.dumps(validation_fixture, indent=2, sort_keys=True) + '\n')

            result = subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'narrativedesk.cli',
                    'source-pack-bundle',
                    str(ROOT / 'examples' / 'source_pack_template.json'),
                    '--out-dir',
                    str(out_dir),
                    '--validation-fixture',
                    str(validation_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            response = json.loads(result.stdout)

        self.assertEqual(result.returncode, 1)
        self.assertFalse(response['ok'])
        self.assertEqual(response['status'], 'validation_fixture_invalid')
        self.assertIn('blocked_future sources', response['errors'][0])

    def test_cli_source_pack_preview_reports_missing_file_as_json(self):
        result = subprocess.run(
            [
                sys.executable,
                '-m',
                'narrativedesk.cli',
                'source-pack-preview',
                str(ROOT / 'examples' / 'missing_source_pack.json'),
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        response = json.loads(result.stdout)

        self.assertEqual(result.returncode, 1)
        self.assertFalse(response['ok'])
        self.assertEqual(response['status'], 'invalid_input')
        self.assertEqual(result.stderr, '')

    def test_cli_source_pack_bundle_stops_when_readiness_fails(self):
        payload = _ingest_pack()
        payload['sources'][0]['supported_narrative_ids'] = []
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / 'source_pack.json'
            out_dir = Path(tmpdir) / 'bundle'
            source_path.write_text(json.dumps(payload))

            result = subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'narrativedesk.cli',
                    'source-pack-bundle',
                    str(source_path),
                    '--out-dir',
                    str(out_dir),
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            response = json.loads(result.stdout)
            readiness = json.loads((out_dir / 'readiness.json').read_text())

        self.assertEqual(result.returncode, 1)
        self.assertFalse(response['ok'])
        self.assertEqual(response['status'], 'needs_attention')
        self.assertFalse(readiness['checks']['narrative_linkage']['ok'])
        self.assertFalse((out_dir / 'event_fixture.json').exists())

    def test_cli_source_pack_ingest_template_round_trips(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'fixture.json'
            validation_path = Path(tmpdir) / 'validation.json'
            result = subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'narrativedesk.cli',
                    'source-pack-ingest',
                    str(ROOT / 'examples' / 'source_pack_template.json'),
                    '--out',
                    str(output_path),
                    '--validation-out',
                    str(validation_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            event, narratives, audit, _validation = run_replay(output_path)
            validation = json.loads(validation_path.read_text())

        self.assertEqual(event.ticker, 'EXMPL')
        self.assertEqual(len(narratives), 2)
        self.assertEqual(audit.blocked_source_ids, ['SRC-009'])
        self.assertEqual(validation['event_id'], 'EVT-EXAMPLE-2025-01-02')
        self.assertEqual(len(validation['rows']), 2)


if __name__ == '__main__':
    unittest.main()
