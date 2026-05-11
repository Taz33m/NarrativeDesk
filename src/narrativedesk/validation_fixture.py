from __future__ import annotations

from pathlib import Path
from typing import Any

import json


ALLOWED_VALIDATION_LABELS = {"pending", "partial", "validated", "invalidated", "inconclusive"}
ALLOWED_VALIDATION_WINDOWS = {"T+1", "T+5", "T+20", "T+60"}
FORBIDDEN_ROW_FIELDS = {"source_text", "document_text", "raw_text", "content_hash"}


def load_validation_fixture_payload(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text())
    errors = validate_validation_fixture(payload)
    if errors:
        raise ValueError("; ".join(errors))
    return payload


def preview_validation_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("rows", [])
    future_source_ids = payload.get("future_source_ids", [])
    return {
        "event_id": payload["event_id"],
        "status": payload.get("status", "unknown"),
        "row_count": len(rows) if isinstance(rows, list) else 0,
        "future_source_count": len(future_source_ids) if isinstance(future_source_ids, list) else 0,
        "future_source_ids": future_source_ids if isinstance(future_source_ids, list) else [],
    }


def validate_validation_fixture(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["validation fixture must be an object"]
    if not payload.get("event_id"):
        errors.append("event_id is required")
    if "validation" in payload:
        errors.append("validation fixture must not contain nested validation")

    future_source_ids = _string_list(payload, "future_source_ids", errors, required=False)
    duplicate_future_source_ids = _duplicate_strings(future_source_ids)
    if duplicate_future_source_ids:
        errors.append(f"future_source_ids contains duplicates: {', '.join(duplicate_future_source_ids)}")
    expected_count = payload.get("future_source_count")
    if expected_count is not None:
        if not isinstance(expected_count, int) or isinstance(expected_count, bool) or expected_count < 0:
            errors.append("future_source_count must be a non-negative integer")
        elif expected_count != len(set(future_source_ids)):
            errors.append(
                f"future_source_count {expected_count} does not match "
                f"{len(set(future_source_ids))} future_source_ids"
            )

    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        errors.append("rows must be a list")
        return errors
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"rows[{idx}] must be an object")
            continue
        for field in ["window", "label", "narrative_id", "expected_observable", "what_happened"]:
            if not row.get(field):
                errors.append(f"rows[{idx}].{field} is required")
        if row.get("window") and row["window"] not in ALLOWED_VALIDATION_WINDOWS:
            errors.append(f"rows[{idx}].window invalid")
        if row.get("label") and row["label"] not in ALLOWED_VALIDATION_LABELS:
            errors.append(f"rows[{idx}].label invalid")
        row_future_ids = _string_list(row, "future_source_ids", errors, required=False, prefix=f"rows[{idx}].")
        unknown_row_ids = sorted(set(row_future_ids) - set(future_source_ids))
        if unknown_row_ids:
            errors.append(
                f"rows[{idx}].future_source_ids not declared at top level: {', '.join(unknown_row_ids)}"
            )
        forbidden = sorted(FORBIDDEN_ROW_FIELDS & set(row))
        if forbidden:
            errors.append(f"rows[{idx}] cannot contain source payload fields: {', '.join(forbidden)}")
    return errors


def _string_list(
    payload: dict[str, Any],
    field: str,
    errors: list[str],
    *,
    required: bool,
    prefix: str = "",
) -> list[str]:
    if field not in payload:
        if required:
            errors.append(f"{prefix}{field} is required")
        return []
    value = payload[field]
    if not isinstance(value, list):
        errors.append(f"{prefix}{field} must be a list")
        return []
    result = []
    for idx, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{prefix}{field}[{idx}] must be a non-empty string")
            continue
        result.append(item)
    return result


def _duplicate_strings(values: list[str]) -> list[str]:
    seen = set()
    duplicates = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)
