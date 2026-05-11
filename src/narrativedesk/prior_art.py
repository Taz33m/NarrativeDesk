from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from narrativedesk.models import parse_datetime
from narrativedesk.source_pack import source_content_hash


PRIOR_ART_TARGETS: dict[str, list[str]] = {
    "citadail": [
        "frontend/lib/built-in-market-data.ts",
        "frontend/lib/ticker-news.ts",
        "frontend/lib/equity-research-data.ts",
        "frontend/lib/full-auto-historical-data.ts",
        "frontend/outputs/equity-demo/aapl-buy-long/*",
    ],
    "mktmind-qtm": [
        "data/marketmind_qml_dataset.csv",
        "src/build_dataset.py",
        "src/splits.py",
        "results/metrics_summary.csv",
    ],
    "applecapital": [
        "src/app/api/fetch-sec-filing/route.ts",
        "src/app/api/fetch-tickers/route.ts",
        "src/lib/server/market-data.ts",
        "python/market_intelligence.py",
        "test-logs/*AAPL*.json",
    ],
}

TIMESTAMP_FIELDS = ("published_at", "publishedAt", "timestamp", "datetime", "as_of", "asOf")
URL_FIELDS = ("url", "source_url", "sourceUrl", "href", "filing_url", "filingUrl")
PUBLISHER_FIELDS = ("publisher", "source", "provider", "authority")
CLAIM_FIELDS = ("claim_extracted", "claim", "summary", "headline", "title", "text")
MISSING_FIELD_KEYS = ("timestamp", "url", "publisher", "claim", "timezone_timestamp")


@dataclass(frozen=True)
class PriorArtInspection:
    map_payload: dict[str, Any]
    manual_sources_payload: dict[str, Any]


def inspect_prior_art_repos(
    repo_roots: dict[str, str | Path],
    *,
    output_dir: str | Path = ".codex-work",
) -> PriorArtInspection:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    map_payload: dict[str, Any] = {
        "schema_version": 1,
        "target_repos": sorted(PRIOR_ART_TARGETS),
        "missing_field_counts": _empty_missing_counts(),
        "repos": [],
    }
    manual_sources: list[dict[str, Any]] = []
    skipped_record_count = 0

    for repo, targets in PRIOR_ART_TARGETS.items():
        root = Path(repo_roots[repo]) if repo in repo_roots else None
        repo_entry: dict[str, Any] = {
            "repo": repo,
            "root": str(root) if root else None,
            "targets": [],
        }
        for target in targets:
            target_entry, sources, skipped = _inspect_target(repo, root, target)
            repo_entry["targets"].append(target_entry)
            manual_sources.extend(sources)
            skipped_record_count += skipped
            _add_counts(map_payload["missing_field_counts"], target_entry["missing_field_counts"])
        map_payload["repos"].append(repo_entry)

    manual_sources_payload = {
        "schema_version": 1,
        "manual_sources": manual_sources,
        "manual_source_count": len(manual_sources),
        "skipped_record_count": skipped_record_count,
        "conversion_rule": (
            "Records convert only when they include a timezone-aware timestamp, source URL, "
            "publisher, and claim text. Incomplete or model-only records are skipped."
        ),
    }
    map_payload["manual_source_count"] = len(manual_sources)
    map_payload["skipped_record_count"] = skipped_record_count

    _write_json(out_dir / "prior-art-map.json", map_payload)
    _write_json(out_dir / "prior-art-manual-sources.json", manual_sources_payload)
    return PriorArtInspection(map_payload=map_payload, manual_sources_payload=manual_sources_payload)


def _inspect_target(
    repo: str,
    root: Path | None,
    target: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    if root is None:
        return (
            {
                "path": target,
                "status": "not_configured",
                "matched_files": [],
                "candidate_record_count": 0,
                "manual_source_count": 0,
                "skipped_record_count": 0,
                "missing_field_counts": _empty_missing_counts(),
                "skipped_record_examples": [],
            },
            [],
            0,
        )
    matches = sorted(root.glob(target)) if _is_glob(target) else [root / target]
    existing = [path for path in matches if path.exists() and path.is_file()]
    manual_sources: list[dict[str, Any]] = []
    candidate_count = 0
    skipped_count = 0
    missing_field_counts = _empty_missing_counts()
    skipped_examples: list[dict[str, Any]] = []
    for path in existing:
        records = _candidate_records(path)
        candidate_count += len(records)
        for idx, record in enumerate(records):
            prepared, missing_fields = _prepare_record(record)
            if missing_fields:
                skipped_count += 1
                _add_missing_fields(missing_field_counts, missing_fields)
                if len(skipped_examples) < 5:
                    skipped_examples.append(
                        {
                            "path": _relative_path(root, path),
                            "record_index": idx,
                            "missing_fields": missing_fields,
                        }
                    )
            else:
                manual_sources.append(_manual_source_from_record(repo, root, path, prepared, idx))
    return (
        {
            "path": target,
            "status": "found" if existing else "missing",
            "matched_files": [_relative_path(root, path) for path in existing],
            "candidate_record_count": candidate_count,
            "manual_source_count": len(manual_sources),
            "skipped_record_count": skipped_count,
            "missing_field_counts": missing_field_counts,
            "skipped_record_examples": skipped_examples,
        },
        manual_sources,
        skipped_count,
    )


def _candidate_records(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            return []
        return list(_walk_dict_records(payload))
    if suffix == ".csv":
        try:
            with path.open(newline="") as handle:
                return [dict(row) for row in csv.DictReader(handle)]
        except csv.Error:
            return []
    return []


def _walk_dict_records(payload: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        if any(field in payload for field in (*TIMESTAMP_FIELDS, *URL_FIELDS, *CLAIM_FIELDS)):
            records.append(payload)
        for value in payload.values():
            records.extend(_walk_dict_records(value))
    elif isinstance(payload, list):
        for value in payload:
            records.extend(_walk_dict_records(value))
    return records


def _manual_source_from_record(
    repo: str,
    root: Path,
    path: Path,
    record: dict[str, str],
    index: int,
) -> dict[str, Any]:
    relative_path = _relative_path(root, path)
    source_id = _source_id(repo, relative_path, index, record["claim"])
    title = str(record.get("title") or record.get("headline") or record["claim"])[:120]
    claim_text = record["claim"].strip()
    return {
        "source_id": source_id,
        "source_type": "prior_art_manual_source",
        "publisher": record["publisher"].strip(),
        "title": title,
        "url": record["url"].strip(),
        "published_at": record["published_at"],
        "claim_extracted": claim_text,
        "document_text": claim_text,
        "content_hash": source_content_hash(claim_text),
        "originality_score": 0.7,
        "support_strength": 0.5,
        "evidence_quality": 0.65,
        "independence": 0.7,
        "incentive_conflict": 0.15,
        "independence_cluster_id": f"prior-art-{repo}",
        "prior_art_repo": repo,
        "prior_art_path": relative_path,
    }


def _prepare_record(record: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    timestamp = _first_value(record, TIMESTAMP_FIELDS)
    url = _first_value(record, URL_FIELDS)
    publisher = _first_value(record, PUBLISHER_FIELDS)
    claim = _first_value(record, CLAIM_FIELDS)
    missing_fields: list[str] = []
    published_at = None
    if not timestamp:
        missing_fields.append("timestamp")
    else:
        published_at = _normalize_timestamp(timestamp)
        if not published_at:
            missing_fields.append("timezone_timestamp")
    if not url:
        missing_fields.append("url")
    if not publisher:
        missing_fields.append("publisher")
    if not claim:
        missing_fields.append("claim")
    if missing_fields:
        return {}, missing_fields
    return {
        "published_at": str(published_at),
        "url": str(url),
        "publisher": str(publisher),
        "claim": str(claim),
        "title": str(record.get("title") or record.get("headline") or claim),
    }, []


def _normalize_timestamp(value: Any) -> str | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        parsed = parse_datetime(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.isoformat()


def _first_value(record: dict[str, Any], fields: tuple[str, ...]) -> Any:
    for field in fields:
        value = record.get(field)
        if value is not None and value != "":
            return value
    return None


def _source_id(repo: str, relative_path: str, index: int, claim: Any) -> str:
    digest = sha256(f"{repo}|{relative_path}|{index}|{claim}".encode("utf-8")).hexdigest()[:10]
    prefix = "".join(part[0] for part in repo.replace("-", "_").split("_") if part).upper()[:4]
    return f"PRIOR-{prefix}-{digest}"


def _empty_missing_counts() -> dict[str, int]:
    return {key: 0 for key in MISSING_FIELD_KEYS}


def _add_missing_fields(counts: dict[str, int], missing_fields: list[str]) -> None:
    for field in missing_fields:
        counts[field] = counts.get(field, 0) + 1


def _add_counts(left: dict[str, int], right: dict[str, int]) -> None:
    for key in MISSING_FIELD_KEYS:
        left[key] = left.get(key, 0) + int(right.get(key, 0))


def _relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_glob(path: str) -> bool:
    return "*" in path or "?" in path or "[" in path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
