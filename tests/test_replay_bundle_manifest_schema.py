from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tests.schema_utils import validate_schema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "replay_bundle_manifest.schema.json"
TEMPLATE_PATH = ROOT / "examples" / "source_pack_template.json"


class ReplayBundleManifestSchemaTests(unittest.TestCase):
    def test_generated_bundle_manifest_matches_public_schema(self):
        schema = _load_schema()
        manifest = _generated_manifest()

        validate_schema(manifest, schema, schema)

    def test_schema_describes_replay_bundle_contract(self):
        schema = _load_schema()
        integrity_required = schema["$defs"]["replay_integrity"]["required"]
        artifact_required = schema["$defs"]["artifact"]["required"]

        self.assertEqual(schema["title"], "NarrativeDesk Replay Bundle Manifest")
        self.assertIn("replay_integrity", schema["required"])
        self.assertIn("artifacts", schema["required"])
        self.assertIn("future_validation_separate", integrity_required)
        self.assertIn("sha256", artifact_required)
        self.assertIn("bytes", artifact_required)

    def test_schema_rejects_bad_artifact_hash_shape(self):
        schema = _load_schema()
        manifest = _generated_manifest()
        manifest["artifacts"][0]["sha256"] = "sha256:not-a-real-hash"

        with self.assertRaisesRegex(AssertionError, "sha256 expected pattern"):
            validate_schema(manifest, schema, schema)

    def test_schema_rejects_naive_replay_timestamp(self):
        schema = _load_schema()
        manifest = _generated_manifest()
        manifest["replay_timestamp"] = "2025-01-02T10:00:00"

        with self.assertRaisesRegex(AssertionError, "timezone offset"):
            validate_schema(manifest, schema, schema)

    def test_schema_rejects_missing_replay_integrity_field(self):
        schema = _load_schema()
        manifest = _generated_manifest()
        del manifest["replay_integrity"]["future_validation_separate"]

        with self.assertRaisesRegex(AssertionError, "future_validation_separate is required"):
            validate_schema(manifest, schema, schema)


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text())


def _generated_manifest() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir) / "bundle"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "narrativedesk.cli",
                "source-pack-bundle",
                str(TEMPLATE_PATH),
                "--out-dir",
                str(out_dir),
                "--label",
                "EXMPL schema contract",
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=ROOT,
            env=env,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr + result.stdout)
        return copy.deepcopy(json.loads((out_dir / "manifest.json").read_text()))


if __name__ == "__main__":
    unittest.main()
