import unittest
from pathlib import Path

from narrativedesk.pipeline import load_validation_fixture, run_replay
from narrativedesk.report import generate_markdown_report

ROOT = Path(__file__).resolve().parents[1]
EVENT_FIXTURE = ROOT / "data" / "fixtures" / "synthetic_event.json"
VALIDATION_FIXTURE = ROOT / "data" / "fixtures" / "synthetic_validation.json"


class ReportTests(unittest.TestCase):
    def test_report_shows_replay_and_future_validation_separately(self):
        event, narratives, audit, _validation = run_replay(EVENT_FIXTURE)
        validation = load_validation_fixture(VALIDATION_FIXTURE)
        report = generate_markdown_report(event, narratives, audit, validation)

        self.assertIn("Research support output. Not investment advice.", report)
        self.assertIn("Blocked future sources: SRC-009", report)
        self.assertIn("Narrative Tournament", report)
        self.assertIn("Future Validation Fixture", report)
        self.assertIn("Validation data is shown separately", report)
        self.assertIn("| T+20 | validated |", report)


if __name__ == "__main__":
    unittest.main()
