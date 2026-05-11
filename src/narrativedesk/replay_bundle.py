from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Any

from narrativedesk.case_index import validate_case_index
from narrativedesk.pipeline import load_validation_fixture, run_replay
from narrativedesk.source_pack import assess_source_pack_readiness, load_source_pack, validate_source_pack


REQUIRED_BUNDLE_ARTIFACTS = {
    "source_pack.json",
    "readiness.json",
    "event_fixture.json",
    "validation_fixture.json",
    "ledger.json",
    "report.md",
    "case_index.json",
}
REQUIRED_MANIFEST_FIELDS = {
    "schema_version",
    "bundle_type",
    "case_id",
    "event_id",
    "ticker",
    "data_provenance_mode",
    "replay_timestamp",
    "readiness_status",
    "replay_integrity",
    "artifacts",
}
REQUIRED_REPLAY_INTEGRITY_FIELDS = {
    "blocked_future_source_count",
    "blocked_future_source_ids",
    "validation_future_source_count",
    "validation_future_source_ids",
    "future_validation_separate",
}
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def verify_replay_bundle(bundle_dir: str | Path) -> dict[str, Any]:
    bundle_path = Path(bundle_dir)
    errors: list[str] = []
    checks: dict[str, dict[str, Any]] = {}

    if not bundle_path.exists():
        errors.append(f"bundle directory does not exist: {bundle_path}")
        return _summary(bundle_path, {}, checks, errors)
    if not bundle_path.is_dir():
        errors.append(f"bundle path is not a directory: {bundle_path}")
        return _summary(bundle_path, {}, checks, errors)

    manifest = _read_json(bundle_path / "manifest.json", "manifest", errors)
    if not isinstance(manifest, dict):
        _record(checks, "manifest", False, errors=["manifest.json must contain an object"])
        return _summary(bundle_path, {}, checks, errors)

    manifest_errors = _manifest_errors(manifest)
    _extend_errors(errors, "manifest", manifest_errors)
    _record(checks, "manifest", not manifest_errors, errors=manifest_errors)

    artifact_map, artifact_errors = _verify_artifacts(bundle_path, manifest)
    _extend_errors(errors, "artifacts", artifact_errors)
    _record(
        checks,
        "artifacts",
        not artifact_errors,
        artifact_count=len(artifact_map),
        required_artifacts=sorted(REQUIRED_BUNDLE_ARTIFACTS),
        errors=artifact_errors,
    )

    source_pack = _read_json(bundle_path / "source_pack.json", "source_pack", errors)
    source_errors: list[str] = []
    computed_readiness: dict[str, Any] | None = None
    if isinstance(source_pack, dict):
        source_errors.extend(validate_source_pack(source_pack, require_narratives=True))
        computed_readiness = assess_source_pack_readiness(source_pack)
    else:
        source_errors.append("source_pack.json must contain an object")
    _extend_errors(errors, "source_pack", source_errors)
    _record(checks, "source_pack", not source_errors, errors=source_errors)

    readiness = _read_json(bundle_path / "readiness.json", "readiness", errors)
    readiness_errors = _readiness_errors(readiness, manifest, computed_readiness)
    _extend_errors(errors, "readiness", readiness_errors)
    _record(checks, "readiness", not readiness_errors, errors=readiness_errors)

    validation = _load_validation(bundle_path / "validation_fixture.json", errors)
    event = None
    audit = None
    replay_errors: list[str] = []
    try:
        event, _narratives, audit, _inline_validation = run_replay(bundle_path / "event_fixture.json")
    except Exception as exc:
        replay_errors.append(str(exc))
    _extend_errors(errors, "replay", replay_errors)
    _record(checks, "replay", not replay_errors, errors=replay_errors)

    case_index_result = validate_case_index(bundle_path / "case_index.json")
    case_index_errors = list(case_index_result.get("errors", []))
    _extend_errors(errors, "case_index", case_index_errors)
    _record(
        checks,
        "case_index",
        bool(case_index_result.get("ok")),
        case_count=case_index_result.get("case_count", 0),
        errors=case_index_errors,
    )

    ledger = _read_json(bundle_path / "ledger.json", "ledger", errors)
    ledger_errors = _ledger_errors(ledger, event, audit)
    _extend_errors(errors, "ledger", ledger_errors)
    _record(checks, "ledger", not ledger_errors, errors=ledger_errors)

    integrity_errors = _integrity_errors(manifest, event, audit, validation)
    _extend_errors(errors, "replay_integrity", integrity_errors)
    _record(checks, "replay_integrity", not integrity_errors, errors=integrity_errors)

    return _summary(bundle_path, manifest, checks, errors)


def _manifest_errors(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_MANIFEST_FIELDS - set(manifest))
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")
    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if manifest.get("bundle_type") != "narrativedesk_replay_bundle":
        errors.append("bundle_type must be narrativedesk_replay_bundle")
    integrity = manifest.get("replay_integrity")
    if not isinstance(integrity, dict):
        errors.append("replay_integrity must be an object")
    else:
        integrity_missing = sorted(REQUIRED_REPLAY_INTEGRITY_FIELDS - set(integrity))
        if integrity_missing:
            errors.append(f"replay_integrity missing fields: {', '.join(integrity_missing)}")
    if not isinstance(manifest.get("artifacts"), list):
        errors.append("artifacts must be a list")
    return errors


def _verify_artifacts(
    bundle_path: Path,
    manifest: dict[str, Any],
) -> tuple[dict[str, Path], list[str]]:
    artifact_map: dict[str, Path] = {}
    errors: list[str] = []
    artifacts = manifest.get("artifacts", [])
    if not isinstance(artifacts, list):
        return artifact_map, ["artifacts must be a list"]

    for idx, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            errors.append(f"artifacts[{idx}] must be an object")
            continue
        path_value = artifact.get("path")
        if not isinstance(path_value, str) or not path_value:
            errors.append(f"artifacts[{idx}].path is required")
            continue
        artifact_path_error = _artifact_path_error(path_value)
        if artifact_path_error:
            errors.append(f"artifacts[{idx}].path {artifact_path_error}")
            continue
        if path_value in artifact_map:
            errors.append(f"artifacts[{idx}].path duplicates {path_value}")
            continue

        path = bundle_path / path_value
        artifact_map[path_value] = path
        if not path.exists():
            errors.append(f"{path_value} does not exist")
            continue
        expected_hash = artifact.get("sha256")
        if not isinstance(expected_hash, str) or not HEX_SHA256.match(expected_hash):
            errors.append(f"{path_value} sha256 must be 64 lowercase hex chars")
        elif _file_sha256(path) != expected_hash:
            errors.append(f"{path_value} sha256 mismatch")

        expected_bytes = artifact.get("bytes")
        if not isinstance(expected_bytes, int) or isinstance(expected_bytes, bool) or expected_bytes < 0:
            errors.append(f"{path_value} bytes must be a non-negative integer")
        elif path.stat().st_size != expected_bytes:
            errors.append(f"{path_value} byte size mismatch")

    missing_required = sorted(REQUIRED_BUNDLE_ARTIFACTS - set(artifact_map))
    if missing_required:
        errors.append(f"missing required artifacts: {', '.join(missing_required)}")
    return artifact_map, errors


def _artifact_path_error(path_value: str) -> str | None:
    path = Path(path_value)
    if path.is_absolute():
        return "must be relative"
    if ".." in path.parts:
        return "must not escape the bundle directory"
    if path_value == "manifest.json":
        return "must not point at manifest.json"
    return None


def _readiness_errors(
    readiness: Any,
    manifest: dict[str, Any],
    computed_readiness: dict[str, Any] | None,
) -> list[str]:
    if not isinstance(readiness, dict):
        return ["readiness.json must contain an object"]
    errors: list[str] = []
    if readiness.get("ok") is not True:
        errors.append("readiness ok must be true")
    if readiness.get("status") != manifest.get("readiness_status"):
        errors.append("readiness status does not match manifest")
    if computed_readiness is not None:
        if computed_readiness.get("status") != readiness.get("status"):
            errors.append("readiness status is stale relative to source_pack.json")
        if computed_readiness.get("ok") != readiness.get("ok"):
            errors.append("readiness ok is stale relative to source_pack.json")
    return errors


def _load_validation(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        return load_validation_fixture(path)
    except Exception as exc:
        errors.append(f"validation: {exc}")
        return None


def _ledger_errors(ledger: Any, event: Any, audit: Any) -> list[str]:
    if not isinstance(ledger, dict):
        return ["ledger.json must contain an object"]
    errors: list[str] = []
    if event is not None and ledger.get("event", {}).get("case_id") != event.case_id:
        errors.append("ledger event.case_id does not match replay event")
    ledger_blocked_ids = ledger.get("replay_audit", {}).get("blocked_source_ids")
    if audit is not None and ledger_blocked_ids != audit.blocked_source_ids:
        errors.append("ledger replay_audit.blocked_source_ids does not match replay audit")
    return errors


def _integrity_errors(
    manifest: dict[str, Any],
    event: Any,
    audit: Any,
    validation: dict[str, Any] | None,
) -> list[str]:
    errors: list[str] = []
    integrity = manifest.get("replay_integrity")
    if not isinstance(integrity, dict):
        return ["manifest replay_integrity must be an object"]

    if integrity.get("future_validation_separate") is not True:
        errors.append("future_validation_separate must be true")
    if event is not None:
        if manifest.get("case_id") != event.case_id:
            errors.append("manifest case_id does not match event fixture")
        if manifest.get("event_id") != event.event_id:
            errors.append("manifest event_id does not match event fixture")
        if manifest.get("ticker") != event.ticker:
            errors.append("manifest ticker does not match event fixture")
        if manifest.get("data_provenance_mode") != event.data_provenance_mode:
            errors.append("manifest data_provenance_mode does not match event fixture")
        if manifest.get("replay_timestamp") != event.event_timestamp.isoformat():
            errors.append("manifest replay_timestamp does not match event fixture")
    if audit is not None:
        blocked_ids = integrity.get("blocked_future_source_ids")
        if blocked_ids != audit.blocked_source_ids:
            errors.append("manifest blocked future source IDs do not match replay audit")
        if integrity.get("blocked_future_source_count") != len(audit.blocked_source_ids):
            errors.append("manifest blocked future source count does not match replay audit")
    if validation is not None:
        future_ids = validation.get("future_source_ids", [])
        if future_ids != integrity.get("validation_future_source_ids"):
            errors.append("manifest validation future source IDs do not match validation fixture")
        if integrity.get("validation_future_source_count") != len(future_ids):
            errors.append("manifest validation future source count does not match validation fixture")
    return errors


def _read_json(path: Path, label: str, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        errors.append(f"{label}: {path.name} does not exist")
    except json.JSONDecodeError as exc:
        errors.append(f"{label}: invalid JSON: {exc}")
    except OSError as exc:
        errors.append(f"{label}: {exc}")
    return None


def _record(checks: dict[str, dict[str, Any]], name: str, ok: bool, **details: Any) -> None:
    checks[name] = {"ok": ok, **details}


def _extend_errors(errors: list[str], prefix: str, check_errors: list[str]) -> None:
    errors.extend(f"{prefix}: {error}" for error in check_errors)


def _summary(
    bundle_path: Path,
    manifest: dict[str, Any],
    checks: dict[str, dict[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    return {
        "ok": not errors,
        "bundle_dir": str(bundle_path),
        "case_id": manifest.get("case_id"),
        "ticker": manifest.get("ticker"),
        "artifact_count": len(manifest.get("artifacts", [])) if isinstance(manifest.get("artifacts"), list) else 0,
        "checks": checks,
        "errors": errors,
    }


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()
