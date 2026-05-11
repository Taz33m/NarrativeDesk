from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Any

from narrativedesk.market import compute_event_market_metrics
from narrativedesk.models import parse_datetime

REQUIRED_SOURCE_FIELDS = {
    "source_id",
    "source_type",
    "publisher",
    "title",
    "url",
    "published_at",
    "retrieved_at",
    "content_hash",
    "availability_status",
    "originality_score",
    "independence_cluster_id",
    "claim_extracted",
    "supported_narrative_ids",
    "contradicted_narrative_ids",
}
ALLOWED_AVAILABILITY_STATUSES = {"allowed", "blocked_future", "unavailable", "placeholder"}
ALLOWED_DIRECTIONS = {"bullish", "bearish", "neutral", "mixed"}
HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
DEMO_READY_VALIDATION_LABELS = {"validated", "invalidated"}
SOURCE_HASH_TEXT_FIELDS = ("document_text", "raw_text", "claim_extracted")
REQUIRED_NARRATIVE_FIELDS = {
    "narrative_id",
    "title",
    "narrative",
    "mechanism",
    "directional_implication",
    "time_horizon",
    "expected_observables",
    "scoring_inputs",
}
REQUIRED_SCORING_FIELDS = {
    "evidence_strength",
    "mechanism_specificity",
    "source_independence",
    "cross_sectional_fit",
    "contradiction_resistance",
    "timestamp_advantage",
    "forward_observable_quality",
    "crowding_risk",
    "unsupported_claim_penalty",
}
SOURCE_SCORE_FIELDS = (
    "originality_score",
    "support_strength",
    "evidence_quality",
    "independence",
    "incentive_conflict",
)
OPTIONAL_SOURCE_FIELDS = {
    "claim",
    "document_text",
    "raw_text",
    *SOURCE_SCORE_FIELDS,
}
PUBLIC_SOURCE_FIELDS = REQUIRED_SOURCE_FIELDS | OPTIONAL_SOURCE_FIELDS
SENSITIVE_SOURCE_EXTRA_PATTERNS = (
    "authorization",
    "cookie",
    "header",
    "key",
    "password",
    "secret",
    "token",
)
PLACEHOLDER_URLS = {"", "https://...", "http://..."}


def load_source_pack(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def validate_source_pack(payload: dict[str, Any], *, require_narratives: bool = False) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["source pack must be an object"]

    for forbidden_key in ["validation", "validation_rows"]:
        if forbidden_key in payload:
            errors.append(f"{forbidden_key} must stay in a separate validation fixture")

    meta = payload.get("case_metadata", {})
    if not isinstance(meta, dict):
        errors.append("case_metadata must be an object")
        meta = {}
    for field in ["case_id", "ticker", "company_name", "event_timestamp", "data_provenance_mode"]:
        if not meta.get(field):
            errors.append(f"case_metadata.{field} is required")

    event_timestamp = None
    if meta.get("event_timestamp"):
        try:
            event_timestamp = parse_datetime(meta["event_timestamp"])
        except ValueError:
            errors.append("case_metadata.event_timestamp must be an ISO timestamp")
        else:
            if not _has_timezone_offset(event_timestamp):
                errors.append("case_metadata.event_timestamp must include a timezone offset")
                event_timestamp = None

    if meta.get("data_provenance_mode") not in {None, "synthetic", "real-curated"}:
        errors.append("case_metadata.data_provenance_mode must be synthetic or real-curated")

    if payload.get("market_snapshot"):
        try:
            compute_event_market_metrics(payload["market_snapshot"], replay_timestamp=meta.get("event_timestamp"))
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"market_snapshot invalid: {exc}")

    sources = payload.get("sources", [])
    if not isinstance(sources, list) or not sources:
        errors.append("sources must be a non-empty list")
        return errors

    seen_source_ids: set[str] = set()
    narrative_ids = _narrative_ids(payload)
    for idx, source in enumerate(sources):
        if not isinstance(source, dict):
            errors.append(f"sources[{idx}] must be an object")
            continue

        unknown_fields = sorted(set(source) - PUBLIC_SOURCE_FIELDS)
        if unknown_fields:
            errors.append(f"sources[{idx}] has unsupported public fields: {', '.join(unknown_fields)}")
        sensitive_unknown = [
            field
            for field in unknown_fields
            if any(pattern in field.lower() for pattern in SENSITIVE_SOURCE_EXTRA_PATTERNS)
        ]
        if sensitive_unknown:
            errors.append(
                f"sources[{idx}] has secret-like unsupported fields: {', '.join(sensitive_unknown)}"
            )

        missing = sorted(REQUIRED_SOURCE_FIELDS - set(source.keys()))
        if missing:
            errors.append(f"sources[{idx}] missing required fields: {', '.join(missing)}")
            continue

        source_id = source.get("source_id")
        if source_id in seen_source_ids:
            errors.append(f"sources[{idx}].source_id duplicates {source_id}")
        seen_source_ids.add(source_id)

        status = source.get("availability_status")
        if status not in ALLOWED_AVAILABILITY_STATUSES:
            errors.append(f"sources[{idx}].availability_status invalid")

        hash_shape_ok = bool(HASH_PATTERN.match(str(source.get("content_hash", ""))))
        if not hash_shape_ok:
            errors.append(f"sources[{idx}].content_hash must be sha256:<64 lowercase hex chars>")
        elif meta.get("data_provenance_mode") == "real-curated":
            hash_field, hash_text = _source_hash_text(source)
            expected_hash = source_content_hash(hash_text)
            if source["content_hash"] != expected_hash:
                errors.append(f"sources[{idx}].content_hash does not match {hash_field}")

        try:
            published_at = parse_datetime(source["published_at"])
        except ValueError:
            errors.append(f"sources[{idx}].published_at must be an ISO timestamp")
            published_at = None
        else:
            if not _has_timezone_offset(published_at):
                errors.append(f"sources[{idx}].published_at must include a timezone offset")
                published_at = None

        try:
            retrieved_at = parse_datetime(source["retrieved_at"])
        except ValueError:
            errors.append(f"sources[{idx}].retrieved_at must be an ISO timestamp")
            retrieved_at = None
        else:
            if not _has_timezone_offset(retrieved_at):
                errors.append(f"sources[{idx}].retrieved_at must include a timezone offset")
                retrieved_at = None

        if published_at and retrieved_at and retrieved_at < published_at:
            errors.append(f"sources[{idx}].retrieved_at cannot be before published_at")

        if event_timestamp and published_at and status == "allowed" and published_at > event_timestamp:
            errors.append(f"sources[{idx}].availability_status must be blocked_future after event_timestamp")
        if event_timestamp and published_at and status == "blocked_future" and published_at <= event_timestamp:
            errors.append(f"sources[{idx}].availability_status cannot be blocked_future before event_timestamp")

        for list_field in ["supported_narrative_ids", "contradicted_narrative_ids"]:
            if not isinstance(source.get(list_field), list):
                errors.append(f"sources[{idx}].{list_field} must be a list")
                continue
            if status in {"unavailable", "placeholder"} and source[list_field]:
                errors.append(f"sources[{idx}].{list_field} cannot link {status} sources")
            if narrative_ids:
                reference_ids = {str(item) for item in source[list_field]}
                unknown_ids = sorted(reference_ids - narrative_ids)
                if unknown_ids:
                    errors.append(
                        f"sources[{idx}].{list_field} references unknown narrative IDs: {', '.join(unknown_ids)}"
                    )

        for score_key in SOURCE_SCORE_FIELDS:
            if score_key in source and not _is_score01(source[score_key]):
                errors.append(f"sources[{idx}].{score_key} must be a number from 0 to 1")
    errors.extend(_validate_narratives(payload, require_narratives=require_narratives))
    if require_narratives:
        errors.extend(_validate_ingestion_links(payload))
    return errors


def source_content_hash(claim_extracted: str) -> str:
    return f"sha256:{sha256(claim_extracted.encode('utf-8')).hexdigest()}"


def sanitize_source_record(source: dict[str, Any]) -> dict[str, Any]:
    return {key: source[key] for key in sorted(PUBLIC_SOURCE_FIELDS) if key in source}


def sanitize_source_pack_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(payload)
    sources = payload.get("sources", [])
    if isinstance(sources, list):
        sanitized["sources"] = [
            sanitize_source_record(source) if isinstance(source, dict) else source
            for source in sources
        ]
    return sanitized


def _source_hash_text(source: dict[str, Any]) -> tuple[str, str]:
    for field in SOURCE_HASH_TEXT_FIELDS:
        value = source.get(field)
        if isinstance(value, str) and value:
            return field, value
    return "claim_extracted", str(source.get("claim_extracted", ""))


def _has_timezone_offset(value: Any) -> bool:
    return bool(getattr(value, "tzinfo", None) and value.utcoffset() is not None)


def _is_score01(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and 0 <= value <= 1


def preview_source_pack(payload: dict[str, Any]) -> dict[str, Any]:
    meta = payload["case_metadata"]
    sources = payload.get("sources", [])
    narratives = payload.get("narratives", [])
    allowed = [s for s in sources if s.get("availability_status") == "allowed"]
    blocked = [s for s in sources if s.get("availability_status") == "blocked_future"]
    source_type_counts: dict[str, int] = {}
    for source in sources:
        source_type = str(source.get("source_type", "unknown"))
        source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1
    return {
        "case_id": meta["case_id"],
        "ticker": meta["ticker"],
        "provenance_mode": meta["data_provenance_mode"],
        "source_counts": {
            "total": len(sources),
            "allowed": len(allowed),
            "blocked_future": len(blocked),
        },
        "narrative_count": len(narratives) if isinstance(narratives, list) else 0,
        "source_ids": [s["source_id"] for s in sources],
        "allowed_source_ids": [s["source_id"] for s in allowed],
        "blocked_future_source_ids": [s["source_id"] for s in blocked],
        "source_type_counts": dict(sorted(source_type_counts.items())),
    }


def assess_source_pack_readiness(payload: dict[str, Any]) -> dict[str, Any]:
    preview_errors = validate_source_pack(payload)
    ingestion_errors = validate_source_pack(payload, require_narratives=True)
    meta = payload.get("case_metadata", {}) if isinstance(payload, dict) else {}
    if not isinstance(meta, dict):
        meta = {}

    checks = {
        "preview_valid": {
            "ok": not preview_errors,
            "errors": preview_errors,
        },
        "ingestion_ready": {
            "ok": not ingestion_errors,
            "errors": ingestion_errors,
        },
        "replay_safe": _readiness_replay_check(payload, meta),
        "provenance_ready": _readiness_provenance_check(payload, meta),
        "narrative_linkage": _readiness_linkage_check(payload),
    }
    ok = all(check["ok"] for check in checks.values())
    result: dict[str, Any] = {
        "ok": ok,
        "status": "ready_to_ingest" if ok else "needs_attention",
        "case_id": meta.get("case_id"),
        "ticker": meta.get("ticker"),
        "checks": checks,
    }
    if not preview_errors:
        result["preview"] = preview_source_pack(payload)
    return result


def assess_real_case_quality(
    payload: dict[str, Any],
    *,
    min_narratives: int = 3,
    max_narratives: int = 5,
    min_allowed_sources: int = 5,
    min_blocked_future_sources: int = 1,
    min_contradictions: int = 1,
    require_demo_ready: bool = False,
    min_linked_allowed_sources: int = 5,
    min_source_types: int = 2,
    min_publishers: int = 2,
    min_validation_outcomes: int = 1,
    require_public_ready: bool = False,
    bundle_verification: dict[str, Any] | None = None,
    validation_fixture: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assess whether a real-curated case clears private or public proof thresholds."""
    require_demo_ready = require_demo_ready or require_public_ready
    readiness = assess_source_pack_readiness(payload)
    meta = payload.get("case_metadata", {}) if isinstance(payload, dict) else {}
    if not isinstance(meta, dict):
        meta = {}

    sources = _source_items(payload)
    allowed_sources = [source for source in sources if source.get("availability_status") == "allowed"]
    blocked_future_sources = [
        source for source in sources if source.get("availability_status") == "blocked_future"
    ]
    narratives = [item for item in payload.get("narratives", []) if isinstance(item, dict)]
    allowed_source_ids = {str(source.get("source_id")) for source in allowed_sources}
    allowed_supported_ids = {
        str(source.get("source_id"))
        for source in allowed_sources
        if source.get("supported_narrative_ids")
    }
    allowed_contradiction_ids = {
        str(source.get("source_id"))
        for source in allowed_sources
        if source.get("contradicted_narrative_ids")
    }
    linked_allowed_sources = [
        source
        for source in allowed_sources
        if source.get("supported_narrative_ids") or source.get("contradicted_narrative_ids")
    ]
    linked_allowed_ids = {str(source.get("source_id")) for source in linked_allowed_sources}
    linked_source_types = _distinct_nonempty(source.get("source_type") for source in linked_allowed_sources)
    linked_publishers = _distinct_nonempty(source.get("publisher") for source in linked_allowed_sources)
    supported_by_narrative: dict[str, list[str]] = {}
    for narrative in narratives:
        narrative_id = str(narrative.get("narrative_id", "unknown"))
        supported_by_narrative[narrative_id] = [
            str(source.get("source_id"))
            for source in allowed_sources
            if narrative_id in source.get("supported_narrative_ids", [])
        ]
    narratives_without_allowed_support = sorted(
        narrative_id for narrative_id, source_ids in supported_by_narrative.items() if not source_ids
    )

    validation_future_source_ids = _validation_future_source_ids(validation_fixture)
    validation_future_source_count = len(validation_future_source_ids)
    if validation_fixture is None:
        validation_future_source_count = len(blocked_future_sources)
        validation_future_source_ids = [str(source.get("source_id")) for source in blocked_future_sources]
    validation_outcome_rows = _validation_outcome_rows(validation_fixture)
    public_evidence = _public_replay_evidence_check(linked_allowed_sources)
    public_validation = _public_validation_linkage_check(validation_outcome_rows)
    demo_market_context = _demo_market_context_check(payload, meta)

    checks: dict[str, dict[str, Any]] = {
        "source_pack_ready": {
            "ok": bool(readiness.get("ok")),
            "status": readiness.get("status"),
            "errors": _readiness_errors_for_quality(readiness),
        },
        "real_curated_provenance": {
            "ok": meta.get("data_provenance_mode") == "real-curated",
            "actual": meta.get("data_provenance_mode"),
        },
        "case_identity": {
            "ok": all(meta.get(field) for field in ["case_id", "ticker", "event_timestamp"]),
            "case_id": meta.get("case_id"),
            "ticker": meta.get("ticker"),
            "event_timestamp": meta.get("event_timestamp"),
        },
        "market_snapshot": {
            "ok": bool(payload.get("market_snapshot")),
            "present": bool(payload.get("market_snapshot")),
        },
        "narrative_count": {
            "ok": min_narratives <= len(narratives) <= max_narratives,
            "actual": len(narratives),
            "minimum": min_narratives,
            "maximum": max_narratives,
        },
        "replay_time_sources": {
            "ok": len(allowed_sources) >= min_allowed_sources,
            "actual": len(allowed_sources),
            "minimum": min_allowed_sources,
            "source_ids": sorted(allowed_source_ids),
        },
        "blocked_future_sources": {
            "ok": len(blocked_future_sources) >= min_blocked_future_sources,
            "actual": len(blocked_future_sources),
            "minimum": min_blocked_future_sources,
            "source_ids": sorted(str(source.get("source_id")) for source in blocked_future_sources),
        },
        "contradiction_links": {
            "ok": len(allowed_contradiction_ids) >= min_contradictions,
            "actual": len(allowed_contradiction_ids),
            "minimum": min_contradictions,
            "source_ids": sorted(allowed_contradiction_ids),
        },
        "narrative_allowed_support": {
            "ok": not narratives_without_allowed_support and bool(narratives),
            "narratives_without_allowed_support": narratives_without_allowed_support,
            "supported_by_narrative": supported_by_narrative,
        },
        "validation_future_sources": {
            "ok": validation_future_source_count >= min_blocked_future_sources,
            "actual": validation_future_source_count,
            "minimum": min_blocked_future_sources,
            "source_ids": sorted(validation_future_source_ids),
        },
    }
    if require_demo_ready:
        checks.update(
            {
                "demo_market_context": demo_market_context,
                "linked_replay_time_sources": {
                    "ok": len(linked_allowed_sources) >= min_linked_allowed_sources,
                    "actual": len(linked_allowed_sources),
                    "minimum": min_linked_allowed_sources,
                    "source_ids": sorted(linked_allowed_ids),
                },
                "source_type_diversity": {
                    "ok": len(linked_source_types) >= min_source_types,
                    "actual": len(linked_source_types),
                    "minimum": min_source_types,
                    "source_types": linked_source_types,
                },
                "publisher_diversity": {
                    "ok": len(linked_publishers) >= min_publishers,
                    "actual": len(linked_publishers),
                    "minimum": min_publishers,
                    "publishers": linked_publishers,
                },
                "validation_outcomes": {
                    "ok": len(validation_outcome_rows) >= min_validation_outcomes,
                    "actual": len(validation_outcome_rows),
                    "minimum": min_validation_outcomes,
                    "accepted_labels": sorted(DEMO_READY_VALIDATION_LABELS),
                    "rows": validation_outcome_rows,
                },
            }
        )
    if require_public_ready:
        checks.update(
            {
                "public_replay_evidence": public_evidence,
                "public_validation_evidence": public_validation,
            }
        )
    if bundle_verification is not None:
        checks["bundle_verified"] = {
            "ok": bool(bundle_verification.get("ok")),
            "artifact_count": bundle_verification.get("artifact_count", 0),
            "errors": bundle_verification.get("errors", []),
        }

    ok = all(check["ok"] for check in checks.values())
    status = "quality_ready"
    if require_demo_ready:
        status = "demo_ready"
    if require_public_ready:
        status = "public_demo_ready"
    if not ok:
        status = "needs_curation"
    metrics = {
        "narrative_count": len(narratives),
        "allowed_source_count": len(allowed_sources),
        "blocked_future_source_count": len(blocked_future_sources),
        "allowed_support_source_count": len(allowed_supported_ids),
        "allowed_contradiction_source_count": len(allowed_contradiction_ids),
        "linked_allowed_source_count": len(linked_allowed_sources),
        "linked_source_type_count": len(linked_source_types),
        "linked_publisher_count": len(linked_publishers),
        "public_replay_source_count": public_evidence["actual"],
        "public_non_sec_replay_source_count": public_evidence["non_sec_actual"],
        "public_replay_source_type_count": public_evidence["source_type_actual"],
        "public_replay_publisher_count": public_evidence["publisher_actual"],
        "validation_future_source_count": validation_future_source_count,
        "validation_outcome_count": len(validation_outcome_rows),
        "validation_outcome_with_source_count": public_validation["actual"],
    }
    return {
        "ok": ok,
        "status": status,
        "gate": "public_demo" if require_public_ready else "demo" if require_demo_ready else "quality",
        "case_id": meta.get("case_id"),
        "ticker": meta.get("ticker"),
        "checks": checks,
        "metrics": metrics,
        "readiness": readiness,
        "next_action": _quality_next_action(checks),
    }


def _readiness_errors_for_quality(readiness: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    checks = readiness.get("checks", {})
    if not isinstance(checks, dict):
        return ["source-pack readiness checks are unavailable"]
    for name, check in checks.items():
        if isinstance(check, dict) and not check.get("ok"):
            for error in check.get("errors", []):
                errors.append(f"{name}: {error}")
    return errors


def _validation_future_source_ids(validation_fixture: dict[str, Any] | None) -> list[str]:
    if not isinstance(validation_fixture, dict):
        return []
    explicit_ids = validation_fixture.get("future_source_ids", [])
    if isinstance(explicit_ids, list):
        return [str(item) for item in explicit_ids]
    return []


def _validation_outcome_rows(validation_fixture: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(validation_fixture, dict):
        return []
    rows = validation_fixture.get("rows", [])
    if not isinstance(rows, list):
        return []
    outcome_rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label", ""))
        if label not in DEMO_READY_VALIDATION_LABELS:
            continue
        outcome_rows.append(
            {
                "window": str(row.get("window", "")),
                "label": label,
                "narrative_id": str(row.get("narrative_id", "")),
                "future_source_ids": [str(item) for item in row.get("future_source_ids", [])]
                if isinstance(row.get("future_source_ids"), list)
                else [],
            }
        )
    return outcome_rows


def _public_replay_evidence_check(linked_allowed_sources: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_sources = [
        source
        for source in linked_allowed_sources
        if str(source.get("source_type", "")).strip() != "market_data"
        and str(source.get("publisher", "")).strip() != "Frozen market bars"
    ]
    non_sec_sources = [
        source
        for source in evidence_sources
        if str(source.get("publisher", "")).strip() != "SEC EDGAR"
    ]
    source_types = _distinct_nonempty(source.get("source_type") for source in evidence_sources)
    publishers = _distinct_nonempty(source.get("publisher") for source in evidence_sources)
    source_ids = sorted(str(source.get("source_id")) for source in evidence_sources)
    non_sec_source_ids = sorted(str(source.get("source_id")) for source in non_sec_sources)
    min_sources = 2
    min_non_sec_sources = 2
    min_source_types = 2
    min_publishers = 2
    errors = []
    if len(evidence_sources) < min_sources:
        errors.append("not enough linked non-market replay-time evidence sources")
    if len(non_sec_sources) < min_non_sec_sources:
        errors.append("not enough linked non-SEC replay-time evidence sources")
    if len(source_types) < min_source_types:
        errors.append("not enough non-market replay-time source type diversity")
    if len(publishers) < min_publishers:
        errors.append("not enough non-market replay-time publisher diversity")
    return {
        "ok": not errors,
        "actual": len(evidence_sources),
        "minimum": min_sources,
        "source_ids": source_ids,
        "non_sec_actual": len(non_sec_sources),
        "non_sec_minimum": min_non_sec_sources,
        "non_sec_source_ids": non_sec_source_ids,
        "source_type_actual": len(source_types),
        "source_type_minimum": min_source_types,
        "source_types": source_types,
        "publisher_actual": len(publishers),
        "publisher_minimum": min_publishers,
        "publishers": publishers,
        "errors": errors,
    }


def _public_validation_linkage_check(validation_outcome_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows_with_sources = [
        row
        for row in validation_outcome_rows
        if isinstance(row.get("future_source_ids"), list) and row.get("future_source_ids")
    ]
    return {
        "ok": bool(rows_with_sources),
        "actual": len(rows_with_sources),
        "minimum": 1,
        "rows": rows_with_sources,
        "errors": [] if rows_with_sources else ["validation outcomes need linked held-out future sources"],
    }


def _demo_market_context_check(payload: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    snapshot = payload.get("market_snapshot") if isinstance(payload, dict) else None
    errors: list[str] = []
    metrics: dict[str, float | None] = {}
    if not isinstance(snapshot, dict):
        return {
            "ok": False,
            "errors": ["market_snapshot is required"],
            "event_bar_present": False,
            "peer_bar_count": 0,
            "metrics": metrics,
        }

    event_bar = snapshot.get("event_bar")
    peer_bars = snapshot.get("peer_bars", [])
    peer_bar_count = len(peer_bars) if isinstance(peer_bars, list) else 0
    event_bar_as_of = _market_bar_reference_time(event_bar) if isinstance(event_bar, dict) else None
    latest_evidence_at = _latest_linked_replay_evidence_time(payload)
    if not isinstance(event_bar, dict):
        errors.append("event_bar is required")
    if peer_bar_count == 0:
        errors.append("peer_bars are required so abnormal return is measurable")
    try:
        metrics = compute_event_market_metrics(snapshot, replay_timestamp=meta.get("event_timestamp"))
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"market metrics are not computable: {exc}")
    else:
        if metrics.get("daily_return") is None:
            errors.append("daily_return is not computable")
        if metrics.get("peer_median_return") is None:
            errors.append("peer_median_return is not computable")
        if metrics.get("abnormal_return") is None:
            errors.append("abnormal_return is not computable")
    if latest_evidence_at is not None:
        if event_bar_as_of is None:
            errors.append("event_bar must include a timestamp or as_of for public demo market context")
        elif event_bar_as_of < latest_evidence_at:
            errors.append(
                "event_bar is stale relative to latest linked replay-time evidence; "
                "use intraday or replay-lock market bars"
            )

    return {
        "ok": not errors,
        "errors": errors,
        "event_bar_present": isinstance(event_bar, dict),
        "peer_bar_count": peer_bar_count,
        "sector_bar_present": isinstance(snapshot.get("sector_bar"), dict),
        "event_bar_as_of": event_bar_as_of.isoformat() if event_bar_as_of is not None else None,
        "latest_linked_evidence_at": latest_evidence_at.isoformat() if latest_evidence_at is not None else None,
        "post_evidence_bar_present": (
            event_bar_as_of is not None
            and latest_evidence_at is not None
            and event_bar_as_of >= latest_evidence_at
        )
        if latest_evidence_at is not None
        else None,
        "metrics": metrics,
    }


def _market_bar_reference_time(bar: dict[str, Any]) -> Any:
    for field in ("as_of", "timestamp"):
        if not bar.get(field):
            continue
        try:
            return parse_datetime(str(bar[field]))
        except ValueError:
            return None
    return None


def _latest_linked_replay_evidence_time(payload: dict[str, Any]) -> Any:
    sources = _source_items(payload)
    timestamps = []
    for source in sources:
        if source.get("availability_status") != "allowed":
            continue
        if str(source.get("source_type", "")).strip() == "market_data":
            continue
        if not source.get("supported_narrative_ids") and not source.get("contradicted_narrative_ids"):
            continue
        try:
            timestamps.append(parse_datetime(str(source.get("published_at"))))
        except ValueError:
            continue
    return max(timestamps) if timestamps else None


def _distinct_nonempty(values: Any) -> list[str]:
    return sorted(
        {
            str(value).strip()
            for value in values
            if str(value or "").strip() and str(value).strip().lower() != "unknown"
        }
    )


def _quality_next_action(checks: dict[str, dict[str, Any]]) -> str:
    if checks.get("bundle_verified", {}).get("ok") is False:
        return "Rebuild or inspect the replay bundle until bundle verification passes."
    if checks["source_pack_ready"]["ok"] is False:
        return "Fix source-pack readiness errors before judging demo quality."
    if checks["market_snapshot"]["ok"] is False:
        return "Add a market snapshot so the abnormal move is measurable."
    if checks["narrative_count"]["ok"] is False:
        return "Curate 3-5 competing narratives for this real event."
    if checks["replay_time_sources"]["ok"] is False:
        return "Add more timestamped replay-time sources with stable provenance."
    if checks["blocked_future_sources"]["ok"] is False:
        return "Add at least one post-lock source as blocked future validation evidence."
    if checks["contradiction_links"]["ok"] is False:
        return "Link at least one replay-time contradiction to a curated narrative."
    if checks["narrative_allowed_support"]["ok"] is False:
        return "Give every narrative at least one replay-safe supporting source."
    if checks["validation_future_sources"]["ok"] is False:
        return "Keep future validation evidence separate from replay-time ranking inputs."
    if checks["real_curated_provenance"]["ok"] is False:
        return "Use real-curated provenance mode before treating this as a real replay candidate."
    if checks["case_identity"]["ok"] is False:
        return "Add case ID, ticker, and replay timestamp metadata."
    if checks.get("demo_market_context", {}).get("ok") is False:
        context_errors = checks.get("demo_market_context", {}).get("errors", [])
        if any("stale relative to latest linked replay-time evidence" in str(error) for error in context_errors):
            return "Add intraday or replay-lock market bars so abnormal return is measured after the event evidence."
        return "Add peer market bars so daily, peer median, and abnormal returns are measurable."
    if checks.get("linked_replay_time_sources", {}).get("ok") is False:
        return "Link more replay-time sources directly to narrative claims before public demo use."
    if checks.get("source_type_diversity", {}).get("ok") is False:
        return "Add independently sourced replay-time evidence beyond a single source type."
    if checks.get("publisher_diversity", {}).get("ok") is False:
        return "Add replay-time evidence from more than one publisher before public demo use."
    if checks.get("validation_outcomes", {}).get("ok") is False:
        return "Add at least one held-out validation outcome before treating this as public demo-ready."
    if checks.get("public_replay_evidence", {}).get("ok") is False:
        return "Add non-SEC replay-time evidence from multiple non-market sources before public demo use."
    if checks.get("public_validation_evidence", {}).get("ok") is False:
        return "Link held-out validation outcomes to blocked future source IDs before public demo use."
    return "Review the report and decide whether this private case is demo-worthy."


def _readiness_replay_check(payload: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    errors = []
    event_timestamp = _safe_parse_datetime(meta.get("event_timestamp"))
    if event_timestamp is None:
        errors.append("case_metadata.event_timestamp must be a timezone-aware ISO timestamp")

    allowed_after_lock = []
    blocked_before_lock = []
    blocked_future = []
    for source in _source_items(payload):
        source_id = str(source.get("source_id", "unknown"))
        status = source.get("availability_status")
        if status == "blocked_future":
            blocked_future.append(source_id)
        published_at = _safe_parse_datetime(source.get("published_at"))
        if event_timestamp is None or published_at is None:
            continue
        if status == "allowed" and published_at > event_timestamp:
            allowed_after_lock.append(source_id)
        if status == "blocked_future" and published_at <= event_timestamp:
            blocked_before_lock.append(source_id)

    if allowed_after_lock:
        errors.append("allowed sources published after the replay lock")
    if blocked_before_lock:
        errors.append("blocked_future sources published before or at the replay lock")

    return {
        "ok": not errors and not allowed_after_lock and not blocked_before_lock,
        "errors": errors,
        "blocked_future_source_ids": blocked_future,
        "allowed_after_lock_source_ids": allowed_after_lock,
        "blocked_before_lock_source_ids": blocked_before_lock,
    }


def _readiness_provenance_check(payload: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    real_curated = meta.get("data_provenance_mode") == "real-curated"
    missing_stable_url = []
    missing_hash = []
    hash_mismatch = []
    missing_retrieved_at = []
    document_text_source_ids = []

    for source in _source_items(payload):
        source_id = str(source.get("source_id", "unknown"))
        if _is_placeholder_url(source.get("url")):
            missing_stable_url.append(source_id)
        if not HASH_PATTERN.match(str(source.get("content_hash", ""))):
            missing_hash.append(source_id)
        elif real_curated:
            hash_field, hash_text = _source_hash_text(source)
            if source["content_hash"] != source_content_hash(hash_text):
                hash_mismatch.append(f"{source_id}:{hash_field}")
        if not source.get("retrieved_at"):
            missing_retrieved_at.append(source_id)
        if source.get("document_text") or source.get("raw_text"):
            document_text_source_ids.append(source_id)

    errors = []
    if missing_stable_url:
        errors.append("sources need stable non-placeholder URLs")
    if missing_hash:
        errors.append("sources need sha256 content hashes")
    if hash_mismatch:
        errors.append("real-curated source hashes must match document_text, raw_text, or claim_extracted")
    if missing_retrieved_at:
        errors.append("sources need retrieved_at timestamps")

    return {
        "ok": not errors,
        "errors": errors,
        "missing_stable_url_source_ids": missing_stable_url,
        "missing_hash_source_ids": missing_hash,
        "hash_mismatch_source_ids": hash_mismatch,
        "missing_retrieved_at_source_ids": missing_retrieved_at,
        "document_text_source_ids": document_text_source_ids,
    }


def _readiness_linkage_check(payload: dict[str, Any]) -> dict[str, Any]:
    narratives = [item for item in payload.get("narratives", []) if isinstance(item, dict)]
    sources = _source_items(payload)
    allowed_sources_without_links = []
    narrative_link_counts = []
    narratives_without_allowed_support = []

    for source in sources:
        if source.get("availability_status") != "allowed":
            continue
        linked_ids = [
            *source.get("supported_narrative_ids", []),
            *source.get("contradicted_narrative_ids", []),
        ]
        if not linked_ids:
            allowed_sources_without_links.append(str(source.get("source_id", "unknown")))

    for narrative in narratives:
        narrative_id = str(narrative.get("narrative_id", "unknown"))
        allowed_support = [
            str(source.get("source_id", "unknown"))
            for source in sources
            if source.get("availability_status") == "allowed"
            and narrative_id in source.get("supported_narrative_ids", [])
        ]
        allowed_contradiction = [
            str(source.get("source_id", "unknown"))
            for source in sources
            if source.get("availability_status") == "allowed"
            and narrative_id in source.get("contradicted_narrative_ids", [])
        ]
        future_links = [
            str(source.get("source_id", "unknown"))
            for source in sources
            if source.get("availability_status") == "blocked_future"
            and (
                narrative_id in source.get("supported_narrative_ids", [])
                or narrative_id in source.get("contradicted_narrative_ids", [])
            )
        ]
        if not allowed_support:
            narratives_without_allowed_support.append(narrative_id)
        narrative_link_counts.append(
            {
                "narrative_id": narrative_id,
                "allowed_support_source_count": len(allowed_support),
                "allowed_contradiction_source_count": len(allowed_contradiction),
                "blocked_future_source_count": len(future_links),
            }
        )

    errors = []
    if narratives and narratives_without_allowed_support:
        errors.append("each narrative needs at least one replay-safe supporting source")

    return {
        "ok": not errors,
        "errors": errors,
        "narratives_without_allowed_support": narratives_without_allowed_support,
        "allowed_sources_without_links": allowed_sources_without_links,
        "narrative_link_counts": narrative_link_counts,
    }


def _source_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    sources = payload.get("sources", []) if isinstance(payload, dict) else []
    return [source for source in sources if isinstance(source, dict)]


def _safe_parse_datetime(value: Any) -> Any:
    if not value:
        return None
    try:
        parsed = parse_datetime(value)
    except ValueError:
        return None
    if not _has_timezone_offset(parsed):
        return None
    return parsed


def _is_placeholder_url(value: Any) -> bool:
    return str(value or "").strip() in PLACEHOLDER_URLS


def build_fixture_from_source_pack(payload: dict[str, Any]) -> dict[str, Any]:
    errors = validate_source_pack(payload, require_narratives=True)
    if errors:
        raise ValueError("; ".join(errors))

    meta = payload["case_metadata"]
    event_timestamp = parse_datetime(meta["event_timestamp"])
    event_overrides = payload.get("event", {})
    if not isinstance(event_overrides, dict):
        event_overrides = {}

    event = {
        "event_id": event_overrides.get("event_id", meta["case_id"]),
        "ticker": meta["ticker"],
        "company_name": meta["company_name"],
        "event_date": event_overrides.get("event_date", meta.get("event_date", event_timestamp.date().isoformat())),
        "event_timestamp": event_timestamp.isoformat(),
        "event_type": event_overrides.get("event_type", meta.get("event_type", "unknown")),
        "event_summary": event_overrides.get("event_summary", meta.get("event_summary", "")),
        "case_id": meta["case_id"],
        "data_provenance_mode": meta["data_provenance_mode"],
    }
    for metric_key in [
        "daily_return",
        "abnormal_return",
        "volume_ratio",
        "sector_etf_return",
        "peer_median_return",
    ]:
        if metric_key in event_overrides:
            event[metric_key] = event_overrides[metric_key]

    fixture: dict[str, Any] = {
        "event": event,
        "narratives": _build_narratives(payload),
    }
    if payload.get("market_snapshot"):
        fixture["market_snapshot"] = payload["market_snapshot"]
    return fixture


def _source_pack_event_id(payload: dict[str, Any]) -> str:
    meta = payload["case_metadata"]
    event_overrides = payload.get("event", {})
    if not isinstance(event_overrides, dict):
        event_overrides = {}
    return str(event_overrides.get("event_id", meta["case_id"]))


def build_validation_fixture_template_from_source_pack(payload: dict[str, Any]) -> dict[str, Any]:
    errors = validate_source_pack(payload, require_narratives=True)
    if errors:
        raise ValueError("; ".join(errors))

    meta = payload["case_metadata"]
    future_source_ids_by_narrative = _future_source_ids_by_narrative(payload)
    future_source_ids = sorted(
        {
            source_id
            for source_ids in future_source_ids_by_narrative.values()
            for source_id in source_ids
        }
    )
    rows = []
    for narrative in payload.get("narratives", []):
        narrative_id = narrative["narrative_id"]
        for observable in narrative["expected_observables"]:
            rows.append(
                {
                    "window": "T+20",
                    "label": "pending",
                    "narrative_id": narrative_id,
                    "expected_observable": observable,
                    "future_source_ids": future_source_ids_by_narrative.get(narrative_id, []),
                    "what_happened": "Pending future validation; fill only after the validation window closes.",
                }
            )

    return {
        "event_id": _source_pack_event_id(payload),
        "status": "pending",
        "future_source_ids": future_source_ids,
        "future_source_count": len(future_source_ids),
        "note": (
            "Generated validation scaffold. Keep this file separate from event-time replay "
            "evidence and fill outcomes only after the validation window closes."
        ),
        "rows": rows,
    }


def _narrative_ids(payload: dict[str, Any]) -> set[str]:
    narratives = payload.get("narratives", [])
    if not isinstance(narratives, list):
        return set()
    return {
        str(item["narrative_id"])
        for item in narratives
        if isinstance(item, dict) and item.get("narrative_id")
    }


def _future_source_ids_by_narrative(payload: dict[str, Any]) -> dict[str, list[str]]:
    future_source_ids_by_narrative: dict[str, set[str]] = {}
    for source in payload.get("sources", []):
        if not isinstance(source, dict) or source.get("availability_status") != "blocked_future":
            continue
        source_id = str(source.get("source_id", ""))
        if not source_id:
            continue
        linked_ids = [
            *source.get("supported_narrative_ids", []),
            *source.get("contradicted_narrative_ids", []),
        ]
        for narrative_id in linked_ids:
            future_source_ids_by_narrative.setdefault(str(narrative_id), set()).add(source_id)
    return {
        narrative_id: sorted(source_ids)
        for narrative_id, source_ids in sorted(future_source_ids_by_narrative.items())
    }


def _validate_narratives(payload: dict[str, Any], *, require_narratives: bool = False) -> list[str]:
    errors: list[str] = []
    narratives = payload.get("narratives", [])
    if not isinstance(narratives, list):
        return ["narratives must be a list"]
    if require_narratives and not narratives:
        errors.append("narratives must be a non-empty list for ingestion")

    seen_narrative_ids: set[str] = set()
    for idx, narrative in enumerate(narratives):
        if not isinstance(narrative, dict):
            errors.append(f"narratives[{idx}] must be an object")
            continue
        missing = sorted(REQUIRED_NARRATIVE_FIELDS - set(narrative.keys()))
        if missing:
            errors.append(f"narratives[{idx}] missing required fields: {', '.join(missing)}")
            continue

        narrative_id = narrative.get("narrative_id")
        if narrative_id in seen_narrative_ids:
            errors.append(f"narratives[{idx}].narrative_id duplicates {narrative_id}")
        seen_narrative_ids.add(narrative_id)

        if narrative.get("directional_implication") not in ALLOWED_DIRECTIONS:
            errors.append(f"narratives[{idx}].directional_implication invalid")

        if not isinstance(narrative.get("expected_observables"), list):
            errors.append(f"narratives[{idx}].expected_observables must be a list")
        elif require_narratives and any(
            not isinstance(item, str) or not item.strip()
            for item in narrative["expected_observables"]
        ):
            errors.append(f"narratives[{idx}].expected_observables must contain non-empty strings")

        scoring = narrative.get("scoring_inputs")
        if not isinstance(scoring, dict):
            errors.append(f"narratives[{idx}].scoring_inputs must be an object")
            continue
        missing_scores = sorted(REQUIRED_SCORING_FIELDS - set(scoring.keys()))
        if missing_scores:
            errors.append(
                f"narratives[{idx}].scoring_inputs missing required fields: {', '.join(missing_scores)}"
            )
        for score_key in sorted(REQUIRED_SCORING_FIELDS & set(scoring.keys())):
            if not _is_score01(scoring[score_key]):
                errors.append(f"narratives[{idx}].scoring_inputs.{score_key} must be a number from 0 to 1")
    return errors


def _validate_ingestion_links(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    narratives = payload.get("narratives", [])
    sources = payload.get("sources", [])
    narrative_ids = _narrative_ids(payload)
    linked_narrative_ids: set[str] = set()
    meta = payload.get("case_metadata", {})
    if not isinstance(meta, dict):
        meta = {}

    for idx, source in enumerate(sources):
        if not isinstance(source, dict):
            continue
        supported = {str(item) for item in source.get("supported_narrative_ids", [])}
        contradicted = {str(item) for item in source.get("contradicted_narrative_ids", [])}
        overlap = sorted(supported & contradicted)
        if overlap:
            errors.append(
                f"sources[{idx}] cannot support and contradict the same narrative IDs: {', '.join(overlap)}"
            )
        linked_narrative_ids.update(supported | contradicted)
        if meta.get("data_provenance_mode") == "real-curated":
            if str(source.get("url", "")).strip() in {"", "https://...", "http://..."}:
                errors.append(f"sources[{idx}].url must be a stable non-placeholder locator")
            if not source.get("retrieved_at"):
                errors.append(f"sources[{idx}].retrieved_at is required for real-curated ingestion")

    for idx, narrative in enumerate(narratives):
        if not isinstance(narrative, dict):
            continue
        narrative_id = narrative.get("narrative_id")
        if narrative_id in narrative_ids and narrative_id not in linked_narrative_ids:
            errors.append(f"narratives[{idx}] must have at least one supporting or contradicting source")
    return errors


def _build_narratives(payload: dict[str, Any]) -> list[dict[str, Any]]:
    meta = payload["case_metadata"]
    sources = payload.get("sources", [])
    narratives = []
    for narrative in payload.get("narratives", []):
        narrative_id = narrative["narrative_id"]
        narratives.append(
            {
                "narrative_id": narrative_id,
                "event_id": meta["case_id"],
                "ticker": meta["ticker"],
                "timestamp_created": narrative.get("timestamp_created", meta["event_timestamp"]),
                "title": narrative["title"],
                "narrative": narrative["narrative"],
                "mechanism": narrative["mechanism"],
                "directional_implication": narrative["directional_implication"],
                "time_horizon": narrative["time_horizon"],
                "expected_observables": narrative["expected_observables"],
                "supporting_evidence": [
                    _evidence_from_source(source)
                    for source in sources
                    if narrative_id in source.get("supported_narrative_ids", [])
                ],
                "contradicting_evidence": [
                    _evidence_from_source(source)
                    for source in sources
                    if narrative_id in source.get("contradicted_narrative_ids", [])
                ],
                "scoring_inputs": narrative["scoring_inputs"],
                "validation_status": narrative.get("validation_status", "pending"),
            }
        )
    return narratives


def _evidence_from_source(source: dict[str, Any]) -> dict[str, Any]:
    evidence = sanitize_source_record(source)
    evidence["claim"] = source.get("claim") or source["claim_extracted"]
    return evidence
