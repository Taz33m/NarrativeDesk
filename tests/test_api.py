import unittest

try:
    from fastapi.testclient import TestClient

    from apps.api.main import app
except Exception as exc:  # pragma: no cover - dependency may be absent in minimal envs
    TestClient = None
    app = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


@unittest.skipIf(TestClient is None, f"FastAPI TestClient unavailable: {IMPORT_ERROR}")
class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_events_and_run_endpoint(self):
        events_response = self.client.get("/api/events")
        self.assertEqual(events_response.status_code, 200)
        events = events_response.json()["events"]
        self.assertEqual(events[0]["ticker"], "ORION")
        self.assertEqual(events[1]["ticker"], "AURORA")
        self.assertEqual(events[2]["ticker"], "LYRA")
        self.assertEqual(events[0]["links"]["ledger"], "/api/events/EVT-ORION-2025-08-07/ledger")

        run_response = self.client.post("/api/events/EVT-ORION-2025-08-07/run")
        self.assertEqual(run_response.status_code, 200)
        payload = run_response.json()

        self.assertEqual(payload["event"]["ticker"], "ORION")
        self.assertEqual(len(payload["narratives"]), 4)
        self.assertEqual(payload["narratives"][0]["title"], "Forward demand slowdown")
        self.assertEqual(payload["replay_audit"]["blocked_source_ids"], ["SRC-009"])
        self.assertIn("source_clustering", payload)
        self.assertEqual(payload["source_clustering"]["blocked_future_source_ids"], ["SRC-009"])
        self.assertNotIn("validation", payload)

        returned_sources = []
        for narrative in payload["narratives"]:
            returned_sources.extend(item["source_id"] for item in narrative["supporting_evidence"])
            returned_sources.extend(item["source_id"] for item in narrative["contradicting_evidence"])
        self.assertNotIn("SRC-009", returned_sources)

        aurora_response = self.client.post("/api/events/EVT-AURORA-2025-10-22/run")
        self.assertEqual(aurora_response.status_code, 200)
        self.assertEqual(aurora_response.json()["event"]["ticker"], "AURORA")
        self.assertEqual(aurora_response.json()["event"]["case_id"], "EVT-AURORA-2025-10-22")

        lyra_response = self.client.post("/api/events/EVT-LYRA-2025-11-13/run")
        self.assertEqual(lyra_response.status_code, 200)
        self.assertEqual(lyra_response.json()["event"]["ticker"], "LYRA")
        self.assertEqual(lyra_response.json()["narratives"][1]["narrative_id"], "LYR-NARR-002")
        self.assertNotIn(
            "LYR-SRC-009",
            [
                item["source_id"]
                for narrative in lyra_response.json()["narratives"]
                for item in [*narrative["supporting_evidence"], *narrative["contradicting_evidence"]]
            ],
        )

    def test_evaluations_endpoint_returns_benchmark_without_validation_rows(self):
        response = self.client.get("/api/evaluations")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["aggregate"]["case_count"], 3)
        self.assertEqual(payload["aggregate"]["narrative_recall_at_3_rate"], 1.0)
        self.assertAlmostEqual(payload["aggregate"]["narrativedesk_tournament_validated_rate"], 2 / 3)
        self.assertEqual(payload["aggregate"]["source_duplicate_cluster_count"], 3)
        self.assertEqual(payload["cases"][2]["ticker"], "LYRA")
        self.assertEqual(payload["cases"][2]["evaluation"]["validated_rank"], 2)
        self.assertFalse(payload["cases"][2]["evaluation"]["top_ranked_validated"])
        self.assertIn("source_reliability", payload["cases"][2])
        self.assertIn("source_clustering", payload["cases"][2])
        self.assertNotIn("validation", payload["cases"][2])
        self.assertEqual(
            payload["cases"][2]["links"]["validation"],
            "/api/events/EVT-LYRA-2025-11-13/validation",
        )

    def test_validation_and_report_are_separate(self):
        validation_response = self.client.get("/api/events/EVT-ORION-2025-08-07/validation")
        self.assertEqual(validation_response.status_code, 200)
        self.assertEqual(validation_response.json()["future_source_ids"], ["SRC-009"])
        self.assertEqual(validation_response.json()["rows"][1]["label"], "validated")
        self.assertEqual(validation_response.json()["rows"][1]["future_source_ids"], ["SRC-009"])

        report_response = self.client.get("/api/events/EVT-ORION-2025-08-07/report")
        self.assertEqual(report_response.status_code, 200)
        self.assertNotIn("Future Validation Fixture", report_response.text)
        self.assertIn("Not investment advice", report_response.text)

        evaluation_report_response = self.client.get(
            "/api/events/EVT-ORION-2025-08-07/report?include_validation=true"
        )
        self.assertEqual(evaluation_report_response.status_code, 200)
        self.assertIn("Future Validation Fixture", evaluation_report_response.text)
        self.assertIn("Future validation source IDs: SRC-009", evaluation_report_response.text)

    def test_missing_event_returns_404(self):
        response = self.client.post("/api/events/MISSING/run")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
