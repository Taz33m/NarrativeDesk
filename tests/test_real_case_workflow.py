from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cli(args: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "narrativedesk.cli", *args],
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        check=False,
        capture_output=True,
        text=True,
    )


class RealCaseWorkflowCliTests(unittest.TestCase):
    def test_real_case_workflow_writes_status_and_commands_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            env_file = root / ".env.workflow"
            env_file.write_text(
                "FINNHUB_API_KEY=fake-finnhub\n"
                "SEC_USER_AGENT=NarrativeDesk Tests test@example.com\n"
            )
            completed = run_cli(
                [
                    "real-case-workflow",
                    "--ticker",
                    "EXMPL",
                    "--company-name",
                    "Example Co",
                    "--event-type",
                    "regulatory/antitrust shock",
                    "--event-date",
                    "2025-01-02",
                    "--replay-lock",
                    "2025-01-02T16:10:00-05:00",
                    "--from",
                    "2025-01-01",
                    "--to",
                    "2025-01-07",
                    "--out-root",
                    str(root / "scratch"),
                    "--env-file",
                    str(env_file),
                    "--sonar-query",
                    "Example Co antitrust event January 2025",
                    "--market-peers",
                    "PEER",
                    "--sector-symbol",
                    "SECTOR",
                ]
            )

            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            payload = json.loads(completed.stdout)
            status_path = Path(payload["workflow_status_out"])
            commands_path = Path(payload["workflow_commands_out"])
            status = json.loads(status_path.read_text())
            commands = commands_path.read_text()

        self.assertEqual(status["status"], "ready_to_fetch")
        self.assertEqual(status["next_stage"], "fetch")
        self.assertGreaterEqual(status["total_stage_count"], 10)
        self.assertEqual(status["stage_statuses"][0]["stage"], "preflight")
        self.assertEqual(status["stage_statuses"][0]["status"], "complete")
        self.assertEqual(status["stage_statuses"][1]["stage"], "fetch")
        self.assertEqual(status["stage_statuses"][1]["status"], "next")
        self.assertTrue(any(item["stage"] == "discover" for item in status["commands"]))
        self.assertIn("real-source-discover", commands)
        self.assertIn("## Stage Status", commands)
        self.assertIn("| fetch | next |", commands)
        self.assertIn("real-case-curated-bundle", commands)
        self.assertIn("real-case-promote", commands)

    def test_real_case_workflow_detects_completed_scratch_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            env_file = root / ".env.workflow"
            env_file.write_text(
                "FINNHUB_API_KEY=fake-finnhub\n"
                "SEC_USER_AGENT=NarrativeDesk Tests test@example.com\n"
            )
            fetch_dir = root / "fetch"
            normalized_dir = fetch_dir / "normalized"
            draft_dir = root / "draft"
            normalized_dir.mkdir(parents=True)
            draft_dir.mkdir()
            (fetch_dir / "fetch_manifest.json").write_text("{}\n")
            (normalized_dir / "source_candidates.json").write_text('{"candidates": []}\n')
            (normalized_dir / "rejected_candidates.json").write_text('{"rejected_candidates": []}\n')
            completed = run_cli(
                [
                    "real-case-workflow",
                    "--ticker",
                    "EXMPL",
                    "--company-name",
                    "Example Co",
                    "--event-type",
                    "litigation settlement",
                    "--event-date",
                    "2025-01-02",
                    "--replay-lock",
                    "2025-01-02T16:10:00-05:00",
                    "--from",
                    "2025-01-01",
                    "--to",
                    "2025-01-07",
                    "--out-root",
                    str(root / "scratch"),
                    "--fetch-dir",
                    str(fetch_dir),
                    "--draft-dir",
                    str(draft_dir),
                    "--env-file",
                    str(env_file),
                ]
            )

        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        payload = json.loads(completed.stdout)
        by_stage = {stage["stage"]: stage for stage in payload["stage_statuses"]}
        self.assertEqual(by_stage["fetch"]["status"], "complete")
        self.assertEqual(by_stage["discover"]["status"], "skipped")
        self.assertEqual(by_stage["freeze"]["status"], "skipped")
        self.assertEqual(by_stage["normalize"]["status"], "complete")
        self.assertEqual(by_stage["draft"]["status"], "next")
        self.assertEqual(payload["next_stage"], "draft")
        self.assertEqual(payload["status"], "ready_to_draft")

    def test_real_case_promote_copies_verified_bundle_and_registers_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_index = root / "public_case_index.json"
            real_root = root / "real"
            completed = run_cli(
                [
                    "real-case-promote",
                    "--bundle-dir",
                    "data/fixtures/real/save_2024_regulatory",
                    "--public-slug",
                    "save_public_copy",
                    "--label",
                    "SAVE promoted copy",
                    "--real-root",
                    str(real_root),
                    "--case-index",
                    str(case_index),
                ]
            )

            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            payload = json.loads(completed.stdout)
            index_payload = json.loads(case_index.read_text())
            self.assertTrue(payload["ok"])
            self.assertTrue((real_root / "save_public_copy" / "manifest.json").exists())
            self.assertEqual(index_payload["cases"][0]["case_id"], "EVT-REAL-SAVE-2024-01-16")

    def test_real_case_promote_refuses_duplicate_case_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_index = root / "public_case_index.json"
            case_index.write_text(
                json.dumps(
                    {
                        "default_case_id": "EVT-REAL-SAVE-2024-01-16",
                        "cases": [
                            {
                                "case_id": "EVT-REAL-SAVE-2024-01-16",
                                "label": "Existing",
                                "event_fixture": "missing.json",
                                "validation_fixture": "missing-validation.json",
                            }
                        ],
                    }
                )
            )
            completed = run_cli(
                [
                    "real-case-promote",
                    "--bundle-dir",
                    "data/fixtures/real/save_2024_regulatory",
                    "--public-slug",
                    "save_duplicate",
                    "--label",
                    "SAVE duplicate",
                    "--real-root",
                    str(root / "real"),
                    "--case-index",
                    str(case_index),
                ]
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("already exists", completed.stdout)


if __name__ == "__main__":
    unittest.main()
