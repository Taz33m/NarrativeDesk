from __future__ import annotations

import csv
import html
import json
import re
import shutil
import time
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from narrativedesk.models import parse_datetime
from narrativedesk.real_data import JsonFetcher, UrllibJsonFetcher
from narrativedesk.source_pack import (
    ALLOWED_DIRECTIONS,
    REQUIRED_NARRATIVE_FIELDS,
    REQUIRED_SCORING_FIELDS,
    source_content_hash,
)


class RealProvenanceError(ValueError):
    """Raised when live real-data provenance artifacts cannot be prepared safely."""


CANDIDATE_SOURCE_TYPES = {"filing", "news", "transcript", "estimate", "market_data", "other"}
CANDIDATE_REPLAY_STATUSES = {"eligible", "blocked_future", "rejected"}
SECRET_PARAM_NAMES = {"token", "apikey", "apiKey", "api_key", "authorization", "x-api-key"}
DEFAULT_PROVIDERS = ("finnhub", "sec")
CURATION_LINK_FIELDS = {
    "supporting_source_ids": ("supported_narrative_ids", "allowed"),
    "contradicting_source_ids": ("contradicted_narrative_ids", "allowed"),
    "future_supporting_source_ids": ("supported_narrative_ids", "blocked_future"),
    "future_contradicting_source_ids": ("contradicted_narrative_ids", "blocked_future"),
}


@dataclass(frozen=True)
class SourceCandidate:
    source_id: str
    provider: str
    publisher: str
    title: str
    url: str
    published_at: str
    retrieved_at: str
    source_type: str
    excerpt: str
    raw_artifact_path: str
    content_hash: str
    replay_status: str
    rejection_reason: str | None

    def __post_init__(self) -> None:
        if self.source_type not in CANDIDATE_SOURCE_TYPES:
            raise RealProvenanceError(f"Unsupported source candidate type: {self.source_type}")
        if self.replay_status not in CANDIDATE_REPLAY_STATUSES:
            raise RealProvenanceError(f"Unsupported source candidate replay status: {self.replay_status}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_manual_source(self) -> dict[str, Any]:
        if self.replay_status == "rejected":
            raise RealProvenanceError("Rejected candidates cannot be converted to manual sources")
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "publisher": self.publisher,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at,
            "retrieved_at": self.retrieved_at,
            "claim_extracted": self.excerpt,
            "document_text": self.excerpt,
            "content_hash": self.content_hash,
            "availability_status": "allowed" if self.replay_status == "eligible" else "blocked_future",
            "supported_narrative_ids": [],
            "contradicted_narrative_ids": [],
            "provider": self.provider,
            "raw_artifact_path": self.raw_artifact_path,
        }


def fetch_real_data(
    *,
    ticker: str,
    date_from: str,
    date_to: str,
    out_dir: str | Path,
    company_name: str = "",
    providers: list[str] | tuple[str, ...] = DEFAULT_PROVIDERS,
    finnhub_token: str | None = None,
    sec_user_agent: str | None = None,
    news_api_key: str | None = None,
    fetcher: JsonFetcher | None = None,
    retrieved_at: str | datetime | None = None,
    forms: list[str] | None = None,
    sec_count: int = 5,
    cik: str | None = None,
    include_sec_document_text: bool = False,
    news_query: str | None = None,
    news_domains: str | None = None,
    news_page_size: int = 20,
    sec_throttle_seconds: float = 0.12,
) -> dict[str, Any]:
    fetcher = fetcher or UrllibJsonFetcher()
    out_path = Path(out_dir)
    raw_dir = out_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    now = _iso_timestamp(_coerce_datetime(retrieved_at) if retrieved_at else datetime.now(timezone.utc))
    normalized_ticker = ticker.upper()
    selected_providers = _parse_providers(providers)

    manifest: dict[str, Any] = {
        "ok": True,
        "ticker": normalized_ticker,
        "company_name": company_name,
        "date_from": date_from,
        "date_to": date_to,
        "retrieved_at": now,
        "providers": selected_providers,
        "artifacts": [],
        "errors": [],
    }

    if "finnhub" in selected_providers:
        if not finnhub_token:
            _record_error(manifest, provider="finnhub", endpoint="auth", error="FINNHUB_API_KEY is required")
        else:
            _fetch_json_artifact(
                fetcher,
                manifest,
                out_path,
                provider="finnhub",
                endpoint="stock_candle",
                rel_path=f"raw/finnhub/{normalized_ticker}_stock_candles_D.json",
                url="https://finnhub.io/api/v1/stock/candle",
                params={
                    "symbol": normalized_ticker,
                    "resolution": "D",
                    "from": int(_date_bound(date_from, end_of_day=False).timestamp()),
                    "to": int(_date_bound(date_to, end_of_day=True).timestamp()),
                    "token": finnhub_token,
                },
                headers=None,
                retrieved_at=now,
            )
            _fetch_json_artifact(
                fetcher,
                manifest,
                out_path,
                provider="finnhub",
                endpoint="company_news",
                rel_path=f"raw/finnhub/{normalized_ticker}_company_news.json",
                url="https://finnhub.io/api/v1/company-news",
                params={
                    "symbol": normalized_ticker,
                    "from": date_from,
                    "to": date_to,
                    "token": finnhub_token,
                },
                headers=None,
                retrieved_at=now,
            )

    if "sec" in selected_providers:
        if not sec_user_agent:
            _record_error(manifest, provider="sec", endpoint="auth", error="SEC_USER_AGENT is required")
        else:
            headers = _sec_headers(sec_user_agent, host="www.sec.gov")
            resolved_cik = cik
            if not resolved_cik:
                ticker_artifact = _fetch_json_artifact(
                    fetcher,
                    manifest,
                    out_path,
                    provider="sec",
                    endpoint="ticker_cik_map",
                    rel_path="raw/sec/company_tickers.json",
                    url="https://www.sec.gov/files/company_tickers.json",
                    params=None,
                    headers=headers,
                    retrieved_at=now,
                )
                if ticker_artifact and ticker_artifact.get("status") == "ok":
                    data = json.loads((out_path / str(ticker_artifact["path"])).read_text())
                    resolved_cik = _resolve_cik_from_ticker_map(data, normalized_ticker)
                _sleep_if_needed(sec_throttle_seconds)
            if resolved_cik:
                padded_cik = str(resolved_cik).zfill(10)
                submissions_artifact = _fetch_json_artifact(
                    fetcher,
                    manifest,
                    out_path,
                    provider="sec",
                    endpoint="submissions",
                    rel_path=f"raw/sec/submissions_CIK{padded_cik}.json",
                    url=f"https://data.sec.gov/submissions/CIK{padded_cik}.json",
                    params=None,
                    headers=_sec_headers(sec_user_agent, host="data.sec.gov"),
                    retrieved_at=now,
                    extra={"cik": padded_cik, "forms": forms or ["8-K", "10-Q", "10-K"], "count": sec_count},
                )
                _sleep_if_needed(sec_throttle_seconds)
                _fetch_json_artifact(
                    fetcher,
                    manifest,
                    out_path,
                    provider="sec",
                    endpoint="companyfacts",
                    rel_path=f"raw/sec/companyfacts_CIK{padded_cik}.json",
                    url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded_cik}.json",
                    params=None,
                    headers=_sec_headers(sec_user_agent, host="data.sec.gov"),
                    retrieved_at=now,
                    extra={"cik": padded_cik},
                )
                _sleep_if_needed(sec_throttle_seconds)
                if include_sec_document_text and submissions_artifact and submissions_artifact.get("status") == "ok":
                    submissions = json.loads(
                        _artifact_path(out_path, str(submissions_artifact["path"])).read_text()
                    )
                    for filing in _select_recent_sec_filings(
                        submissions,
                        ticker=normalized_ticker,
                        cik=padded_cik,
                        forms=forms or ["8-K", "10-Q", "10-K"],
                        count=sec_count,
                    ):
                        accession = _safe_filename(filing["accession"].replace("-", ""))
                        document = filing["document"]
                        safe_document = _safe_filename(document)
                        rel_path = f"raw/sec/filing_{accession}_{safe_document}.txt"
                        _fetch_text_artifact(
                            fetcher,
                            manifest,
                            out_path,
                            provider="sec",
                            endpoint="filing_document",
                            rel_path=rel_path,
                            url=filing["url"],
                            params=None,
                            headers=_sec_headers(sec_user_agent, host="www.sec.gov"),
                            retrieved_at=now,
                            extra={
                                "cik": padded_cik,
                                "accession": filing["accession"],
                                "accession_compact": accession,
                                "document": document,
                                "form": filing["form"],
                                "filing_date": filing["filing_date"],
                            },
                        )
                        _sleep_if_needed(sec_throttle_seconds)
            else:
                _record_error(manifest, provider="sec", endpoint="resolve_cik", error=f"Could not resolve CIK for {normalized_ticker}")

    if "newsapi" in selected_providers:
        if not news_api_key:
            _record_error(manifest, provider="newsapi", endpoint="auth", error="NEWS_API_KEY is required")
        else:
            query = news_query or f'("{company_name}" OR {normalized_ticker})'
            params: dict[str, Any] = {
                "q": query,
                "from": date_from,
                "to": date_to,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": max(1, min(int(news_page_size), 100)),
            }
            if news_domains:
                params["domains"] = news_domains
            _fetch_json_artifact(
                fetcher,
                manifest,
                out_path,
                provider="newsapi",
                endpoint="everything",
                rel_path=f"raw/newsapi/{normalized_ticker}_everything.json",
                url="https://newsapi.org/v2/everything",
                params=params,
                headers={"X-Api-Key": news_api_key},
                retrieved_at=now,
            )

    manifest["ok"] = not manifest["errors"]
    _write_json(out_path / "fetch_manifest.json", manifest)
    return manifest


def normalize_real_data_fetch(
    fetch_dir: str | Path,
    *,
    replay_lock: str | datetime,
    out_dir: str | Path | None = None,
    generated_at: str | datetime | None = None,
) -> dict[str, Any]:
    fetch_path = Path(fetch_dir)
    manifest_path = fetch_path / "fetch_manifest.json"
    if not manifest_path.exists():
        raise RealProvenanceError(f"fetch_manifest.json not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    output_dir = Path(out_dir) if out_dir else fetch_path / "normalized"
    output_dir.mkdir(parents=True, exist_ok=True)
    lock = _coerce_datetime(replay_lock)
    now = _iso_timestamp(_coerce_datetime(generated_at) if generated_at else datetime.now(timezone.utc))

    candidates: list[SourceCandidate] = []
    rejected: list[SourceCandidate] = []
    market_rows: list[dict[str, Any]] = []
    counters: dict[str, int] = {}

    for artifact in manifest.get("artifacts", []):
        if not isinstance(artifact, dict) or artifact.get("status") != "ok":
            continue
        provider = str(artifact.get("provider", ""))
        endpoint = str(artifact.get("endpoint", ""))
        raw_path = _artifact_path(fetch_path, str(artifact["path"]))
        rel_raw_path = str(Path(artifact["path"]))
        if provider == "finnhub" and endpoint == "stock_candle":
            market_rows.extend(
                _market_rows_from_finnhub_candles(
                    raw_path,
                    str(artifact.get("params", {}).get("symbol") or manifest.get("ticker")),
                    replay_lock=lock,
                )
            )
        elif provider == "finnhub" and endpoint == "company_news":
            for item in _load_json_list(raw_path):
                candidate = _candidate_from_finnhub_news(
                    item,
                    raw_path=rel_raw_path,
                    retrieved_at=str(artifact.get("retrieved_at") or manifest.get("retrieved_at") or now),
                    replay_lock=lock,
                    counters=counters,
                )
                _append_candidate(candidate, candidates, rejected)
        elif provider == "sec" and endpoint == "submissions":
            document_artifacts = _sec_document_artifacts(manifest)
            data = json.loads(raw_path.read_text())
            for filing in _select_recent_sec_filings(
                data,
                ticker=str(manifest.get("ticker") or ""),
                cik=str(artifact.get("cik") or ""),
                forms=[str(item) for item in artifact.get("forms", ["8-K", "10-Q", "10-K"])],
                count=max(int(artifact.get("count", 5)), 50),
            ):
                doc_artifact = document_artifacts.get(filing["accession"])
                doc_text = ""
                doc_path = rel_raw_path
                if doc_artifact:
                    doc_path = str(doc_artifact["path"])
                    doc_text = _normalize_text(_artifact_path(fetch_path, doc_path).read_text())
                candidate = _candidate_from_sec_filing(
                    filing,
                    raw_path=doc_path,
                    retrieved_at=str(artifact.get("retrieved_at") or manifest.get("retrieved_at") or now),
                    replay_lock=lock,
                    counters=counters,
                    document_text=doc_text,
                )
                _append_candidate(candidate, candidates, rejected)
        elif provider == "newsapi" and endpoint == "everything":
            payload = json.loads(raw_path.read_text())
            for item in payload.get("articles", []) if isinstance(payload, dict) else []:
                candidate = _candidate_from_newsapi_article(
                    item,
                    raw_path=rel_raw_path,
                    retrieved_at=str(artifact.get("retrieved_at") or manifest.get("retrieved_at") or now),
                    replay_lock=lock,
                    counters=counters,
                )
                _append_candidate(candidate, candidates, rejected)

    market_path = output_dir / "market_bars.csv"
    if market_rows:
        _write_market_rows(market_path, market_rows)
    else:
        market_path.write_text("date,ticker,open,close,volume\n")

    candidate_payload = {
        "generated_at": now,
        "replay_lock": _iso_timestamp(lock),
        "ticker": manifest.get("ticker"),
        "candidates": [candidate.to_dict() for candidate in candidates],
    }
    rejected_payload = {
        "generated_at": now,
        "replay_lock": _iso_timestamp(lock),
        "ticker": manifest.get("ticker"),
        "rejected_candidates": [candidate.to_dict() for candidate in rejected],
    }
    _write_json(output_dir / "source_candidates.json", candidate_payload)
    _write_json(output_dir / "rejected_candidates.json", rejected_payload)

    summary = {
        "ok": True,
        "fetch_dir": str(fetch_path),
        "out_dir": str(output_dir),
        "market_bars_out": str(market_path),
        "source_candidates_out": str(output_dir / "source_candidates.json"),
        "rejected_candidates_out": str(output_dir / "rejected_candidates.json"),
        "eligible_candidates": len([item for item in candidates if item.replay_status == "eligible"]),
        "blocked_future_candidates": len([item for item in candidates if item.replay_status == "blocked_future"]),
        "rejected_candidates": len(rejected),
        "market_bar_rows": len(market_rows),
    }
    return summary


def draft_real_case(
    *,
    ticker: str,
    company_name: str,
    event_type: str,
    event_date: str,
    replay_lock: str | datetime,
    normalized_dir: str | Path,
    out_dir: str | Path,
    case_id: str | None = None,
    market_bars_path: str | Path | None = None,
) -> dict[str, Any]:
    normalized_path = Path(normalized_dir)
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    lock = _coerce_datetime(replay_lock)
    normalized_ticker = ticker.upper()
    case_id = case_id or f"EVT-REAL-{normalized_ticker}-{event_date}"

    candidates = _load_candidates(normalized_path / "source_candidates.json")
    rejected = _load_rejected_candidates(normalized_path / "rejected_candidates.json")
    usable_candidates = [candidate for candidate in candidates if candidate.replay_status in {"eligible", "blocked_future"}]
    eligible_count = len([candidate for candidate in usable_candidates if candidate.replay_status == "eligible"])
    blocked_count = len([candidate for candidate in usable_candidates if candidate.replay_status == "blocked_future"])

    market_bars = _draft_market_bars_path(
        normalized_path=normalized_path,
        output_dir=output_dir,
        market_bars_path=market_bars_path,
    )
    market_bars_available = _has_market_rows(market_bars, ticker=normalized_ticker, replay_lock=lock)
    missing_requirements = []
    if eligible_count == 0:
        missing_requirements.append("At least one replay-eligible source candidate")
    if not market_bars_available:
        missing_requirements.append("Frozen market_bars.csv with at least one replay-eligible ticker row")

    config = {
        "case_metadata": {
            "case_id": case_id,
            "ticker": normalized_ticker,
            "company_name": company_name,
            "event_timestamp": _iso_timestamp(lock),
            "data_provenance_mode": "real-curated",
            "event_type": event_type,
            "event_summary": "Curator-ready real-data replay draft. No narrative claims have been asserted yet.",
        },
        "event": {
            "event_id": case_id,
            "event_date": event_date,
            "event_type": event_type,
            "event_summary": "Curator-ready real-data replay draft. Add human-curated competing narratives before ingestion.",
        },
        "manual_sources": [candidate.to_manual_source() for candidate in usable_candidates],
        "narratives": [],
    }
    if market_bars_available:
        config["market_data"] = {
            "provider": "local_csv",
            "path": _relative_path(market_bars, output_dir),
        }

    config_path = output_dir / "real_case_config.json"
    narratives_path = output_dir / "narratives.todo.json"
    validation_path = output_dir / "validation_fixture.json"
    summary_path = output_dir / "draft_summary.json"

    future_source_ids = [candidate.source_id for candidate in usable_candidates if candidate.replay_status == "blocked_future"]
    _write_json(config_path, config)
    _write_json(
        narratives_path,
        {
            "case_id": case_id,
            "recommended_narrative_count": "3-5",
            "note": "Add human-curated competing narratives and link source IDs before running real-pack-build --require-narratives.",
            "available_source_ids": [candidate.source_id for candidate in usable_candidates],
        },
    )
    _write_json(
        validation_path,
        {
            "event_id": case_id,
            "status": "pending",
            "future_source_ids": future_source_ids,
            "future_source_count": len(future_source_ids),
            "note": "Validation evidence stays separate from event-time replay inputs.",
            "rows": [],
        },
    )

    filings_available = any(candidate.source_type == "filing" for candidate in usable_candidates)
    news_available = any(candidate.source_type == "news" for candidate in usable_candidates)
    case_readiness = "curator_ready" if not missing_requirements else "needs_sources"
    summary = {
        "ticker": normalized_ticker,
        "event_date": event_date,
        "replay_lock": _iso_timestamp(lock),
        "accepted_sources": eligible_count,
        "rejected_sources": len(rejected),
        "blocked_future_sources": blocked_count,
        "market_bars_available": market_bars_available,
        "filings_available": filings_available,
        "news_available": news_available,
        "case_readiness": case_readiness,
        "missing_requirements": missing_requirements,
        "recommended_next_action": (
            "Add 3-5 human-curated competing narratives."
            if case_readiness == "curator_ready"
            else "Fetch or curate additional timestamped sources before narrative curation."
        ),
        "real_case_config_out": str(config_path),
        "narratives_todo_out": str(narratives_path),
        "validation_fixture_out": str(validation_path),
    }
    _write_json(summary_path, summary)
    summary["draft_summary_out"] = str(summary_path)
    return {"ok": True, **summary}


def write_real_case_worksheet(
    draft_dir: str | Path,
    *,
    out: str | Path | None = None,
    allowed_limit: int = 12,
    blocked_limit: int = 10,
) -> dict[str, Any]:
    draft_path = Path(draft_dir)
    config = json.loads((draft_path / "real_case_config.json").read_text())
    summary = json.loads((draft_path / "draft_summary.json").read_text())
    sources = config.get("manual_sources", [])
    if not isinstance(sources, list):
        raise RealProvenanceError("real_case_config.json manual_sources must be a list")

    allowed = [source for source in sources if source.get("availability_status") == "allowed"]
    blocked = [source for source in sources if source.get("availability_status") == "blocked_future"]
    allowed.sort(key=lambda source: str(source.get("published_at") or ""), reverse=True)
    blocked.sort(key=lambda source: str(source.get("published_at") or ""))

    out_path = Path(out) if out else draft_path / "curation_worksheet.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = _worksheet_lines(
        summary=summary,
        allowed=allowed[: max(0, allowed_limit)],
        blocked=blocked[: max(0, blocked_limit)],
    )
    out_path.write_text("\n".join(lines) + "\n")
    return {
        "ok": True,
        "out": str(out_path),
        "allowed_source_count": len(allowed),
        "blocked_future_source_count": len(blocked),
        "rendered_allowed_source_count": min(len(allowed), max(0, allowed_limit)),
        "rendered_blocked_future_source_count": min(len(blocked), max(0, blocked_limit)),
    }


def write_curated_narratives_template(
    draft_dir: str | Path,
    *,
    out: str | Path | None = None,
    narrative_count: int = 5,
    allowed_limit: int = 20,
    blocked_limit: int = 20,
) -> dict[str, Any]:
    draft_path = Path(draft_dir)
    config = json.loads((draft_path / "real_case_config.json").read_text())
    summary_path = draft_path / "draft_summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    sources = config.get("manual_sources", [])
    if not isinstance(sources, list):
        raise RealProvenanceError("real_case_config.json manual_sources must be a list")

    allowed = [source for source in sources if source.get("availability_status") == "allowed"]
    blocked = [source for source in sources if source.get("availability_status") == "blocked_future"]
    allowed.sort(key=lambda source: str(source.get("published_at") or ""), reverse=True)
    blocked.sort(key=lambda source: str(source.get("published_at") or ""))

    metadata = config.get("case_metadata", {}) if isinstance(config.get("case_metadata"), dict) else {}
    normalized_ticker = str(metadata.get("ticker") or summary.get("ticker") or "REAL").upper()
    slot_count = max(1, min(int(narrative_count), 8))
    payload = {
        "_note": (
            "Scratch curation template. Replace all TBD values with human-curated claims before "
            "running real-case-apply-narratives. Do not treat this file as a real financial claim."
        ),
        "case": {
            "case_id": metadata.get("case_id"),
            "ticker": normalized_ticker,
            "company_name": metadata.get("company_name"),
            "event_date": summary.get("event_date"),
            "replay_lock": summary.get("replay_lock") or metadata.get("event_timestamp"),
            "case_readiness": summary.get("case_readiness"),
        },
        "source_pool": {
            "allowed": [_curation_source_preview(source) for source in allowed[: max(0, allowed_limit)]],
            "blocked_future": [_curation_source_preview(source) for source in blocked[: max(0, blocked_limit)]],
        },
        "narratives": [
            _curation_narrative_slot(normalized_ticker, idx)
            for idx in range(1, slot_count + 1)
        ],
    }

    out_path = Path(out) if out else draft_path / "curated_narratives.template.json"
    _write_json(out_path, payload)
    return {
        "ok": True,
        "out": str(out_path),
        "narrative_slot_count": slot_count,
        "allowed_source_count": len(allowed),
        "blocked_future_source_count": len(blocked),
        "rendered_allowed_source_count": min(len(allowed), max(0, allowed_limit)),
        "rendered_blocked_future_source_count": min(len(blocked), max(0, blocked_limit)),
    }


def rehearse_real_case(
    *,
    ticker: str,
    company_name: str,
    event_type: str,
    event_date: str,
    replay_lock: str | datetime,
    date_from: str,
    date_to: str,
    out_root: str | Path = ".codex-work",
    fetch_dir: str | Path | None = None,
    draft_dir: str | Path | None = None,
    providers: list[str] | tuple[str, ...] | str = DEFAULT_PROVIDERS,
    finnhub_token: str | None = None,
    sec_user_agent: str | None = None,
    news_api_key: str | None = None,
    fetcher: JsonFetcher | None = None,
    retrieved_at: str | datetime | None = None,
    forms: list[str] | None = None,
    sec_count: int = 5,
    cik: str | None = None,
    include_sec_document_text: bool = False,
    news_query: str | None = None,
    news_domains: str | None = None,
    sec_throttle_seconds: float = 0.12,
    worksheet: bool = True,
    curation_template: bool = True,
    allowed_limit: int = 12,
    blocked_limit: int = 10,
    template_narrative_count: int = 5,
) -> dict[str, Any]:
    """Run the deterministic live-fetch -> normalize -> draft rehearsal path."""
    root = Path(out_root)
    slug = _safe_filename(f"{ticker.lower()}-{event_date}")
    fetch_path = Path(fetch_dir) if fetch_dir else root / "live-fetches" / slug
    draft_path = Path(draft_dir) if draft_dir else root / "real-cases" / f"{slug}-rehearsal"
    fetched = fetch_real_data(
        ticker=ticker,
        company_name=company_name,
        date_from=date_from,
        date_to=date_to,
        providers=providers,
        out_dir=fetch_path,
        finnhub_token=finnhub_token,
        sec_user_agent=sec_user_agent,
        news_api_key=news_api_key,
        fetcher=fetcher,
        retrieved_at=retrieved_at,
        forms=forms,
        sec_count=sec_count,
        cik=cik,
        include_sec_document_text=include_sec_document_text,
        news_query=news_query,
        news_domains=news_domains,
        sec_throttle_seconds=sec_throttle_seconds,
    )
    response: dict[str, Any] = {
        "ok": bool(fetched.get("ok")),
        "stage": "fetch",
        "fetch_dir": str(fetch_path),
        "manifest_out": str(fetch_path / "fetch_manifest.json"),
        "artifact_count": len(fetched.get("artifacts", [])),
        "errors": fetched.get("errors", []),
    }
    usable_artifacts = [
        artifact
        for artifact in fetched.get("artifacts", [])
        if isinstance(artifact, dict) and artifact.get("status") == "ok"
    ]
    if not usable_artifacts:
        return response

    normalized = normalize_real_data_fetch(
        fetch_path,
        replay_lock=replay_lock,
        generated_at=retrieved_at,
    )
    draft = draft_real_case(
        ticker=ticker,
        company_name=company_name,
        event_type=event_type,
        event_date=event_date,
        replay_lock=replay_lock,
        normalized_dir=normalized["out_dir"],
        out_dir=draft_path,
    )
    worksheet_response = None
    if worksheet:
        worksheet_response = write_real_case_worksheet(
            draft_path,
            allowed_limit=allowed_limit,
            blocked_limit=blocked_limit,
        )
    template_response = None
    if curation_template:
        template_response = write_curated_narratives_template(
            draft_path,
            narrative_count=template_narrative_count,
        )

    response.update(
        {
            "ok": bool(fetched.get("ok")) and bool(normalized.get("ok")) and bool(draft.get("ok")),
            "stage": "complete" if fetched.get("ok") else "complete_with_fetch_errors",
            "normalized_dir": normalized["out_dir"],
            "source_candidates_out": normalized["source_candidates_out"],
            "rejected_candidates_out": normalized["rejected_candidates_out"],
            "draft_dir": str(draft_path),
            "real_case_config_out": draft["real_case_config_out"],
            "draft_summary_out": draft["draft_summary_out"],
            "narratives_todo_out": draft["narratives_todo_out"],
            "validation_fixture_out": draft["validation_fixture_out"],
            "worksheet_out": worksheet_response["out"] if worksheet_response else None,
            "curation_template_out": template_response["out"] if template_response else None,
            "accepted_sources": draft["accepted_sources"],
            "blocked_future_sources": draft["blocked_future_sources"],
            "rejected_sources": draft["rejected_sources"],
            "market_bars_available": draft["market_bars_available"],
            "filings_available": draft["filings_available"],
            "news_available": draft["news_available"],
            "case_readiness": draft["case_readiness"],
            "missing_requirements": draft["missing_requirements"],
            "recommended_next_action": draft["recommended_next_action"],
        }
    )
    return response


def apply_curated_narratives(
    draft_dir: str | Path,
    narratives_path: str | Path,
    *,
    out: str | Path | None = None,
) -> dict[str, Any]:
    draft_path = Path(draft_dir)
    config_path = draft_path / "real_case_config.json"
    config = json.loads(config_path.read_text())
    payload = json.loads(Path(narratives_path).read_text())
    updated, summary = _curated_config_from_payload(config, payload)
    out_path = Path(out) if out else draft_path / "real_case_config.curated.json"
    _write_json(out_path, updated)
    return {
        "ok": True,
        "out": str(out_path),
        "source_config": str(config_path),
        "narratives_in": str(narratives_path),
        **summary,
    }


def validate_curated_narratives(
    draft_dir: str | Path,
    narratives_path: str | Path,
) -> dict[str, Any]:
    draft_path = Path(draft_dir)
    config_path = draft_path / "real_case_config.json"
    config = json.loads(config_path.read_text())
    payload = json.loads(Path(narratives_path).read_text())
    _updated, summary = _curated_config_from_payload(config, payload)
    return {
        "ok": True,
        "source_config": str(config_path),
        "narratives_in": str(narratives_path),
        **summary,
    }


def _curated_config_from_payload(
    config: dict[str, Any],
    payload: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_narratives = _curated_narratives_from_payload(payload)
    if not raw_narratives:
        raise RealProvenanceError("Curated narratives payload must include a non-empty narratives list")

    updated = deepcopy(config)
    sources = updated.get("manual_sources")
    if not isinstance(sources, list) or not sources:
        raise RealProvenanceError("real_case_config.json must include manual_sources before narratives can be applied")
    source_by_id = {
        str(source.get("source_id")): source
        for source in sources
        if isinstance(source, dict) and source.get("source_id")
    }

    errors: list[str] = []
    curated_narratives: list[dict[str, Any]] = []
    seen_narrative_ids: set[str] = set()
    allowed_link_count = 0
    future_link_count = 0
    for idx, raw_narrative in enumerate(raw_narratives):
        if not isinstance(raw_narrative, dict):
            errors.append(f"narratives[{idx}] must be an object")
            continue
        narrative = {
            key: value
            for key, value in raw_narrative.items()
            if key not in CURATION_LINK_FIELDS
        }
        _validate_curated_narrative_shape(narrative, idx, errors)
        narrative_id = str(raw_narrative.get("narrative_id") or "")
        if narrative_id:
            if narrative_id in seen_narrative_ids:
                errors.append(f"narratives[{idx}].narrative_id duplicates {narrative_id}")
            seen_narrative_ids.add(narrative_id)
        linked_source_count = 0
        for field, (target_field, required_status) in CURATION_LINK_FIELDS.items():
            source_ids = _string_list(raw_narrative.get(field, []), f"narratives[{idx}].{field}", errors)
            for source_id in source_ids:
                source = source_by_id.get(source_id)
                if not source:
                    errors.append(f"narratives[{idx}].{field} references unknown source ID: {source_id}")
                    continue
                status = source.get("availability_status")
                if status != required_status:
                    errors.append(
                        f"narratives[{idx}].{field} references {source_id}, "
                        f"which is {status}; expected {required_status}"
                    )
                    continue
                target_values = source.setdefault(target_field, [])
                if not isinstance(target_values, list):
                    errors.append(f"source {source_id}.{target_field} must be a list")
                    continue
                if narrative_id and narrative_id not in target_values:
                    target_values.append(narrative_id)
                linked_source_count += 1
                if required_status == "allowed":
                    allowed_link_count += 1
                else:
                    future_link_count += 1
        if linked_source_count == 0:
            errors.append(f"narratives[{idx}] must link at least one source ID")
        curated_narratives.append(narrative)

    for idx, source in enumerate(sources):
        if not isinstance(source, dict):
            continue
        supported = {str(item) for item in source.get("supported_narrative_ids", [])}
        contradicted = {str(item) for item in source.get("contradicted_narrative_ids", [])}
        overlap = sorted(supported & contradicted)
        if overlap:
            errors.append(
                f"manual_sources[{idx}] cannot support and contradict the same narrative IDs: {', '.join(overlap)}"
            )

    if errors:
        raise RealProvenanceError("; ".join(errors))

    updated["narratives"] = curated_narratives
    return (
        updated,
        {
            "narrative_count": len(curated_narratives),
            "allowed_source_link_count": allowed_link_count,
            "future_source_link_count": future_link_count,
            "manual_source_count": len(sources),
        },
    )


def _worksheet_lines(
    *,
    summary: dict[str, Any],
    allowed: list[dict[str, Any]],
    blocked: list[dict[str, Any]],
) -> list[str]:
    missing_requirements = summary.get("missing_requirements") or []
    missing_text = ", ".join(str(item) for item in missing_requirements) if missing_requirements else "None"
    lines = [
        f"# {summary.get('ticker', 'Unknown')} Real-Case Replay Curation Worksheet",
        "",
        "Scratch artifact. Do not commit. No winning narrative has been asserted.",
        "",
        "## Case",
        "",
        f"- Ticker: {summary.get('ticker', 'Unknown')}",
        f"- Event date: {summary.get('event_date', 'Unknown')}",
        f"- Replay lock: {summary.get('replay_lock', 'Unknown')}",
        f"- Case readiness: {summary.get('case_readiness', 'Unknown')}",
        f"- Accepted replay-time sources: {summary.get('accepted_sources', 0)}",
        f"- Blocked future sources: {summary.get('blocked_future_sources', 0)}",
        f"- Rejected sources: {summary.get('rejected_sources', 0)}",
        f"- Missing requirements: {missing_text}",
        "",
        "## Current Evidence Shape",
        "",
        "- Replay-eligible sources can support event-time narrative curation.",
        "- Blocked future sources are quarantined for validation only.",
        "- This worksheet is for curation triage only; it is not a public real-case claim set.",
        "",
        "## Replay-Eligible Sources",
        "",
        "| Source | Published At | Title | URL | Excerpt |",
        "|---|---:|---|---|---|",
    ]
    lines.extend(_worksheet_source_row(source) for source in allowed)
    lines.extend(
        [
            "",
            "## Blocked Future Sources",
            "",
            "| Source | Published At | Title | URL | Excerpt |",
            "|---|---:|---|---|---|",
        ]
    )
    lines.extend(_worksheet_source_row(source) for source in blocked)
    lines.extend(["", "## Narrative Slots To Curate", ""])
    for idx in range(1, 6):
        lines.extend(
            [
                f"### Narrative {idx}",
                "",
                "- Title: TBD",
                "- Thesis: TBD",
                "- Mechanism: TBD",
                "- Replay-safe supporting source IDs (`supporting_source_ids`): TBD",
                "- Replay-safe contradicting source IDs (`contradicting_source_ids`): TBD",
                "- Future supporting source IDs (`future_supporting_source_ids`): TBD",
                "- Future contradicting source IDs (`future_contradicting_source_ids`): TBD",
                "",
            ]
        )
    lines.extend(
        [
            "## Next Evidence Needed",
            "",
            "- Frozen market bars for the event company plus peers or sector.",
            "- Timestamped news, transcript, filing, or estimate evidence available before the replay lock.",
            "- At least one future source for validation only.",
            "- A contradiction source for at least one competing narrative.",
            "- Human-curated 3-5 competing narratives before `real-pack-build --require-narratives` can pass.",
        ]
    )
    return lines


def _worksheet_source_row(source: dict[str, Any]) -> str:
    return (
        f"| {_markdown_cell(source.get('source_id'))} "
        f"| {_markdown_cell(source.get('published_at'))} "
        f"| {_markdown_cell(source.get('title'), limit=120)} "
        f"| {_markdown_cell(source.get('url'), limit=160)} "
        f"| {_markdown_cell(source.get('claim_extracted') or source.get('document_text'), limit=320)} |"
    )


def _markdown_cell(value: Any, *, limit: int = 320) -> str:
    text = " ".join(str(value or "").split())
    text = text.replace("|", "\\|")
    if len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def _curation_source_preview(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": source.get("source_id"),
        "availability_status": source.get("availability_status"),
        "source_type": source.get("source_type"),
        "publisher": source.get("publisher"),
        "title": source.get("title"),
        "published_at": source.get("published_at"),
        "url": source.get("url"),
        "excerpt": _truncate_text(
            str(source.get("claim_extracted") or source.get("document_text") or ""),
            max_chars=420,
        ),
    }


def _curation_narrative_slot(ticker: str, idx: int) -> dict[str, Any]:
    return {
        "narrative_id": f"NARR-{ticker}-{idx:03d}",
        "title": "TBD",
        "narrative": "TBD",
        "mechanism": "TBD",
        "directional_implication": "mixed",
        "time_horizon": "20 trading days",
        "expected_observables": ["TBD"],
        "supporting_source_ids": [],
        "contradicting_source_ids": [],
        "future_supporting_source_ids": [],
        "future_contradicting_source_ids": [],
        "scoring_inputs": {
            "evidence_strength": 0.5,
            "mechanism_specificity": 0.5,
            "source_independence": 0.5,
            "cross_sectional_fit": 0.5,
            "contradiction_resistance": 0.5,
            "timestamp_advantage": 0.5,
            "forward_observable_quality": 0.5,
            "crowding_risk": 0.3,
            "unsupported_claim_penalty": 0.05,
        },
    }


def _curated_narratives_from_payload(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("narratives"), list):
        return payload["narratives"]
    raise RealProvenanceError("Curated narratives payload must be a list or an object with narratives")


def _validate_curated_narrative_shape(narrative: dict[str, Any], idx: int, errors: list[str]) -> None:
    missing = sorted(REQUIRED_NARRATIVE_FIELDS - set(narrative.keys()))
    if missing:
        errors.append(f"narratives[{idx}] missing required fields: {', '.join(missing)}")
        return
    if not str(narrative.get("narrative_id") or "").strip():
        errors.append(f"narratives[{idx}].narrative_id is required")
    for field in ["title", "narrative", "mechanism", "time_horizon"]:
        if _is_placeholder(narrative.get(field)):
            errors.append(f"narratives[{idx}].{field} must replace the TBD placeholder")
    if narrative.get("directional_implication") not in ALLOWED_DIRECTIONS:
        errors.append(f"narratives[{idx}].directional_implication invalid")
    observables = narrative.get("expected_observables")
    if not isinstance(observables, list) or any(not isinstance(item, str) or not item.strip() for item in observables):
        errors.append(f"narratives[{idx}].expected_observables must contain non-empty strings")
    elif any(_is_placeholder(item) for item in observables):
        errors.append(f"narratives[{idx}].expected_observables must replace TBD placeholders")
    scoring = narrative.get("scoring_inputs")
    if not isinstance(scoring, dict):
        errors.append(f"narratives[{idx}].scoring_inputs must be an object")
        return
    missing_scores = sorted(REQUIRED_SCORING_FIELDS - set(scoring.keys()))
    if missing_scores:
        errors.append(f"narratives[{idx}].scoring_inputs missing required fields: {', '.join(missing_scores)}")
    for score_key in sorted(REQUIRED_SCORING_FIELDS & set(scoring.keys())):
        if not _score01(scoring[score_key]):
            errors.append(f"narratives[{idx}].scoring_inputs.{score_key} must be a number from 0 to 1")


def _string_list(value: Any, label: str, errors: list[str]) -> list[str]:
    if value is None or value == "":
        return []
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return []
    return [str(item) for item in value if str(item).strip()]


def _score01(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and 0 <= value <= 1


def _is_placeholder(value: Any) -> bool:
    return str(value or "").strip().upper() == "TBD"


def _candidate_from_finnhub_news(
    item: Any,
    *,
    raw_path: str,
    retrieved_at: str,
    replay_lock: datetime,
    counters: dict[str, int],
) -> SourceCandidate:
    if not isinstance(item, dict):
        return _candidate(
            source_id=_next_candidate_id(counters, "FINNHUB-NEWS"),
            provider="finnhub",
            publisher="",
            title="",
            url="",
            published_at="",
            retrieved_at=retrieved_at,
            source_type="news",
            excerpt="",
            raw_artifact_path=raw_path,
            replay_lock=replay_lock,
        )
    headline = str(item.get("headline") or "").strip()
    summary = str(item.get("summary") or "").strip()
    text = _join_text(headline, summary)
    published_at = _iso_timestamp(datetime.fromtimestamp(int(item["datetime"]), timezone.utc)) if item.get("datetime") else ""
    return _candidate(
        source_id=_next_candidate_id(counters, "FINNHUB-NEWS"),
        provider="finnhub",
        publisher=str(item.get("source") or ""),
        title=headline,
        url=str(item.get("url") or ""),
        published_at=published_at,
        retrieved_at=retrieved_at,
        source_type="news",
        excerpt=text,
        raw_artifact_path=raw_path,
        replay_lock=replay_lock,
    )


def _candidate_from_sec_filing(
    filing: dict[str, Any],
    *,
    raw_path: str,
    retrieved_at: str,
    replay_lock: datetime,
    counters: dict[str, int],
    document_text: str,
) -> SourceCandidate:
    company_name = str(filing.get("company_name") or filing.get("ticker") or "Company")
    title = f"{company_name} {filing.get('form', 'filing')} filed {filing.get('filing_date', '')}".strip()
    claim = f"{company_name} filed {filing.get('form', 'filing')} on {filing.get('filing_date', 'unknown date')}."
    excerpt = _sec_filing_excerpt(document_text, fallback=claim)
    return _candidate(
        source_id=_next_candidate_id(counters, "SEC"),
        provider="sec",
        publisher="SEC EDGAR",
        title=title,
        url=str(filing.get("url") or ""),
        published_at=str(filing.get("accepted_at") or ""),
        retrieved_at=retrieved_at,
        source_type="filing",
        excerpt=excerpt,
        raw_artifact_path=raw_path,
        replay_lock=replay_lock,
    )


def _candidate_from_newsapi_article(
    item: Any,
    *,
    raw_path: str,
    retrieved_at: str,
    replay_lock: datetime,
    counters: dict[str, int],
) -> SourceCandidate:
    if not isinstance(item, dict):
        return _candidate(
            source_id=_next_candidate_id(counters, "NEWSAPI"),
            provider="newsapi",
            publisher="",
            title="",
            url="",
            published_at="",
            retrieved_at=retrieved_at,
            source_type="news",
            excerpt="",
            raw_artifact_path=raw_path,
            replay_lock=replay_lock,
        )
    source = item.get("source", {})
    publisher = source.get("name") if isinstance(source, dict) else ""
    title = str(item.get("title") or "").strip()
    text = _join_text(title, str(item.get("description") or "").strip(), str(item.get("content") or "").strip())
    return _candidate(
        source_id=_next_candidate_id(counters, "NEWSAPI"),
        provider="newsapi",
        publisher=str(publisher or ""),
        title=title,
        url=str(item.get("url") or ""),
        published_at=str(item.get("publishedAt") or ""),
        retrieved_at=retrieved_at,
        source_type="news",
        excerpt=_truncate_text(text),
        raw_artifact_path=raw_path,
        replay_lock=replay_lock,
    )


def _candidate(
    *,
    source_id: str,
    provider: str,
    publisher: str,
    title: str,
    url: str,
    published_at: str,
    retrieved_at: str,
    source_type: str,
    excerpt: str,
    raw_artifact_path: str,
    replay_lock: datetime,
) -> SourceCandidate:
    missing = []
    for field, value in [
        ("publisher", publisher),
        ("title", title),
        ("url", url),
        ("published_at", published_at),
        ("retrieved_at", retrieved_at),
        ("excerpt", excerpt),
        ("raw_artifact_path", raw_artifact_path),
    ]:
        if not str(value or "").strip():
            missing.append(field)
    parsed_published_at: datetime | None = None
    parsed_retrieved_at: datetime | None = None
    if published_at:
        try:
            parsed_published_at = _coerce_datetime(published_at)
        except RealProvenanceError:
            missing.append("published_at_timezone")
    if retrieved_at:
        try:
            parsed_retrieved_at = _coerce_datetime(retrieved_at)
        except RealProvenanceError:
            missing.append("retrieved_at_timezone")
    if parsed_retrieved_at and parsed_published_at and parsed_retrieved_at < parsed_published_at:
        missing.append("retrieved_at_before_published_at")
    content_hash = source_content_hash(excerpt) if excerpt else ""
    if not content_hash:
        missing.append("content_hash")
    if missing:
        replay_status = "rejected"
        rejection_reason = "missing_or_invalid: " + ", ".join(dict.fromkeys(missing))
    else:
        replay_status = "blocked_future" if parsed_published_at and parsed_published_at > replay_lock else "eligible"
        rejection_reason = None
    return SourceCandidate(
        source_id=source_id,
        provider=provider,
        publisher=publisher,
        title=title,
        url=url,
        published_at=_iso_timestamp(parsed_published_at) if parsed_published_at else str(published_at or ""),
        retrieved_at=_iso_timestamp(parsed_retrieved_at) if parsed_retrieved_at else str(retrieved_at or ""),
        source_type=source_type if source_type in CANDIDATE_SOURCE_TYPES else "other",
        excerpt=_truncate_text(excerpt),
        raw_artifact_path=raw_artifact_path,
        content_hash=content_hash,
        replay_status=replay_status,
        rejection_reason=rejection_reason,
    )


def _fetch_json_artifact(
    fetcher: JsonFetcher,
    manifest: dict[str, Any],
    root: Path,
    *,
    provider: str,
    endpoint: str,
    rel_path: str,
    url: str,
    params: dict[str, Any] | None,
    headers: dict[str, str] | None,
    retrieved_at: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        payload = fetcher.get_json(url, params=params, headers=headers)
        path = _artifact_path(root, rel_path)
        _write_json(path, payload)
        artifact = _artifact(
            provider=provider,
            endpoint=endpoint,
            rel_path=rel_path,
            url=url,
            params=params,
            headers=headers,
            retrieved_at=retrieved_at,
            status="ok",
            content=path.read_text(),
            error=None,
            extra=extra,
        )
    except Exception as exc:  # pragma: no cover - exact provider failures vary
        artifact = _artifact(
            provider=provider,
            endpoint=endpoint,
            rel_path=rel_path,
            url=url,
            params=params,
            headers=headers,
            retrieved_at=retrieved_at,
            status="error",
            content="",
            error=str(exc),
            extra=extra,
        )
        manifest["errors"].append(f"{provider}.{endpoint}: {_redact_secret_text(str(exc))}")
    manifest["artifacts"].append(artifact)
    return artifact


def _fetch_text_artifact(
    fetcher: JsonFetcher,
    manifest: dict[str, Any],
    root: Path,
    *,
    provider: str,
    endpoint: str,
    rel_path: str,
    url: str,
    params: dict[str, Any] | None,
    headers: dict[str, str] | None,
    retrieved_at: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        text = fetcher.get_text(url, params=params, headers=headers)
        path = _artifact_path(root, rel_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        artifact = _artifact(
            provider=provider,
            endpoint=endpoint,
            rel_path=rel_path,
            url=url,
            params=params,
            headers=headers,
            retrieved_at=retrieved_at,
            status="ok",
            content=text,
            error=None,
            extra=extra,
        )
    except Exception as exc:  # pragma: no cover - exact provider failures vary
        artifact = _artifact(
            provider=provider,
            endpoint=endpoint,
            rel_path=rel_path,
            url=url,
            params=params,
            headers=headers,
            retrieved_at=retrieved_at,
            status="error",
            content="",
            error=str(exc),
            extra=extra,
        )
        manifest["errors"].append(f"{provider}.{endpoint}: {_redact_secret_text(str(exc))}")
    manifest["artifacts"].append(artifact)
    return artifact


def _artifact(
    *,
    provider: str,
    endpoint: str,
    rel_path: str,
    url: str,
    params: dict[str, Any] | None,
    headers: dict[str, str] | None,
    retrieved_at: str,
    status: str,
    content: str,
    error: str | None,
    extra: dict[str, Any] | None,
) -> dict[str, Any]:
    artifact = {
        "provider": provider,
        "endpoint": endpoint,
        "path": rel_path,
        "url": url,
        "params": _redact_mapping(params or {}),
        "headers": _redact_mapping(headers or {}),
        "retrieved_at": retrieved_at,
        "status": status,
        "content_hash": source_content_hash(content) if content else "",
        "error": _redact_secret_text(error) if error else None,
    }
    if extra:
        artifact.update(extra)
    return artifact


def _record_error(manifest: dict[str, Any], *, provider: str, endpoint: str, error: str) -> None:
    redacted = _redact_secret_text(error)
    manifest["errors"].append(f"{provider}.{endpoint}: {redacted}")
    manifest["artifacts"].append(
        {
            "provider": provider,
            "endpoint": endpoint,
            "path": "",
            "url": "",
            "params": {},
            "headers": {},
            "retrieved_at": manifest.get("retrieved_at"),
            "status": "error",
            "content_hash": "",
            "error": redacted,
        }
    )


def _select_recent_sec_filings(
    data: dict[str, Any],
    *,
    ticker: str,
    cik: str,
    forms: list[str],
    count: int,
) -> list[dict[str, Any]]:
    recent = data.get("filings", {}).get("recent", {}) if isinstance(data, dict) else {}
    normalized_forms = {form.upper() for form in forms}
    filings = []
    for idx, form in enumerate(recent.get("form", [])):
        form = str(form).upper()
        if form not in normalized_forms:
            continue
        accession = _array_value(recent, "accessionNumber", idx)
        document = _array_value(recent, "primaryDocument", idx)
        filing_date = _array_value(recent, "filingDate", idx)
        accepted_at = _parse_sec_accepted_at(_array_value(recent, "acceptanceDateTime", idx), filing_date)
        if not accession or not document:
            continue
        compact = accession.replace("-", "")
        padded_cik = str(cik).zfill(10)
        filings.append(
            {
                "ticker": ticker,
                "cik": padded_cik,
                "company_name": data.get("name", ticker),
                "form": form,
                "accession": accession,
                "document": document,
                "filing_date": filing_date,
                "accepted_at": accepted_at,
                "url": f"https://www.sec.gov/Archives/edgar/data/{padded_cik.lstrip('0')}/{compact}/{document}",
            }
        )
        if len(filings) >= count:
            break
    return filings


def _parse_sec_accepted_at(accepted_at: str, filing_date: str) -> str:
    if accepted_at:
        value = accepted_at.rstrip("Z")
        if re.match(r"^\d{4}-\d{2}-\d{2}T", value):
            return _iso_timestamp(_coerce_datetime(f"{value}+00:00"))
    if filing_date:
        return _iso_timestamp(_coerce_datetime(f"{filing_date}T00:00:00+00:00"))
    return ""


def _market_rows_from_finnhub_candles(
    path: Path,
    symbol: str,
    *,
    replay_lock: datetime,
) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    if payload.get("s") != "ok":
        return []
    timestamps = payload.get("t", [])
    opens = payload.get("o", [])
    closes = payload.get("c", [])
    volumes = payload.get("v", [])
    rows = []
    for idx, epoch in enumerate(timestamps):
        if idx >= len(opens) or idx >= len(closes):
            continue
        candle_timestamp = datetime.fromtimestamp(int(epoch), timezone.utc)
        if candle_timestamp.date() >= replay_lock.astimezone(timezone.utc).date():
            continue
        rows.append(
            {
                "date": candle_timestamp.date().isoformat(),
                "ticker": symbol.upper(),
                "open": opens[idx],
                "close": closes[idx],
                "volume": volumes[idx] if idx < len(volumes) else "",
            }
        )
    return rows


def _write_market_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "ticker", "open", "close", "volume"])
        writer.writeheader()
        for row in sorted(rows, key=lambda item: (str(item["ticker"]), str(item["date"]))):
            writer.writerow(row)


def _append_candidate(
    candidate: SourceCandidate,
    candidates: list[SourceCandidate],
    rejected: list[SourceCandidate],
) -> None:
    if candidate.replay_status == "rejected":
        rejected.append(candidate)
    else:
        candidates.append(candidate)


def _load_candidates(path: Path) -> list[SourceCandidate]:
    payload = json.loads(path.read_text())
    raw_items = payload.get("candidates", payload if isinstance(payload, list) else [])
    return [SourceCandidate(**item) for item in raw_items if isinstance(item, dict)]


def _load_rejected_candidates(path: Path) -> list[SourceCandidate]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    raw_items = payload.get("rejected_candidates", payload if isinstance(payload, list) else [])
    return [SourceCandidate(**item) for item in raw_items if isinstance(item, dict)]


def _load_json_list(path: Path) -> list[Any]:
    payload = json.loads(path.read_text())
    return payload if isinstance(payload, list) else []


def _sec_document_artifacts(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    artifacts = {}
    for artifact in manifest.get("artifacts", []):
        if artifact.get("provider") == "sec" and artifact.get("endpoint") == "filing_document" and artifact.get("status") == "ok":
            artifacts[str(artifact.get("accession"))] = artifact
    return artifacts


def _has_market_rows(path: Path, *, ticker: str | None = None, replay_lock: datetime | None = None) -> bool:
    if not path.exists():
        return False
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if ticker and str(row.get("ticker", "")).upper() != ticker.upper():
                continue
            if replay_lock is not None and not _market_row_before_lock(row, replay_lock):
                continue
            try:
                float(row.get("open", ""))
                float(row.get("close", ""))
            except (TypeError, ValueError):
                continue
            return True
    return False


def _market_row_before_lock(row: dict[str, Any], replay_lock: datetime) -> bool:
    raw_date = str(row.get("date", "")).strip()
    if not raw_date:
        return False
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", raw_date):
            return datetime.fromisoformat(raw_date).date() <= replay_lock.date()
        timestamp = parse_datetime(raw_date)
    except ValueError:
        return False
    if timestamp.tzinfo is None:
        return timestamp <= replay_lock.replace(tzinfo=None)
    return timestamp <= replay_lock.astimezone(timestamp.tzinfo)


def _draft_market_bars_path(
    *,
    normalized_path: Path,
    output_dir: Path,
    market_bars_path: str | Path | None,
) -> Path:
    if market_bars_path is None:
        return normalized_path / "market_bars.csv"

    source = Path(market_bars_path)
    if not source.exists():
        raise RealProvenanceError(f"market_bars_path does not exist: {source}")
    destination = output_dir / "market_bars.csv"
    if source.resolve() != destination.resolve():
        shutil.copyfile(source, destination)
    return destination


def _resolve_cik_from_ticker_map(data: Any, ticker: str) -> str | None:
    if not isinstance(data, dict):
        return None
    for item in data.values():
        if not isinstance(item, dict):
            continue
        if str(item.get("ticker", "")).upper() == ticker.upper():
            return str(item.get("cik_str", "")).zfill(10)
    return None


def _parse_providers(providers: list[str] | tuple[str, ...] | str) -> list[str]:
    if isinstance(providers, str):
        raw = providers.split(",")
    else:
        raw = list(providers)
    parsed = []
    for provider in raw:
        normalized = str(provider).strip().lower()
        if not normalized:
            continue
        if normalized not in {"finnhub", "sec", "newsapi"}:
            raise RealProvenanceError(f"Unsupported real-data provider: {normalized}")
        parsed.append(normalized)
    return parsed or list(DEFAULT_PROVIDERS)


def _date_bound(value: str, *, end_of_day: bool) -> datetime:
    suffix = "T23:59:59+00:00" if end_of_day else "T00:00:00+00:00"
    return _coerce_datetime(f"{value}{suffix}" if re.match(r"^\d{4}-\d{2}-\d{2}$", value) else value)


def _coerce_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = parse_datetime(value)
        except ValueError as exc:
            raise RealProvenanceError(f"Invalid timestamp: {value}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RealProvenanceError(f"Timestamp must include a timezone offset: {value}")
    return parsed


def _iso_timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _next_candidate_id(counters: dict[str, int], prefix: str) -> str:
    counters[prefix] = counters.get(prefix, 0) + 1
    return f"{prefix}-{counters[prefix]:03d}"


def _array_value(data: dict[str, Any], key: str, idx: int) -> str:
    values = data.get(key, [])
    if not isinstance(values, list) or idx >= len(values):
        return ""
    return str(values[idx] or "")


def _sec_headers(user_agent: str, *, host: str) -> dict[str, str]:
    return {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate", "Host": host}


def _artifact_path(root: Path, rel_path: str) -> Path:
    path = Path(rel_path)
    if path.is_absolute() or ".." in path.parts:
        raise RealProvenanceError(f"Artifact path must stay inside fetch directory: {rel_path}")
    resolved_root = root.resolve()
    resolved_path = (resolved_root / path).resolve()
    if resolved_root != resolved_path and resolved_root not in resolved_path.parents:
        raise RealProvenanceError(f"Artifact path must stay inside fetch directory: {rel_path}")
    return resolved_path


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "artifact"


def _redact_mapping(values: dict[str, Any]) -> dict[str, Any]:
    redacted = {}
    for key, value in values.items():
        if key.lower() in SECRET_PARAM_NAMES:
            redacted[key] = "[REDACTED]"
        else:
            redacted[key] = value
    return redacted


def _redact_secret_text(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"(token|apikey|api[_-]?key)=([^&\s]+)", r"\1=[REDACTED]", value, flags=re.I)


def _normalize_text(value: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", value)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<ix:header[^>]*>.*?</ix:header>", " ", text)
    text = re.sub(r"(?is)<ix:hidden[^>]*>.*?</ix:hidden>", " ", text)
    text = re.sub(r"(?is)<ix:resources[^>]*>.*?</ix:resources>", " ", text)
    text = re.sub(r"(?is)<ix:references[^>]*>.*?</ix:references>", " ", text)
    text = re.sub(r"(?is)<xbrli:context[^>]*>.*?</xbrli:context>", " ", text)
    text = re.sub(r"(?is)<xbrli:unit[^>]*>.*?</xbrli:unit>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _truncate_text(value: str, *, max_chars: int = 1000) -> str:
    cleaned = _normalize_text(value)
    return cleaned[:max_chars].rstrip()


def _join_text(*parts: str) -> str:
    return _truncate_text(" ".join(part for part in parts if part and part.strip()))


def _sec_filing_excerpt(document_text: str, *, fallback: str) -> str:
    cleaned = _normalize_text(document_text or "")
    if not cleaned:
        return _truncate_text(fallback)
    patterns = (
        "Item 2.02",
        "Segment Operating Performance",
        "Products and Services Performance",
        "Results of Operations This Item",
        "Results of Operations",
        "Net sales",
        "CONDENSED CONSOLIDATED STATEMENTS",
        "iPhone",
        "Services",
        "share repurchase",
        "dividend",
    )
    lower = cleaned.lower()
    for pattern in patterns:
        position = lower.find(pattern.lower())
        if position >= 0:
            return _truncate_text(cleaned[position:])
    return _truncate_text(cleaned)


def _relative_path(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        import os

        return os.path.relpath(path, base)


def _sleep_if_needed(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
