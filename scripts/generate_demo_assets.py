from __future__ import annotations

import json
from pathlib import Path

from narrativedesk.pipeline import ledger_export, load_validation_fixture, run_replay
from narrativedesk.report import generate_markdown_report

ROOT_DIR = Path(__file__).resolve().parents[1]
EVENT_FIXTURE = ROOT_DIR / "data" / "fixtures" / "synthetic_event.json"
VALIDATION_FIXTURE = ROOT_DIR / "data" / "fixtures" / "synthetic_validation.json"
WEB_DEMO_DIR = ROOT_DIR / "apps" / "web" / "public" / "demo"
EXAMPLES_DIR = ROOT_DIR / "examples"
ARTIFACTS_DIR = ROOT_DIR / "artifacts"


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main() -> int:
    event, narratives, audit, _validation = run_replay(EVENT_FIXTURE)
    validation = load_validation_fixture(VALIDATION_FIXTURE)
    ledger = ledger_export(event, narratives, audit)
    report = generate_markdown_report(event, narratives, audit, validation)

    WEB_DEMO_DIR.mkdir(parents=True, exist_ok=True)
    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    write_json(WEB_DEMO_DIR / "ledger.json", ledger)
    write_json(WEB_DEMO_DIR / "validation.json", validation)
    (WEB_DEMO_DIR / "report.md").write_text(report)
    (EXAMPLES_DIR / "sample_report.md").write_text(report)
    write_json(ARTIFACTS_DIR / "sample_ledger.json", ledger)
    print("Generated web demo assets, example report, and sample ledger.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
