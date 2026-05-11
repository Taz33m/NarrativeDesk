from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from narrativedesk.replay_bundle import verify_replay_bundle

ROOT = Path(__file__).resolve().parents[1]


class ReplayBundleVerificationTests(unittest.TestCase):
    def test_verify_replay_bundle_accepts_generated_bundle(self):
        out_dir = _generated_bundle()

        result = verify_replay_bundle(out_dir)

        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["case_id"], "EVT-EXAMPLE-2025-01-02")
        self.assertTrue(result["checks"]["artifacts"]["ok"])
        self.assertTrue(result["checks"]["replay_integrity"]["ok"])

    def test_cli_bundle_verify_reports_ok(self):
        out_dir = _generated_bundle()
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "narrativedesk.cli",
                "bundle-verify",
                str(out_dir),
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=ROOT,
            env=_cli_env(),
        )

        response = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(response["ok"], response["errors"])

    def test_verify_replay_bundle_flags_tampered_artifact(self):
        out_dir = _generated_bundle()
        (out_dir / "report.md").write_text("tampered report\n")

        result = verify_replay_bundle(out_dir)

        self.assertFalse(result["ok"])
        self.assertIn("artifacts: report.md sha256 mismatch", result["errors"])

    def test_verify_replay_bundle_rejects_manifest_path_escape(self):
        out_dir = _generated_bundle()
        manifest_path = out_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["artifacts"][0]["path"] = "../source_pack.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

        result = verify_replay_bundle(out_dir)

        self.assertFalse(result["ok"])
        self.assertIn(
            "artifacts: artifacts[0].path must not escape the bundle directory",
            result["errors"],
        )

    def test_verify_replay_bundle_flags_stale_replay_integrity(self):
        out_dir = _generated_bundle()
        manifest_path = out_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["replay_integrity"]["blocked_future_source_ids"] = []
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

        result = verify_replay_bundle(out_dir)

        self.assertFalse(result["ok"])
        self.assertIn(
            "replay_integrity: manifest blocked future source IDs do not match replay audit",
            result["errors"],
        )


def _generated_bundle() -> Path:
    tmpdir = tempfile.TemporaryDirectory()
    out_dir = Path(tmpdir.name) / "bundle"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "narrativedesk.cli",
            "source-pack-bundle",
            str(ROOT / "examples" / "source_pack_template.json"),
            "--out-dir",
            str(out_dir),
            "--label",
            "EXMPL bundle verify test",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=_cli_env(),
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr + result.stdout)
    _TEMP_DIRS.append(tmpdir)
    return out_dir


def _cli_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(ROOT / "src")
    return env


_TEMP_DIRS: list[tempfile.TemporaryDirectory[str]] = []


if __name__ == "__main__":
    unittest.main()
