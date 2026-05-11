import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import check_public_hygiene


ROOT = Path(__file__).resolve().parents[1]
BASE_TRACKED_FILES = [
    "AGENTS.md",
    "README.md",
    "apps/web/package.json",
    "apps/web/public/demo/report.md",
    "artifacts/.gitkeep",
    "examples/sample_report.md",
    "examples/source_pack_template.json",
    "package-lock.json",
    "package.json",
]


class PublicHygieneTests(unittest.TestCase):
    def test_public_hygiene_gate_passes(self):
        result = subprocess.run(
            [sys.executable, "scripts/check_public_hygiene.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(payload["ok"])

    def test_public_hygiene_flags_publish_risks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_public_repo(root)
            (root / ".env.local").write_text("FINNHUB_API_KEY=real-looking-value\n")
            (root / "leaky.py").write_text(
                "OPENROUTER_API_KEY='sk-or-v1-thisisarealisticlookingtoken12345'\n"
                "SEC_USER_AGENT='Analyst App (person@private.test)'\n"
            )

            with patch.object(
                check_public_hygiene,
                "tracked_files",
                return_value=[*BASE_TRACKED_FILES, ".env.local", "leaky.py"],
            ):
                errors = check_public_hygiene.run_checks(root)

        self.assertTrue(any("forbidden generated/private path is tracked: .env.local" in error for error in errors))
        self.assertTrue(any("OpenRouter token found in tracked file: leaky.py" in error for error in errors))
        self.assertTrue(any("SEC User-Agent contact found in tracked file: leaky.py" in error for error in errors))
        self.assertTrue(any("provider env assignment found in tracked file: .env.local" in error for error in errors))

    def test_public_hygiene_flags_contract_drift(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_public_repo(root)
            (root / "apps" / "web" / "package.json").write_text('{"dependencies":{"react":"latest"}}\n')
            (root / "examples" / "source_pack_template.json").write_text(
                json.dumps({"case_metadata": {"data_provenance_mode": "real-curated"}})
            )
            (root / "notes.md").write_text("extra public doc\n")

            with patch.object(
                check_public_hygiene,
                "tracked_files",
                return_value=[*BASE_TRACKED_FILES, "notes.md"],
            ):
                errors = check_public_hygiene.run_checks(root)

        self.assertTrue(any("apps/web/package.json must pin dependencies" in error for error in errors))
        self.assertTrue(any("source_pack_template.json must stay synthetic" in error for error in errors))
        self.assertTrue(any("unexpected public markdown files: notes.md" in error for error in errors))


def _write_minimal_public_repo(root: Path) -> None:
    for directory in [
        root / "apps" / "web" / "package.json",
        root / "apps" / "web" / "public" / "demo" / "report.md",
        root / "artifacts" / ".gitkeep",
        root / "examples" / "sample_report.md",
        root / "examples" / "source_pack_template.json",
    ]:
        directory.parent.mkdir(parents=True, exist_ok=True)

    (root / ".gitignore").write_text(
        "\n".join(
            [
                ".env.*",
                ".codex-work/",
                "apps/web/dist/",
                "artifacts/*.json",
                "artifacts/*.md",
                "artifacts/*.csv",
                "!artifacts/.gitkeep",
            ]
        )
        + "\n"
    )
    (root / "AGENTS.md").write_text("agent notes\n")
    (root / "README.md").write_text("readme\n")
    (root / "package.json").write_text('{"dependencies":{"demo":"1.0.0"}}\n')
    (root / "package-lock.json").write_text('{"packages":{}}\n')
    (root / "apps" / "web" / "package.json").write_text('{"dependencies":{"react":"19.2.5"}}\n')
    (root / "apps" / "web" / "public" / "demo" / "report.md").write_text("generated report\n")
    (root / "artifacts" / ".gitkeep").write_text("")
    (root / "examples" / "sample_report.md").write_text("sample report\n")
    (root / "examples" / "source_pack_template.json").write_text(
        json.dumps({"case_metadata": {"data_provenance_mode": "synthetic"}})
    )


if __name__ == "__main__":
    unittest.main()
