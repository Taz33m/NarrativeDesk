from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from narrativedesk.case_index import validate_case_index
from narrativedesk.evaluation import evaluate_replay, summarize_case_evaluations, validated_narrative_ids
from narrativedesk.pipeline import ledger_export, load_validation_fixture, run_replay
from narrativedesk.replay_bundle import verify_replay_bundle
from narrativedesk.source_pack import assess_real_case_quality, load_source_pack


def assess_public_corpus_quality(
    case_index_path: str | Path,
    *,
    min_cases: int = 6,
    min_unique_tickers: int = 6,
    min_unique_event_types: int = 4,
    min_blocked_future_sources_per_case: int = 1,
    min_top_ranked_validated_rate: float = 1.0,
) -> dict[str, Any]:
    """Assess whether the public corpus is sturdy enough to represent the product."""
    index_path = Path(case_index_path)
    case_index_result = validate_case_index(index_path)
    cases = _case_entries(index_path)
    case_results: list[dict[str, Any]] = []
    case_evaluations: list[dict[str, Any]] = []

    for case in cases:
        case_result, evaluation_row = _assess_case(index_path, case)
        case_results.append(case_result)
        if evaluation_row is not None:
            case_evaluations.append(evaluation_row)

    aggregate = summarize_case_evaluations(case_evaluations)
    tickers = sorted({str(item.get("ticker")) for item in case_results if item.get("ticker")})
    event_types = sorted(
        {str(item.get("event_type")) for item in case_results if item.get("event_type")}
    )
    blocked_counts = [
        int(item.get("blocked_future_source_count", 0))
        for item in case_results
        if item.get("loaded")
    ]
    checks = {
        "case_index_valid": {
            "ok": bool(case_index_result.get("ok")),
            "errors": case_index_result.get("errors", []),
        },
        "minimum_case_count": {
            "ok": len(case_results) >= min_cases,
            "actual": len(case_results),
            "minimum": min_cases,
        },
        "unique_ticker_breadth": {
            "ok": len(tickers) >= min_unique_tickers,
            "actual": len(tickers),
            "minimum": min_unique_tickers,
            "tickers": tickers,
        },
        "unique_event_type_breadth": {
            "ok": len(event_types) >= min_unique_event_types,
            "actual": len(event_types),
            "minimum": min_unique_event_types,
            "event_types": event_types,
        },
        "bundle_verification": {
            "ok": all(bool(item.get("bundle_verified")) for item in case_results),
            "failed_case_ids": [
                str(item.get("case_id"))
                for item in case_results
                if not item.get("bundle_verified")
            ],
        },
        "public_case_quality": {
            "ok": all(bool(item.get("public_quality_ok")) for item in case_results),
            "failed_case_ids": [
                str(item.get("case_id"))
                for item in case_results
                if not item.get("public_quality_ok")
            ],
        },
        "blocked_future_per_case": {
            "ok": (
                bool(blocked_counts)
                and all(count >= min_blocked_future_sources_per_case for count in blocked_counts)
            ),
            "minimum": min_blocked_future_sources_per_case,
            "counts_by_case": {
                str(item.get("case_id")): item.get("blocked_future_source_count")
                for item in case_results
                if item.get("loaded")
            },
        },
        "validated_outcomes": {
            "ok": all(bool(item.get("validated_narrative_ids")) for item in case_results),
            "failed_case_ids": [
                str(item.get("case_id"))
                for item in case_results
                if not item.get("validated_narrative_ids")
            ],
        },
        "aggregate_evaluation": _aggregate_evaluation_check(
            aggregate,
            min_top_ranked_validated_rate=min_top_ranked_validated_rate,
        ),
        "provenance_clean": {
            "ok": (
                aggregate.get("missing_url_count") == 0
                and aggregate.get("missing_content_hash_count") == 0
                and aggregate.get("low_quality_evidence_count") == 0
            ),
            "missing_url_count": aggregate.get("missing_url_count"),
            "missing_content_hash_count": aggregate.get("missing_content_hash_count"),
            "low_quality_evidence_count": aggregate.get("low_quality_evidence_count"),
        },
        "baseline_separation": _baseline_separation_check(aggregate),
    }
    ok = all(bool(check.get("ok")) for check in checks.values())
    return {
        "ok": ok,
        "status": "serious_corpus_ready" if ok else "needs_attention",
        "case_index": str(index_path),
        "checks": checks,
        "metrics": {
            "case_count": len(case_results),
            "unique_ticker_count": len(tickers),
            "unique_event_type_count": len(event_types),
            "tickers": tickers,
            "event_types": event_types,
            "blocked_future_source_count": aggregate.get("blocked_future_source_count", 0),
            "evaluated_case_count": aggregate.get("evaluated_case_count", 0),
            "top_ranked_validated_rate": aggregate.get("top_ranked_validated_rate"),
            "headline_baseline_validated_rate": aggregate.get("headline_baseline_validated_rate"),
            "narrativedesk_tournament_validated_rate": aggregate.get(
                "narrativedesk_tournament_validated_rate"
            ),
        },
        "aggregate": aggregate,
        "cases": case_results,
        "next_action": _next_action(checks),
    }


def _assess_case(
    case_index_path: Path,
    case: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    case_id = str(case.get("case_id", "unknown"))
    event_path = _resolve_case_path(case_index_path, str(case.get("event_fixture", "")))
    validation_path = _resolve_case_path(case_index_path, str(case.get("validation_fixture", "")))
    result: dict[str, Any] = {
        "case_id": case_id,
        "label": case.get("label", case_id),
        "event_fixture": str(event_path),
        "validation_fixture": str(validation_path),
        "loaded": False,
        "bundle_verified": False,
        "public_quality_ok": False,
        "errors": [],
    }
    try:
        event, narratives, audit, _inline_validation = run_replay(event_path)
        validation = load_validation_fixture(validation_path)
        ledger = ledger_export(event, narratives, audit)
        source_pack = load_source_pack(event_path.parent / "source_pack.json")
        bundle_verification = verify_replay_bundle(event_path.parent)
        quality = assess_real_case_quality(
            source_pack,
            require_public_ready=True,
            bundle_verification=bundle_verification,
            validation_fixture=validation,
        )
    except (OSError, ValueError, json.JSONDecodeError, KeyError, TypeError) as exc:
        result["errors"].append(str(exc))
        return result, None

    evaluation = evaluate_replay(narratives, audit, validation).to_dict()
    validated_ids = validated_narrative_ids(validation)
    top_ranked = next((narrative for narrative in narratives if narrative.rank == 1), narratives[0] if narratives else None)
    quality_checks = quality.get("checks", {}) if isinstance(quality.get("checks"), dict) else {}
    public_evidence = (
        quality_checks.get("public_replay_evidence", {})
        if isinstance(quality_checks.get("public_replay_evidence"), dict)
        else {}
    )
    validation_future_source_ids = [
        str(source_id)
        for source_id in validation.get("future_source_ids", [])
        if isinstance(source_id, str)
    ] if isinstance(validation, dict) else []
    result.update(
        {
            "loaded": True,
            "ticker": event.ticker,
            "company_name": event.company_name,
            "event_type": event.event_type,
            "abnormal_return": event.abnormal_return,
            "daily_return": event.daily_return,
            "peer_median_return": event.peer_median_return,
            "winning_narrative_id": top_ranked.narrative_id if top_ranked else None,
            "winning_narrative_title": top_ranked.title if top_ranked else None,
            "bundle_verified": bool(bundle_verification.get("ok")),
            "bundle_status": "verified" if bundle_verification.get("ok") else "failed",
            "public_quality_ok": bool(quality.get("ok")),
            "public_quality_status": quality.get("status"),
            "blocked_future_source_count": len(audit.blocked_source_ids),
            "allowed_source_count": len(audit.allowed_source_ids),
            "non_market_evidence_count": public_evidence.get("actual", 0),
            "publisher_count": public_evidence.get("publisher_actual", 0),
            "publishers": public_evidence.get("publishers", []),
            "source_type_count": public_evidence.get("source_type_actual", 0),
            "source_types": public_evidence.get("source_types", []),
            "validation_source_count": len(validation_future_source_ids),
            "validation_future_source_count": len(validation_future_source_ids),
            "validated_narrative_ids": validated_ids,
            "top_ranked_validated": evaluation.get("top_ranked_validated"),
            "top_ranked_validation_status": _top_ranked_validation_status(
                evaluation.get("top_ranked_validated")
            ),
            "citation_qa_pass": ledger["citation_qa"].get("citation_qa_pass"),
        }
    )
    if not bundle_verification.get("ok"):
        result["errors"].extend(str(error) for error in bundle_verification.get("errors", []))
    if not quality.get("ok"):
        for check_name, check in quality.get("checks", {}).items():
            if isinstance(check, dict) and not check.get("ok"):
                result["errors"].append(f"{check_name} failed")

    evaluation_row = {
        "case_id": case_id,
        "label": case.get("label", case_id),
        "ticker": event.ticker,
        "evaluation": evaluation,
        "citation_qa": ledger["citation_qa"],
        "source_reliability": ledger["source_reliability"],
        "source_clustering": ledger["source_clustering"],
    }
    return result, evaluation_row


def _top_ranked_validation_status(value: Any) -> str:
    if value is True:
        return "validated"
    if value is False:
        return "miss"
    return "pending"


def _aggregate_evaluation_check(
    aggregate: dict[str, Any],
    *,
    min_top_ranked_validated_rate: float,
) -> dict[str, Any]:
    errors = []
    required_full_pass_rates = [
        "citation_qa_pass_rate",
        "provenance_ready_rate",
        "replay_filter_pass_rate",
        "support_coverage_pass_rate",
    ]
    for rate_key in required_full_pass_rates:
        if aggregate.get(rate_key) != 1:
            errors.append(f"{rate_key} must be 1.0")
    top_ranked_rate = aggregate.get("top_ranked_validated_rate")
    if top_ranked_rate is None or float(top_ranked_rate) < min_top_ranked_validated_rate:
        errors.append("top_ranked_validated_rate below required threshold")
    return {
        "ok": not errors,
        "errors": errors,
        "minimum_top_ranked_validated_rate": min_top_ranked_validated_rate,
        "top_ranked_validated_rate": top_ranked_rate,
        "citation_qa_pass_rate": aggregate.get("citation_qa_pass_rate"),
        "provenance_ready_rate": aggregate.get("provenance_ready_rate"),
        "replay_filter_pass_rate": aggregate.get("replay_filter_pass_rate"),
        "support_coverage_pass_rate": aggregate.get("support_coverage_pass_rate"),
    }


def _baseline_separation_check(aggregate: dict[str, Any]) -> dict[str, Any]:
    tournament_rate = aggregate.get("narrativedesk_tournament_validated_rate")
    baseline_rate = aggregate.get("headline_baseline_validated_rate")
    ok = (
        tournament_rate is not None
        and baseline_rate is not None
        and float(tournament_rate) > float(baseline_rate)
    )
    return {
        "ok": ok,
        "narrativedesk_tournament_validated_rate": tournament_rate,
        "headline_baseline_validated_rate": baseline_rate,
        "errors": [] if ok else ["NarrativeDesk tournament must beat the headline baseline"],
    }


def _case_entries(case_index_path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(case_index_path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    cases = payload.get("cases", [])
    return [case for case in cases if isinstance(case, dict)] if isinstance(cases, list) else []


def _resolve_case_path(case_index_path: Path, fixture_path: str) -> Path:
    path = Path(fixture_path)
    if path.is_absolute():
        return path
    if path.exists():
        return path
    return case_index_path.parent / path


def _next_action(checks: dict[str, dict[str, Any]]) -> str:
    if not checks["case_index_valid"]["ok"]:
        return "Fix the public case index before judging corpus quality."
    if not checks["minimum_case_count"]["ok"]:
        return "Add more verified public replay cases before positioning this as serious."
    if not checks["unique_ticker_breadth"]["ok"]:
        return "Add cases from more distinct tickers to avoid single-name demo bias."
    if not checks["unique_event_type_breadth"]["ok"]:
        return "Add replay cases from more than one event type before positioning this as serious."
    if not checks["bundle_verification"]["ok"]:
        return "Rebuild or remove public cases that do not pass bundle verification."
    if not checks["public_case_quality"]["ok"]:
        return "Fix public-ready case quality failures before publishing the corpus."
    if not checks["aggregate_evaluation"]["ok"]:
        return "Improve replay, validation, or citation quality until aggregate checks pass."
    if not checks["baseline_separation"]["ok"]:
        return "Add cases where the verification tournament beats surface-level baselines."
    return "Public corpus gate passed; keep adding cases only when they clear the same bar."
