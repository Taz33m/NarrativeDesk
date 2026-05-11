import unittest
from dataclasses import replace
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
        validation["future_source_ids"] = ["SRC-009"]
        validation["rows"][1]["future_source_ids"] = ["SRC-009"]
        report = generate_markdown_report(event, narratives, audit, validation)

        self.assertIn("Research support output. Not investment advice.", report)
        self.assertIn("synthetic fixture", report)
        self.assertIn("Blocked future sources: SRC-009", report)
        self.assertIn("Source Map", report)
        self.assertIn("| SRC-009 | blocked_future | analyst_revision | n/a | NARR-001 | support |", report)
        self.assertNotIn("Future analyst revisions later reduced expansion estimates", report)
        self.assertNotIn("Synthetic Broker Model", report)
        self.assertIn("Citation QA", report)
        self.assertIn("Replay filter: pass", report)
        self.assertIn("Missing URLs: 8", report)
        self.assertIn("Source Reliability", report)
        self.assertIn("Blocked future sources are counted for auditability", report)
        self.assertIn("Average evidence quality: 0.80", report)
        self.assertIn("| unknown | 0 | 1 | n/a | n/a | n/a |", report)
        self.assertIn("Narrative Verification Ranking", report)
        self.assertIn("Evaluation Checks", report)
        self.assertIn("Narrative Recall@3: pass", report)
        self.assertIn("Average unsupported claim penalty: 0.06", report)
        self.assertIn("Model Comparison", report)
        self.assertIn("| headline_baseline | NARR-002 | #4 | miss |", report)
        self.assertIn("| evidence_only | NARR-001 | #1 | pass |", report)
        self.assertIn("| no_contradiction_penalty | NARR-001 | #1 | pass |", report)
        self.assertIn("| quality_weighted | NARR-001 | #1 | pass |", report)
        self.assertIn("| narrativedesk_tournament | NARR-001 | #1 | pass |", report)
        self.assertIn("Future Validation Fixture", report)
        self.assertIn("Validation data is shown separately", report)
        self.assertIn("Future validation source IDs: SRC-009", report)
        self.assertIn("Validation Outcome", report)
        self.assertNotIn("Synthetic Outcome", report)
        self.assertIn("| T+20 | validated |", report)
        self.assertIn(
            "| T+20 | validated | Analysts reduce forward revenue or subscriber estimates within 30 days. | SRC-009 |",
            report,
        )

    def test_replay_only_report_excludes_future_validation_sections(self):
        event, narratives, audit, _validation = run_replay(EVENT_FIXTURE)
        report = generate_markdown_report(event, narratives, audit)

        self.assertIn("Narrative Verification Ranking", report)
        self.assertIn("Citation QA: miss", report)
        self.assertNotIn("Evaluation Checks", report)
        self.assertNotIn("Model Comparison", report)
        self.assertNotIn("Future Validation Fixture", report)

    def test_real_curated_report_uses_real_data_note(self):
        event, narratives, audit, _validation = run_replay(EVENT_FIXTURE)
        real_event = replace(event, data_provenance_mode="real-curated")

        report = generate_markdown_report(real_event, narratives, audit)

        self.assertIn("real-curated replay bundle", report)
        self.assertIn("public use requires curator review", report)
        self.assertNotIn("generated from a synthetic fixture", report)

    def test_missing_volume_ratio_does_not_render_unit_suffix(self):
        event, narratives, audit, _validation = run_replay(EVENT_FIXTURE)
        event_without_volume = replace(event, volume_ratio=None)

        report = generate_markdown_report(event_without_volume, narratives, audit)

        self.assertIn("- Volume ratio: n/a", report)
        self.assertNotIn("n/ax", report)


if __name__ == "__main__":
    unittest.main()
