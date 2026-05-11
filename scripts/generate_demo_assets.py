from __future__ import annotations

import json
from pathlib import Path

from narrativedesk.evaluation import evaluate_replay, summarize_case_evaluations
from narrativedesk.pipeline import ledger_export, load_event_fixture, load_validation_fixture, run_replay
from narrativedesk.report import generate_markdown_report

ROOT_DIR = Path(__file__).resolve().parents[1]
CASE_INDEX_FIXTURE = ROOT_DIR / "data" / "fixtures" / "case_index.json"
WEB_DEMO_DIR = ROOT_DIR / "apps" / "web" / "public" / "demo"
EXAMPLES_DIR = ROOT_DIR / "examples"
ARTIFACTS_DIR = ROOT_DIR / "artifacts"


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main() -> int:
    case_index = json.loads(CASE_INDEX_FIXTURE.read_text())
    case_payload = {"default_case_id": case_index["default_case_id"], "cases": []}
    validation_payload = {"default_case_id": case_index["default_case_id"], "cases": []}
    case_evaluations = []
    for case in case_index["cases"]:
        event, narratives, audit, _validation = run_replay(ROOT_DIR / case["event_fixture"])
        validation = load_validation_fixture(ROOT_DIR / case["validation_fixture"])
        ledger = ledger_export(event, narratives, audit)
        report = generate_markdown_report(event, narratives, audit)
        evaluation = evaluate_replay(narratives, audit, validation).to_dict()
        case_evaluations.append({
            "case_id": case["case_id"],
            "label": case["label"],
            "ticker": event.ticker,
            "evaluation": evaluation,
            "citation_qa": ledger["citation_qa"],
            "source_reliability": ledger["source_reliability"],
            "source_clustering": ledger["source_clustering"],
        })
        case_payload["cases"].append({
            "case_id": case["case_id"],
            "label": case["label"],
            "ledger": ledger,
            "report": report,
            "bundle_integrity": bundle_integrity_summary(ledger, validation),
        })
        validation_payload["cases"].append({
            "case_id": case["case_id"],
            "label": case["label"],
            "validation": validation,
            "evaluation": evaluation,
        })
    validation_payload["aggregate"] = summarize_case_evaluations(case_evaluations)

    default_case = next(item for item in case_payload["cases"] if item["case_id"] == case_payload["default_case_id"])
    default_validation_case = next(
        item for item in validation_payload["cases"] if item["case_id"] == validation_payload["default_case_id"]
    )

    WEB_DEMO_DIR.mkdir(parents=True, exist_ok=True)
    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    write_json(WEB_DEMO_DIR / "ledger.json", default_case["ledger"])
    write_json(WEB_DEMO_DIR / "validation.json", default_validation_case["validation"])
    (WEB_DEMO_DIR / "report.md").write_text(default_case["report"])
    write_json(WEB_DEMO_DIR / "cases.json", case_payload)
    write_json(WEB_DEMO_DIR / "evaluations.json", validation_payload)
    (EXAMPLES_DIR / "sample_report.md").write_text(default_case["report"])
    write_json(ARTIFACTS_DIR / "sample_ledger.json", default_case["ledger"])
    print("Generated web demo assets, example report, and sample ledger.")
    return 0


def bundle_integrity_summary(ledger: dict[str, object], validation: dict[str, object]) -> dict[str, object]:
    audit = ledger["replay_audit"]
    citation_qa = ledger["citation_qa"]
    if not isinstance(audit, dict) or not isinstance(citation_qa, dict):
        raise TypeError("ledger is missing replay audit or citation QA")
    future_source_ids = validation.get("future_source_ids", [])
    if not isinstance(future_source_ids, list):
        future_source_ids = []
    blocked_source_ids = audit.get("blocked_source_ids", [])
    if not isinstance(blocked_source_ids, list):
        blocked_source_ids = []
    return {
        "verified_by_bundle_verify": False,
        "artifact_hashes_ok": None,
        "replay_integrity_ok": bool(
            citation_qa.get("replay_filter_pass") and citation_qa.get("event_time_integrity_pass")
        ),
        "readiness_status": "synthetic_demo_fixture",
        "blocked_future_source_count": len(blocked_source_ids),
        "validation_future_source_count": len(future_source_ids),
        "note": "Synthetic demo fixture. Real-curated replay bundles should pass bundle-verify before sharing or registration.",
    }


if __name__ == "__main__":
    raise SystemExit(main())
