import unittest
from pathlib import Path

from narrativedesk.pipeline import ledger_export, run_replay
from narrativedesk.source_clustering import compute_source_clustering

ROOT = Path(__file__).resolve().parents[1]
ORION_EVENT = ROOT / "data" / "fixtures" / "synthetic_event.json"
AURORA_EVENT = ROOT / "data" / "fixtures" / "synthetic_event_aurora.json"
LYRA_EVENT = ROOT / "data" / "fixtures" / "synthetic_event_lyra.json"


def clusters_by_id(artifact):
    return {cluster.cluster_id: cluster for cluster in artifact.clusters}


class SourceClusteringTests(unittest.TestCase):
    def test_orion_clusters_allowed_sources_without_future_claim_text(self):
        _event, narratives, audit, _validation = run_replay(ORION_EVENT)
        artifact = compute_source_clustering(narratives, audit)

        self.assertEqual(artifact.allowed_source_count, 8)
        self.assertEqual(artifact.blocked_future_source_count, 1)
        self.assertEqual(artifact.blocked_future_source_ids, ["SRC-009"])
        self.assertEqual(artifact.cluster_count, 8)
        self.assertEqual(artifact.duplicate_cluster_count, 0)
        self.assertAlmostEqual(artifact.average_cluster_size, 1.0)
        self.assertAlmostEqual(artifact.average_derived_originality_score, 1.0)
        self.assertFalse(
            any("SRC-009" in cluster.source_ids for cluster in artifact.clusters),
            "blocked future evidence must not be clustered from hidden claim text",
        )

    def test_aurora_uses_explicit_independence_cluster_ids(self):
        _event, narratives, audit, _validation = run_replay(AURORA_EVENT)
        artifact = compute_source_clustering(narratives, audit)
        clusters = clusters_by_id(artifact)

        self.assertEqual(artifact.allowed_source_count, 8)
        self.assertEqual(artifact.cluster_count, 1)
        self.assertEqual(artifact.duplicate_cluster_count, 1)
        self.assertIn("cluster-a", clusters)
        self.assertEqual(clusters["cluster-a"].cluster_basis, "independence_cluster_id")
        self.assertEqual(clusters["cluster-a"].source_count, 8)
        self.assertEqual(clusters["cluster-a"].narrative_ids, [
            "AUR-NARR-001",
            "AUR-NARR-002",
            "AUR-NARR-003",
            "AUR-NARR-004",
        ])

    def test_lyra_surfaces_duplicate_source_clusters(self):
        _event, narratives, audit, _validation = run_replay(LYRA_EVENT)
        artifact = compute_source_clustering(narratives, audit)
        clusters = clusters_by_id(artifact)

        self.assertEqual(artifact.allowed_source_count, 8)
        self.assertEqual(artifact.cluster_count, 3)
        self.assertEqual(artifact.duplicate_cluster_count, 2)
        self.assertAlmostEqual(artifact.average_derived_originality_score, 0.375)
        self.assertEqual(clusters["lyra-company"].source_count, 5)
        self.assertEqual(clusters["lyra-media"].source_count, 1)
        self.assertEqual(clusters["lyra-market-data"].source_count, 2)

    def test_ledger_export_includes_source_clustering_artifact(self):
        event, narratives, audit, _validation = run_replay(ORION_EVENT)
        ledger = ledger_export(event, narratives, audit)

        self.assertIn("source_clustering", ledger)
        self.assertEqual(ledger["source_clustering"]["allowed_source_count"], 8)
        self.assertEqual(ledger["source_clustering"]["blocked_future_source_ids"], ["SRC-009"])
        self.assertIn("clusters", ledger["source_clustering"])


if __name__ == "__main__":
    unittest.main()
