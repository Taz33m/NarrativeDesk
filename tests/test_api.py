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
        self.assertEqual(events_response.json()["events"][0]["ticker"], "ORION")

        run_response = self.client.post("/api/events/EVT-ORION-2025-08-07/run")
        self.assertEqual(run_response.status_code, 200)
        payload = run_response.json()

        self.assertEqual(payload["event"]["ticker"], "ORION")
        self.assertEqual(len(payload["narratives"]), 4)
        self.assertEqual(payload["narratives"][0]["title"], "Forward demand slowdown")
        self.assertEqual(payload["replay_audit"]["blocked_source_ids"], ["SRC-009"])
        self.assertNotIn("validation", payload)

        returned_sources = []
        for narrative in payload["narratives"]:
            returned_sources.extend(item["source_id"] for item in narrative["supporting_evidence"])
            returned_sources.extend(item["source_id"] for item in narrative["contradicting_evidence"])
        self.assertNotIn("SRC-009", returned_sources)

    def test_validation_and_report_are_separate(self):
        validation_response = self.client.get("/api/events/EVT-ORION-2025-08-07/validation")
        self.assertEqual(validation_response.status_code, 200)
        self.assertEqual(validation_response.json()["rows"][1]["label"], "validated")

        report_response = self.client.get("/api/events/EVT-ORION-2025-08-07/report")
        self.assertEqual(report_response.status_code, 200)
        self.assertIn("Future Validation Fixture", report_response.text)
        self.assertIn("Not investment advice", report_response.text)

    def test_missing_event_returns_404(self):
        response = self.client.post("/api/events/MISSING/run")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
