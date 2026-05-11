from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from narrativedesk.evaluation import validated_narrative_ids
from narrativedesk.pipeline import load_event_fixture, load_validation_fixture, run_replay


def load_case_index_payload(path: str | Path) -> dict[str, Any]:
    index_path = Path(path)
    if not index_path.exists():
        return {"default_case_id": "", "cases": []}
    payload = json.loads(index_path.read_text())
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        cases = []
    return {
        "default_case_id": payload.get("default_case_id", ""),
        "cases": cases,
    }


def register_case_index_entry(
    case_index_path: str | Path,
    event_fixture_path: str | Path,
    validation_fixture_path: str | Path,
    *,
    label: str | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    event_path = Path(event_fixture_path)
    validation_path = Path(validation_fixture_path)
    event, _narratives, _inline_validation = load_event_fixture(event_path)
    validation = load_validation_fixture(validation_path)
    validation_event_id = validation.get("event_id")
    if validation_event_id != event.event_id:
        raise ValueError(
            f"validation event_id {validation_event_id!r} does not match event_id {event.event_id!r}"
        )

    payload = load_case_index_payload(case_index_path)
    if any(case.get("case_id") == event.case_id for case in payload["cases"]):
        raise ValueError(f"case_id {event.case_id} already exists in case index")

    if not payload["default_case_id"]:
        payload["default_case_id"] = event.case_id

    entry = {
        "case_id": event.case_id,
        "label": label or f"{event.ticker} curated case",
        "event_fixture": _path_value(event_path),
        "validation_fixture": _path_value(validation_path),
    }
    payload["cases"].append(entry)

    target_path = Path(output_path) if output_path else Path(case_index_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return {
        "case_id": event.case_id,
        "label": entry["label"],
        "case_count": len(payload["cases"]),
        "out": str(target_path),
        "default_case_id": payload["default_case_id"],
    }


def validate_case_index(case_index_path: str | Path) -> dict[str, Any]:
    index_path = Path(case_index_path)
    errors: list[str] = []
    case_summaries: list[dict[str, Any]] = []
    if not index_path.exists():
        return {
            "ok": False,
            "errors": [f"case index does not exist: {index_path}"],
            "case_count": 0,
            "cases": [],
        }

    payload = load_case_index_payload(index_path)
    cases = payload["cases"]
    if not cases:
        errors.append("case index must contain at least one case")

    default_case_id = payload.get("default_case_id")
    case_ids = [case.get("case_id") for case in cases if isinstance(case, dict)]
    if default_case_id and default_case_id not in case_ids:
        errors.append(f"default_case_id {default_case_id} is not present in cases")

    seen_case_ids: set[str] = set()
    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"cases[{idx}] must be an object")
            continue
        missing = [
            field
            for field in ["case_id", "label", "event_fixture", "validation_fixture"]
            if not case.get(field)
        ]
        if missing:
            errors.append(f"cases[{idx}] missing required fields: {', '.join(missing)}")
            continue

        case_id = str(case["case_id"])
        if case_id in seen_case_ids:
            errors.append(f"cases[{idx}].case_id duplicates {case_id}")
            continue
        seen_case_ids.add(case_id)
        case_summaries.append(_validate_case_entry(index_path, idx, case, errors))

    return {
        "ok": not errors,
        "errors": errors,
        "case_count": len(cases),
        "valid_case_count": sum(1 for item in case_summaries if item["ok"]),
        "evaluated_case_count": sum(1 for item in case_summaries if item["validated_narrative_count"] > 0),
        "pending_case_count": sum(1 for item in case_summaries if item["validated_narrative_count"] == 0),
        "blocked_future_source_count": sum(item["blocked_future_source_count"] for item in case_summaries),
        "validation_future_source_count": sum(
            item["validation_future_source_count"] for item in case_summaries
        ),
        "default_case_id": default_case_id,
        "cases": case_summaries,
    }


def _validate_case_entry(
    case_index_path: Path,
    idx: int,
    case: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    case_id = str(case["case_id"])
    event_path = _resolve_case_path(case_index_path, str(case["event_fixture"]))
    validation_path = _resolve_case_path(case_index_path, str(case["validation_fixture"]))
    summary = {
        "case_id": case_id,
        "ok": True,
        "event_fixture": str(event_path),
        "validation_fixture": str(validation_path),
        "ticker": None,
        "validated_narrative_count": 0,
        "blocked_future_source_count": 0,
        "validation_future_source_count": 0,
    }

    if not event_path.exists():
        errors.append(f"cases[{idx}].event_fixture does not exist: {event_path}")
        summary["ok"] = False
        return summary
    if not validation_path.exists():
        errors.append(f"cases[{idx}].validation_fixture does not exist: {validation_path}")
        summary["ok"] = False
        return summary

    try:
        raw_event_fixture = json.loads(event_path.read_text())
        if raw_event_fixture.get("validation"):
            errors.append(f"cases[{idx}].event_fixture must not contain inline validation data")
            summary["ok"] = False
        event, _narratives, _inline_validation = load_event_fixture(event_path)
        validation = load_validation_fixture(validation_path)
        replay_event, ranked, audit, _validation = run_replay(event_path)
    except Exception as exc:
        errors.append(f"cases[{idx}] failed to load: {exc}")
        summary["ok"] = False
        return summary

    summary["ticker"] = event.ticker
    summary["blocked_future_source_count"] = len(audit.blocked_source_ids)
    summary["validated_narrative_count"] = len(validated_narrative_ids(validation))
    validation_future_source_ids = _validation_future_source_ids(validation, idx, errors)
    summary["validation_future_source_count"] = len(validation_future_source_ids)

    if event.case_id != case_id:
        errors.append(f"cases[{idx}].case_id {case_id} does not match event.case_id {event.case_id}")
        summary["ok"] = False
    if replay_event.event_id != validation.get("event_id"):
        errors.append(
            f"cases[{idx}].validation_fixture event_id {validation.get('event_id')} "
            f"does not match event_id {replay_event.event_id}"
        )
        summary["ok"] = False

    returned_source_ids = {
        evidence.source_id
        for narrative in ranked
        for evidence in narrative.all_evidence()
    }
    leaked = sorted(set(audit.blocked_source_ids) & returned_source_ids)
    if leaked:
        errors.append(f"cases[{idx}] returned blocked future sources: {', '.join(leaked)}")
        summary["ok"] = False

    missing_future_ids = sorted(set(validation_future_source_ids) - set(audit.blocked_source_ids))
    if missing_future_ids:
        errors.append(
            f"cases[{idx}].validation_fixture future_source_ids were not blocked by replay: "
            f"{', '.join(missing_future_ids)}"
        )
        summary["ok"] = False

    return summary


def _validation_future_source_ids(
    validation: dict[str, Any],
    idx: int,
    errors: list[str],
) -> list[str]:
    future_source_ids: set[str] = set()
    top_level = validation.get("future_source_ids", [])
    if top_level is None:
        top_level = []
    if not isinstance(top_level, list):
        errors.append(f"cases[{idx}].validation_fixture future_source_ids must be a list")
        return []
    future_source_ids.update(str(item) for item in top_level if str(item).strip())

    rows = validation.get("rows", [])
    if not isinstance(rows, list):
        return sorted(future_source_ids)
    for row_idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        row_ids = row.get("future_source_ids", [])
        if row_ids is None:
            row_ids = []
        if not isinstance(row_ids, list):
            errors.append(
                f"cases[{idx}].validation_fixture rows[{row_idx}].future_source_ids must be a list"
            )
            continue
        future_source_ids.update(str(item) for item in row_ids if str(item).strip())
    expected_count = validation.get("future_source_count")
    if expected_count is not None and expected_count != len(future_source_ids):
        errors.append(
            f"cases[{idx}].validation_fixture future_source_count {expected_count} "
            f"does not match {len(future_source_ids)} future_source_ids"
        )
    return sorted(future_source_ids)


def _resolve_case_path(case_index_path: Path, fixture_path: str) -> Path:
    path = Path(fixture_path)
    if path.is_absolute():
        return path
    if path.exists():
        return path
    return case_index_path.parent / path


def _path_value(path: Path) -> str:
    return path.as_posix()
