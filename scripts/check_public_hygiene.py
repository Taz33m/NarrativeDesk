from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_TRACKED_PATHS = (
    re.compile(r"^\.codex-work(/|$)"),
    re.compile(r"^\.env($|\.)"),
    re.compile(r"^apps/web/dist/"),
    re.compile(r"^artifacts/.*\.(json|md|csv)$"),
)
REQUIRED_GITIGNORE_ENTRIES = (
    ".env.*",
    ".codex-work/",
    "apps/web/dist/",
    "artifacts/*.json",
    "artifacts/*.md",
    "artifacts/*.csv",
    "!artifacts/.gitkeep",
)
ALLOWED_MARKDOWN = {
    "AGENTS.md",
    "README.md",
    "apps/web/public/demo/report.md",
    "examples/sample_report.md",
}
ALLOWED_MARKDOWN_PATTERNS = (
    re.compile(r"^data/fixtures/real/[^/]+/report\.md$"),
)
PACKAGE_FILES = (
    "package.json",
    "package-lock.json",
    "apps/web/package.json",
)
HIGH_CONFIDENCE_SECRET_PATTERNS = (
    ("OpenRouter token", re.compile(r"sk-or-v1-[A-Za-z0-9_-]{20,}")),
    ("Perplexity token", re.compile(r"pplx-[A-Za-z0-9_-]{20,}")),
    ("SEC User-Agent contact", re.compile(r"\bSEC_USER_AGENT[ \t]*=[ \t]*[\"']?([^\n\"']+)")),
    (
        "provider env assignment",
        re.compile(
            r"\b(?:FINNHUB|ALPHA_VANTAGE|NEWS|OPENROUTER|PERPLEXITY)_API_KEY[ \t]*=[ \t]*[\"']?([^\"'\s<>]+)"
        ),
    ),
)
ALLOWED_FAKE_SECRET_PREFIXES = (
    "fake",
    "file",
    "news-secret",
    "secret-token",
    "test",
    "your_",
)
ALLOWED_EXAMPLE_EMAIL_DOMAINS = (
    "example.com",
    "example.org",
    "example.net",
)
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")


def tracked_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def text_for(path: Path) -> str | None:
    try:
        return path.read_text()
    except UnicodeDecodeError:
        return None


def run_checks(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    files = tracked_files(root)
    file_set = set(files)

    for path in files:
        if any(pattern.search(path) for pattern in FORBIDDEN_TRACKED_PATHS):
            errors.append(f"forbidden generated/private path is tracked: {path}")

    markdown_files = {path for path in files if path.endswith(".md")}
    unexpected_markdown = sorted(
        path
        for path in markdown_files - ALLOWED_MARKDOWN
        if not any(pattern.search(path) for pattern in ALLOWED_MARKDOWN_PATTERNS)
    )
    if unexpected_markdown:
        errors.append(f"unexpected public markdown files: {', '.join(unexpected_markdown)}")

    gitignore = (root / ".gitignore").read_text()
    for entry in REQUIRED_GITIGNORE_ENTRIES:
        if entry not in gitignore:
            errors.append(f".gitignore missing required public-safety entry: {entry}")

    for package_file in PACKAGE_FILES:
        text = (root / package_file).read_text()
        if '"latest"' in text:
            errors.append(f"{package_file} must pin dependencies instead of using \"latest\"")

    source_pack_path = root / "examples" / "source_pack_template.json"
    source_pack = json.loads(source_pack_path.read_text())
    provenance_mode = source_pack.get("case_metadata", {}).get("data_provenance_mode")
    if provenance_mode != "synthetic":
        errors.append("examples/source_pack_template.json must stay synthetic until real claims are curated")

    for path in files:
        full_path = root / path
        text = text_for(full_path)
        if text is None:
            continue
        for label, pattern in HIGH_CONFIDENCE_SECRET_PATTERNS:
            for match in pattern.finditer(text):
                if label == "provider env assignment":
                    value = match.group(1).strip().strip("',\")").lower()
                    if value.startswith(ALLOWED_FAKE_SECRET_PREFIXES) or value.startswith("\\n") or value == "":
                        continue
                if label == "SEC User-Agent contact":
                    emails = EMAIL_PATTERN.findall(match.group(1))
                    if not emails:
                        continue
                    if all(email.lower().split("@", 1)[1] in ALLOWED_EXAMPLE_EMAIL_DOMAINS for email in emails):
                        continue
                errors.append(f"{label} found in tracked file: {path}")

    expected_public_artifacts = {
        "artifacts/.gitkeep",
        "apps/web/public/demo/report.md",
        "examples/sample_report.md",
    }
    missing_expected = sorted(expected_public_artifacts - file_set)
    if missing_expected:
        errors.append(f"expected public artifacts missing: {', '.join(missing_expected)}")

    return errors


def main() -> int:
    errors = run_checks(ROOT)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2, sort_keys=True))
        return 1
    print(json.dumps({"ok": True, "checks": "public repository hygiene"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
