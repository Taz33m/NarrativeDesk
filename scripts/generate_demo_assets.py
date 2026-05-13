from __future__ import annotations

import json
from pathlib import Path

from narrativedesk.corpus_quality import assess_public_corpus_quality
from narrativedesk.evaluation import evaluate_replay, summarize_case_evaluations
from narrativedesk.pipeline import ledger_export, load_event_fixture, load_validation_fixture, run_replay
from narrativedesk.report import generate_markdown_report
from narrativedesk.replay_bundle import verify_replay_bundle

ROOT_DIR = Path(__file__).resolve().parents[1]
SYNTHETIC_CASE_INDEX_FIXTURE = ROOT_DIR / "data" / "fixtures" / "case_index.json"
PUBLIC_CASE_INDEX_FIXTURE = ROOT_DIR / "data" / "fixtures" / "public_case_index.json"
WEB_DEMO_DIR = ROOT_DIR / "apps" / "web" / "public" / "demo"
EXAMPLES_DIR = ROOT_DIR / "examples"
ARTIFACTS_DIR = ROOT_DIR / "artifacts"


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def resolve_fixture_path(case_index_path: Path, fixture_path: str) -> Path:
    path = Path(fixture_path)
    if path.is_absolute():
        return path
    root_relative = ROOT_DIR / path
    if root_relative.exists():
        return root_relative
    return case_index_path.parent / path


def main() -> int:
    case_index_path = PUBLIC_CASE_INDEX_FIXTURE if PUBLIC_CASE_INDEX_FIXTURE.exists() else SYNTHETIC_CASE_INDEX_FIXTURE
    case_index = json.loads(case_index_path.read_text())
    case_payload = {"default_case_id": case_index["default_case_id"], "cases": []}
    validation_payload = {"default_case_id": case_index["default_case_id"], "cases": []}
    case_evaluations = []
    for case in case_index["cases"]:
        event_fixture_path = resolve_fixture_path(case_index_path, case["event_fixture"])
        validation_fixture_path = resolve_fixture_path(case_index_path, case["validation_fixture"])
        event, narratives, audit, _validation = run_replay(event_fixture_path)
        validation = load_validation_fixture(validation_fixture_path)
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
            "bundle_integrity": bundle_integrity_summary(ledger, validation, event_fixture_path),
        })
        validation_payload["cases"].append({
            "case_id": case["case_id"],
            "label": case["label"],
            "validation": validation,
            "evaluation": evaluation,
        })
    validation_payload["aggregate"] = summarize_case_evaluations(case_evaluations)
    if case_index_path == PUBLIC_CASE_INDEX_FIXTURE:
        case_payload["corpus_quality"] = corpus_quality_summary(
            assess_public_corpus_quality(case_index_path)
        )

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


def bundle_integrity_summary(
    ledger: dict[str, object],
    validation: dict[str, object],
    event_fixture_path: Path,
) -> dict[str, object]:
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
    bundle_dir = event_fixture_path.parent
    if (bundle_dir / "manifest.json").exists():
        verification = verify_replay_bundle(bundle_dir)
        manifest = json.loads((bundle_dir / "manifest.json").read_text())
        checks = verification.get("checks", {})
        artifacts_ok = bool(
            isinstance(checks, dict)
            and checks.get("artifacts", {}).get("ok")
            and checks.get("manifest", {}).get("ok")
        )
        replay_integrity_ok = bool(
            isinstance(checks, dict)
            and checks.get("replay_integrity", {}).get("ok")
            and checks.get("replay", {}).get("ok")
        )
        return {
            "verified_by_bundle_verify": bool(verification.get("ok")),
            "artifact_hashes_ok": artifacts_ok,
            "replay_integrity_ok": replay_integrity_ok,
            "readiness_status": str(manifest.get("readiness_status", "unknown")),
            "blocked_future_source_count": len(blocked_source_ids),
            "validation_future_source_count": len(future_source_ids),
            "note": "Real-curated replay bundle verified from timestamped, replay-locked source artifacts.",
        }
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


def corpus_quality_summary(result: dict[str, object]) -> dict[str, object]:
    checks = result.get("checks", {})
    if not isinstance(checks, dict):
        checks = {}
    exposed_checks = [
        "minimum_case_count",
        "unique_ticker_breadth",
        "unique_event_type_breadth",
        "bundle_verification",
        "public_case_quality",
        "blocked_future_per_case",
        "aggregate_evaluation",
        "provenance_clean",
        "baseline_separation",
    ]
    return {
        "ok": bool(result.get("ok")),
        "status": str(result.get("status", "unknown")),
        "metrics": result.get("metrics", {}),
        "cases": [
            _public_case_quality_summary(case)
            for case in result.get("cases", [])
            if isinstance(case, dict)
        ],
        "checks": {
            check_name: _public_check_summary(checks.get(check_name))
            for check_name in exposed_checks
        },
        "next_action": str(result.get("next_action", "")),
    }


def _public_check_summary(check: object) -> dict[str, object]:
    if not isinstance(check, dict):
        return {"ok": False}
    summary: dict[str, object] = {"ok": bool(check.get("ok"))}
    for key in [
        "actual",
        "minimum",
        "tickers",
        "event_types",
        "failed_case_ids",
        "missing_url_count",
        "missing_content_hash_count",
        "low_quality_evidence_count",
        "top_ranked_validated_rate",
        "narrativedesk_tournament_validated_rate",
        "headline_baseline_validated_rate",
        "counts_by_case",
        "errors",
    ]:
        if key in check:
            summary[key] = check[key]
    return summary


def _public_case_quality_summary(case: dict[str, object]) -> dict[str, object]:
    return {
        "case_id": case.get("case_id"),
        "ticker": case.get("ticker"),
        "company_name": case.get("company_name"),
        "event_type": case.get("event_type"),
        "winning_narrative_id": case.get("winning_narrative_id"),
        "winning_narrative_title": case.get("winning_narrative_title"),
        "abnormal_return": case.get("abnormal_return"),
        "allowed_source_count": case.get("allowed_source_count", 0),
        "blocked_future_source_count": case.get("blocked_future_source_count", 0),
        "bundle_verified": bool(case.get("bundle_verified")),
        "bundle_status": case.get("bundle_status", "unknown"),
        "public_quality_ok": bool(case.get("public_quality_ok")),
        "public_quality_status": case.get("public_quality_status", "unknown"),
        "top_ranked_validated": case.get("top_ranked_validated"),
        "top_ranked_validation_status": case.get("top_ranked_validation_status", "pending"),
        "validation_source_count": case.get("validation_source_count", 0),
        "non_market_evidence_count": case.get("non_market_evidence_count", 0),
        "publisher_count": case.get("publisher_count", 0),
        "source_type_count": case.get("source_type_count", 0),
        "publishers": case.get("publishers", []),
        "source_types": case.get("source_types", []),
    }


if __name__ == "__main__":
    raise SystemExit(main())
