import unittest
from pathlib import Path

from narrativedesk.citation_qa import run_citation_qa
from narrativedesk.evaluation import (
    evaluate_replay,
    summarize_case_evaluations,
    validated_narrative_ids,
)
from narrativedesk.pipeline import load_validation_fixture, run_replay
from narrativedesk.source_clustering import compute_source_clustering
from narrativedesk.source_reliability import compute_source_reliability

ROOT = Path(__file__).resolve().parents[1]
ORION_EVENT = ROOT / "data" / "fixtures" / "synthetic_event.json"
ORION_VALIDATION = ROOT / "data" / "fixtures" / "synthetic_validation.json"
AURORA_EVENT = ROOT / "data" / "fixtures" / "synthetic_event_aurora.json"
AURORA_VALIDATION = ROOT / "data" / "fixtures" / "synthetic_validation_aurora.json"
LYRA_EVENT = ROOT / "data" / "fixtures" / "synthetic_event_lyra.json"
LYRA_VALIDATION = ROOT / "data" / "fixtures" / "synthetic_validation_lyra.json"


class EvaluationTests(unittest.TestCase):
    def test_validated_narrative_ids(self):
        validation = load_validation_fixture(ORION_VALIDATION)

        self.assertEqual(validated_narrative_ids(validation), ["NARR-001"])

    def test_evaluate_replay_reports_recall_and_unsupported_metrics(self):
        event, narratives, audit, _validation = run_replay(ORION_EVENT)
        validation = load_validation_fixture(ORION_VALIDATION)
        summary = evaluate_replay(narratives, audit, validation)

        self.assertEqual(event.ticker, "ORION")
        self.assertEqual(summary.validated_narrative_ids, ["NARR-001"])
        self.assertEqual(summary.validated_rank, 1)
        self.assertTrue(summary.narrative_recall_at_3)
        self.assertTrue(summary.top_ranked_validated)
        self.assertEqual(summary.blocked_future_source_count, 1)
        self.assertEqual(summary.allowed_source_count, 8)
        self.assertAlmostEqual(summary.unsupported_claim_penalty_avg, 0.0575)
        self.assertEqual(summary.unsupported_claim_penalty_max, 0.1)
        self.assertEqual(summary.high_unsupported_claim_count, 1)
        comparisons = {row.system_id: row for row in summary.model_comparisons}
        self.assertEqual(
            list(comparisons),
            [
                "headline_baseline",
                "evidence_only",
                "no_contradiction_penalty",
                "quality_weighted",
                "narrativedesk_tournament",
            ],
        )
        self.assertEqual(comparisons["headline_baseline"].selected_narrative_id, "NARR-002")
        self.assertFalse(comparisons["headline_baseline"].validated)
        self.assertEqual(comparisons["evidence_only"].selected_narrative_id, "NARR-001")
        self.assertTrue(comparisons["evidence_only"].validated)
        self.assertEqual(comparisons["no_contradiction_penalty"].selected_narrative_id, "NARR-001")
        self.assertTrue(comparisons["no_contradiction_penalty"].validated)
        self.assertEqual(comparisons["quality_weighted"].selected_narrative_id, "NARR-001")
        self.assertTrue(comparisons["quality_weighted"].validated)
        self.assertEqual(comparisons["narrativedesk_tournament"].selected_narrative_id, "NARR-001")
        self.assertTrue(comparisons["narrativedesk_tournament"].validated)

    def test_evaluate_replay_leaves_model_comparison_pending_without_validated_rows(self):
        _event, narratives, audit, _validation = run_replay(ORION_EVENT)
        summary = evaluate_replay(narratives, audit, {"rows": []})

        self.assertIsNone(summary.narrative_recall_at_3)
        self.assertIsNone(summary.top_ranked_validated)
        self.assertTrue(all(row.validated is None for row in summary.model_comparisons))

    def test_evaluate_replay_counts_missing_validated_narrative_as_miss(self):
        _event, narratives, audit, _validation = run_replay(ORION_EVENT)
        summary = evaluate_replay(
            narratives,
            audit,
            {"rows": [{"label": "validated", "narrative_id": "MISSING-NARR"}]},
        )

        self.assertEqual(summary.validated_narrative_ids, ["MISSING-NARR"])
        self.assertEqual(summary.missing_validated_narrative_ids, ["MISSING-NARR"])
        self.assertIsNone(summary.validated_rank)
        self.assertFalse(summary.narrative_recall_at_3)
        self.assertFalse(summary.top_ranked_validated)

    def test_summarize_case_evaluations(self):
        case_evaluations = []
        for case_id, event_path, validation_path in [
            ("EVT-ORION-2025-08-07", ORION_EVENT, ORION_VALIDATION),
            ("EVT-AURORA-2025-10-22", AURORA_EVENT, AURORA_VALIDATION),
            ("EVT-LYRA-2025-11-13", LYRA_EVENT, LYRA_VALIDATION),
        ]:
            event, narratives, audit, _validation = run_replay(event_path)
            validation = load_validation_fixture(validation_path)
            case_evaluations.append(
                {
                    "case_id": case_id,
                    "ticker": event.ticker,
                    "evaluation": evaluate_replay(narratives, audit, validation).to_dict(),
                    "citation_qa": run_citation_qa(narratives, audit).to_dict(),
                    "source_reliability": compute_source_reliability(narratives, audit).to_dict(),
                    "source_clustering": compute_source_clustering(narratives, audit).to_dict(),
                }
            )

        aggregate = summarize_case_evaluations(case_evaluations)

        self.assertEqual(aggregate["case_count"], 3)
        self.assertEqual(aggregate["evaluated_case_count"], 3)
        self.assertEqual(aggregate["narrative_recall_at_3_rate"], 1.0)
        self.assertAlmostEqual(aggregate["top_ranked_validated_rate"], 2 / 3)
        self.assertAlmostEqual(aggregate["evidence_only_validated_rate"], 2 / 3)
        self.assertAlmostEqual(aggregate["headline_baseline_validated_rate"], 1 / 3)
        self.assertAlmostEqual(aggregate["narrativedesk_tournament_validated_rate"], 2 / 3)
        self.assertAlmostEqual(aggregate["no_contradiction_penalty_validated_rate"], 2 / 3)
        self.assertAlmostEqual(aggregate["quality_weighted_validated_rate"], 2 / 3)
        self.assertEqual(aggregate["blocked_future_source_count"], 3)
        self.assertAlmostEqual(aggregate["citation_qa_pass_rate"], 2 / 3)
        self.assertEqual(aggregate["replay_filter_pass_rate"], 1.0)
        self.assertEqual(aggregate["support_coverage_pass_rate"], 1.0)
        self.assertAlmostEqual(aggregate["provenance_ready_rate"], 2 / 3)
        self.assertEqual(aggregate["missing_url_count"], 8)
        self.assertEqual(aggregate["missing_content_hash_count"], 8)
        self.assertEqual(aggregate["low_quality_evidence_count"], 2)
        self.assertAlmostEqual(aggregate["source_reliability_avg_evidence_quality"], 0.804167)
        self.assertAlmostEqual(aggregate["source_reliability_avg_independence"], 0.8192)
        self.assertAlmostEqual(aggregate["source_reliability_avg_originality"], 0.591667)
        self.assertEqual(aggregate["source_cluster_count"], 12)
        self.assertEqual(aggregate["source_duplicate_cluster_count"], 3)
        self.assertAlmostEqual(aggregate["source_clustering_avg_derived_originality"], 0.541667)


if __name__ == "__main__":
    unittest.main()
