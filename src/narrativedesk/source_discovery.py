from __future__ import annotations

import json
import ipaddress
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from narrativedesk.models import parse_datetime
from narrativedesk.real_data import JsonFetcher, UrllibJsonFetcher
from narrativedesk.real_provenance import (
    SourceCandidate,
    _candidate,
    _coerce_datetime,
    _iso_timestamp,
    _normalize_text,
    _safe_filename,
    _truncate_text,
    _write_json,
)
from narrativedesk.source_pack import source_content_hash


class SourceDiscoveryError(ValueError):
    """Raised when source discovery cannot run without weakening provenance."""


class JsonPoster(Protocol):
    def post_json(
        self,
        url: str,
        *,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> Any: ...


@dataclass(frozen=True)
class UrllibJsonPoster:
    timeout_seconds: float = 30

    def post_json(
        self,
        url: str,
        *,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> Any:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", **(headers or {})},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))


DISCOVERY_STATUSES = {"candidate", "rejected"}
SONAR_ENDPOINT = "https://api.perplexity.ai/v1/sonar"
DEFAULT_SONAR_MODEL = "sonar"


@dataclass(frozen=True)
class DiscoveryCandidate:
    candidate_id: str
    provider: str
    model: str
    query: str
    title: str
    url: str
    published_at_hint: str
    publisher_hint: str
    snippet: str
    discovered_at: str
    raw_response_path: str
    raw_response_hash: str
    status: str
    rejection_reason: str | None

    def __post_init__(self) -> None:
        if self.provider != "perplexity":
            raise SourceDiscoveryError(f"Unsupported discovery provider: {self.provider}")
        if self.status not in DISCOVERY_STATUSES:
            raise SourceDiscoveryError(f"Unsupported discovery status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def discover_sources_with_sonar(
    *,
    ticker: str,
    company_name: str,
    event_date: str,
    replay_lock: str | datetime,
    query: str,
    out_dir: str | Path,
    api_key: str | None,
    model: str | None = None,
    poster: JsonPoster | None = None,
    discovered_at: str | datetime | None = None,
    endpoint: str = SONAR_ENDPOINT,
    search_domains: list[str] | tuple[str, ...] | str | None = None,
    search_before_date: str | None = None,
    search_after_date: str | None = None,
) -> dict[str, Any]:
    if not api_key:
        raise SourceDiscoveryError("PERPLEXITY_API_KEY is required for real-source-discover")
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    lock = _coerce_datetime(replay_lock)
    now = _iso_timestamp(_coerce_datetime(discovered_at) if discovered_at else datetime.now(timezone.utc))
    normalized_model = str(model or DEFAULT_SONAR_MODEL).strip() or DEFAULT_SONAR_MODEL
    clean_query = str(query or "").strip()
    if not clean_query:
        raise SourceDiscoveryError("real-source-discover requires a non-empty query")

    request_payload = _sonar_request_payload(
        ticker=ticker,
        company_name=company_name,
        event_date=event_date,
        replay_lock=_iso_timestamp(lock),
        query=clean_query,
        model=normalized_model,
        search_domains=search_domains,
        search_before_date=search_before_date,
        search_after_date=search_after_date,
    )
    _write_json(
        output_dir / "discovery_request.json",
        {
            "provider": "perplexity",
            "endpoint": endpoint,
            "headers": {"Authorization": "Bearer [REDACTED]", "Content-Type": "application/json"},
            "payload": request_payload,
            "created_at": now,
            "note": "Sonar output is discovery-only and is not evidence until URLs are refetched and hashed.",
        },
    )

    try:
        response = (poster or UrllibJsonPoster()).post_json(
            endpoint,
            payload=request_payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
    except Exception as exc:  # pragma: no cover - exact provider failures vary
        raise SourceDiscoveryError(f"perplexity.sonar: {_redact_secret_text(str(exc))}") from exc

    raw_response_path = output_dir / "raw_response.json"
    _write_json(raw_response_path, response)
    raw_response_text = raw_response_path.read_text()
    raw_response_hash = source_content_hash(raw_response_text)
    candidates, rejected = discovery_candidates_from_sonar_response(
        response,
        model=normalized_model,
        query=clean_query,
        discovered_at=now,
        raw_response_path="raw_response.json",
        raw_response_hash=raw_response_hash,
    )
    _write_json(
        output_dir / "discovery_candidates.json",
        {
            "generated_at": now,
            "provider": "perplexity",
            "model": normalized_model,
            "query": clean_query,
            "replay_lock": _iso_timestamp(lock),
            "candidates": [candidate.to_dict() for candidate in candidates],
        },
    )
    _write_json(
        output_dir / "rejected_discovery_candidates.json",
        {
            "generated_at": now,
            "provider": "perplexity",
            "model": normalized_model,
            "query": clean_query,
            "rejected_candidates": [candidate.to_dict() for candidate in rejected],
        },
    )
    summary = {
        "ok": True,
        "out_dir": str(output_dir),
        "request_out": str(output_dir / "discovery_request.json"),
        "raw_response_out": str(raw_response_path),
        "discovery_candidates_out": str(output_dir / "discovery_candidates.json"),
        "rejected_discovery_candidates_out": str(output_dir / "rejected_discovery_candidates.json"),
        "candidate_count": len(candidates),
        "rejected_candidate_count": len(rejected),
        "generated_answer_saved_for_audit": bool(_sonar_message_text(response)),
        "next_action": "Run real-source-freeze to refetch candidate URLs before using any source as evidence.",
    }
    _write_json(output_dir / "discovery_summary.json", summary)
    return summary


def discovery_candidates_from_sonar_response(
    response: Any,
    *,
    model: str,
    query: str,
    discovered_at: str,
    raw_response_path: str,
    raw_response_hash: str,
) -> tuple[list[DiscoveryCandidate], list[DiscoveryCandidate]]:
    raw_candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    if isinstance(response, dict):
        for item in response.get("search_results", []) or []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            raw_candidates.append(
                {
                    "title": str(item.get("title") or "").strip(),
                    "url": url,
                    "published_at_hint": str(item.get("date") or item.get("last_updated") or "").strip(),
                    "publisher_hint": _publisher_hint_from_url(url),
                    "snippet": str(item.get("snippet") or "").strip(),
                }
            )
            if url:
                seen_urls.add(url)
        for citation_url in response.get("citations", []) or []:
            url = str(citation_url or "").strip()
            if not url or url in seen_urls:
                continue
            raw_candidates.append(
                {
                    "title": "",
                    "url": url,
                    "published_at_hint": "",
                    "publisher_hint": _publisher_hint_from_url(url),
                    "snippet": "",
                }
            )
            seen_urls.add(url)

    candidates: list[DiscoveryCandidate] = []
    rejected: list[DiscoveryCandidate] = []
    for idx, item in enumerate(raw_candidates, start=1):
        candidate = _discovery_candidate(
            candidate_id=f"PERPLEXITY-DISC-{idx:03d}",
            model=model,
            query=query,
            title=item["title"],
            url=item["url"],
            published_at_hint=item["published_at_hint"],
            publisher_hint=item["publisher_hint"],
            snippet=item["snippet"],
            discovered_at=discovered_at,
            raw_response_path=raw_response_path,
            raw_response_hash=raw_response_hash,
        )
        if candidate.status == "rejected":
            rejected.append(candidate)
        else:
            candidates.append(candidate)
    return candidates, rejected


def freeze_discovery_candidates(
    *,
    discovery_dir: str | Path,
    replay_lock: str | datetime,
    out_dir: str | Path | None = None,
    normalized_dir: str | Path | None = None,
    fetcher: JsonFetcher | None = None,
    generated_at: str | datetime | None = None,
    source_type: str = "news",
) -> dict[str, Any]:
    discovery_path = Path(discovery_dir)
    candidates_path = discovery_path / "discovery_candidates.json"
    if not candidates_path.exists():
        raise SourceDiscoveryError(f"discovery_candidates.json not found: {candidates_path}")
    output_dir = Path(out_dir) if out_dir else discovery_path / "frozen"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_pages_dir = discovery_path / "raw_pages"
    raw_pages_dir.mkdir(parents=True, exist_ok=True)
    lock = _coerce_datetime(replay_lock)
    now = _iso_timestamp(_coerce_datetime(generated_at) if generated_at else datetime.now(timezone.utc))
    fetch = fetcher or UrllibJsonFetcher()

    existing_candidates: list[SourceCandidate] = []
    existing_rejected: list[SourceCandidate] = []
    normalized_path = Path(normalized_dir) if normalized_dir else None
    if normalized_path:
        existing_candidates = _load_source_candidates(normalized_path / "source_candidates.json", "candidates")
        existing_rejected = _load_source_candidates(normalized_path / "rejected_candidates.json", "rejected_candidates")

    counters = {"PERPLEXITY": _max_prefix_number([*existing_candidates, *existing_rejected], "PERPLEXITY")}
    source_candidates: list[SourceCandidate] = []
    rejected_candidates: list[SourceCandidate] = []
    discovery_candidates = _load_discovery_candidates(candidates_path)
    for discovery_candidate in discovery_candidates:
        if discovery_candidate.status != "candidate":
            continue
        source_id = _next_source_id(counters, "PERPLEXITY")
        if not _is_http_url(discovery_candidate.url):
            rejected_candidates.append(
                _rejected_source_candidate(
                    source_id=source_id,
                    discovery_candidate=discovery_candidate,
                    retrieved_at=now,
                    reason="unsafe_or_unsupported_url",
                    source_type=source_type,
                )
            )
            continue
        try:
            html_text = fetch.get_text(discovery_candidate.url, headers={"User-Agent": "NarrativeDesk source discovery"})
        except Exception as exc:  # pragma: no cover - exact provider failures vary
            rejected_candidates.append(
                _rejected_source_candidate(
                    source_id=source_id,
                    discovery_candidate=discovery_candidate,
                    retrieved_at=now,
                    reason=f"fetch_error: {_redact_secret_text(str(exc))}",
                    source_type=source_type,
                )
            )
            continue
        raw_path = raw_pages_dir / _raw_page_filename(discovery_candidate.url, source_id)
        raw_path.write_text(html_text)
        title = _page_title(html_text)
        publisher = _page_publisher(html_text)
        published_at = _page_published_at(html_text, replay_lock=lock)
        excerpt = _page_excerpt(html_text)
        if len(excerpt) < 40:
            excerpt = ""
        candidate = _candidate(
            source_id=source_id,
            provider="perplexity-refetch",
            publisher=publisher,
            title=title,
            url=discovery_candidate.url,
            published_at=published_at,
            retrieved_at=now,
            source_type=source_type,
            excerpt=excerpt,
            raw_artifact_path=str(raw_path),
            replay_lock=lock,
        )
        if candidate.replay_status == "rejected":
            rejected_candidates.append(candidate)
        else:
            source_candidates.append(candidate)

    _write_source_candidate_payload(
        output_dir / "source_candidates.json",
        key="candidates",
        items=source_candidates,
        generated_at=now,
        replay_lock=_iso_timestamp(lock),
    )
    _write_source_candidate_payload(
        output_dir / "rejected_candidates.json",
        key="rejected_candidates",
        items=rejected_candidates,
        generated_at=now,
        replay_lock=_iso_timestamp(lock),
    )

    appended_candidates = 0
    appended_rejected = 0
    if normalized_path:
        normalized_path.mkdir(parents=True, exist_ok=True)
        merged_candidates, appended_candidates = _merge_source_candidates(existing_candidates, source_candidates)
        merged_rejected, appended_rejected = _merge_source_candidates(existing_rejected, rejected_candidates)
        _write_source_candidate_payload(
            normalized_path / "source_candidates.json",
            key="candidates",
            items=merged_candidates,
            generated_at=now,
            replay_lock=_iso_timestamp(lock),
        )
        _write_source_candidate_payload(
            normalized_path / "rejected_candidates.json",
            key="rejected_candidates",
            items=merged_rejected,
            generated_at=now,
            replay_lock=_iso_timestamp(lock),
        )

    eligible_count = len([candidate for candidate in source_candidates if candidate.replay_status == "eligible"])
    blocked_count = len([candidate for candidate in source_candidates if candidate.replay_status == "blocked_future"])
    summary = {
        "ok": True,
        "discovery_dir": str(discovery_path),
        "out_dir": str(output_dir),
        "normalized_dir": str(normalized_path) if normalized_path else None,
        "raw_pages_dir": str(raw_pages_dir),
        "source_candidates_out": str(output_dir / "source_candidates.json"),
        "rejected_candidates_out": str(output_dir / "rejected_candidates.json"),
        "eligible_candidates": eligible_count,
        "blocked_future_candidates": blocked_count,
        "rejected_candidates": len(rejected_candidates),
        "appended_candidates": appended_candidates,
        "appended_rejected_candidates": appended_rejected,
        "next_action": "Run real-case-draft after adding frozen candidates to the normalized real-case directory.",
    }
    _write_json(output_dir / "freeze_summary.json", summary)
    return summary


def _sonar_request_payload(
    *,
    ticker: str,
    company_name: str,
    event_date: str,
    replay_lock: str,
    query: str,
    model: str,
    search_domains: list[str] | tuple[str, ...] | str | None,
    search_before_date: str | None,
    search_after_date: str | None,
) -> dict[str, Any]:
    web_search_options: dict[str, Any] = {"search_mode": "web", "return_related_questions": False}
    domains = _string_list(search_domains)
    if domains:
        web_search_options["search_domain_filter"] = domains
    if search_before_date:
        web_search_options["search_before_date_filter"] = search_before_date
    if search_after_date:
        web_search_options["search_after_date_filter"] = search_after_date
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a source discovery assistant for a replay-safe financial research system. "
                    "Return source leads only. Do not make investment recommendations or assert final claims."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Find timestamped public source pages for {company_name} ({ticker}) around "
                    f"{event_date}. Replay lock: {replay_lock}. Query: {query}. "
                    "Prefer primary filings, company releases, reputable financial news, and later validation sources."
                ),
            },
        ],
        "temperature": 0,
        "max_tokens": 1200,
        "web_search_options": web_search_options,
    }


def _discovery_candidate(
    *,
    candidate_id: str,
    model: str,
    query: str,
    title: str,
    url: str,
    published_at_hint: str,
    publisher_hint: str,
    snippet: str,
    discovered_at: str,
    raw_response_path: str,
    raw_response_hash: str,
) -> DiscoveryCandidate:
    missing = []
    for field, value in [
        ("title", title),
        ("url", url),
        ("published_at_hint", published_at_hint),
        ("publisher_hint", publisher_hint),
        ("snippet", snippet),
    ]:
        if not str(value or "").strip():
            missing.append(field)
    if url and not _is_http_url(url):
        missing.append("safe_http_url")
    status = "rejected" if missing else "candidate"
    return DiscoveryCandidate(
        candidate_id=candidate_id,
        provider="perplexity",
        model=model,
        query=query,
        title=_truncate_text(title, max_chars=300),
        url=url,
        published_at_hint=published_at_hint,
        publisher_hint=publisher_hint,
        snippet=_truncate_text(snippet, max_chars=1000),
        discovered_at=discovered_at,
        raw_response_path=raw_response_path,
        raw_response_hash=raw_response_hash,
        status=status,
        rejection_reason="missing_or_invalid: " + ", ".join(dict.fromkeys(missing)) if missing else None,
    )


def _load_discovery_candidates(path: Path) -> list[DiscoveryCandidate]:
    payload = json.loads(path.read_text())
    raw_items = payload.get("candidates", payload if isinstance(payload, list) else [])
    return [DiscoveryCandidate(**item) for item in raw_items if isinstance(item, dict)]


def _load_source_candidates(path: Path, key: str) -> list[SourceCandidate]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    raw_items = payload.get(key, payload if isinstance(payload, list) else [])
    return [SourceCandidate(**item) for item in raw_items if isinstance(item, dict)]


def _write_source_candidate_payload(
    path: Path,
    *,
    key: str,
    items: list[SourceCandidate],
    generated_at: str,
    replay_lock: str,
) -> None:
    _write_json(
        path,
        {
            "generated_at": generated_at,
            "replay_lock": replay_lock,
            key: [item.to_dict() for item in items],
        },
    )


def _merge_source_candidates(
    existing: list[SourceCandidate],
    incoming: list[SourceCandidate],
) -> tuple[list[SourceCandidate], int]:
    seen = {(item.url, item.content_hash) for item in existing}
    merged = list(existing)
    appended = 0
    for item in incoming:
        identity = (item.url, item.content_hash)
        if identity in seen:
            continue
        merged.append(item)
        seen.add(identity)
        appended += 1
    return merged, appended


def _rejected_source_candidate(
    *,
    source_id: str,
    discovery_candidate: DiscoveryCandidate,
    retrieved_at: str,
    reason: str,
    source_type: str,
) -> SourceCandidate:
    return SourceCandidate(
        source_id=source_id,
        provider="perplexity-refetch",
        publisher=discovery_candidate.publisher_hint,
        title=discovery_candidate.title,
        url=discovery_candidate.url,
        published_at=discovery_candidate.published_at_hint,
        retrieved_at=retrieved_at,
        source_type=source_type,
        excerpt="",
        raw_artifact_path="",
        content_hash="",
        replay_status="rejected",
        rejection_reason=reason,
    )


def _page_title(html_text: str) -> str:
    return _truncate_text(
        _meta_content(html_text, "og:title")
        or _meta_content(html_text, "twitter:title")
        or _title_tag(html_text),
        max_chars=300,
    )


def _page_publisher(html_text: str) -> str:
    return _truncate_text(
        _meta_content(html_text, "og:site_name")
        or _meta_content(html_text, "application-name")
        or _json_ld_publisher(html_text),
        max_chars=200,
    )


def _page_published_at(html_text: str, *, replay_lock: datetime) -> str:
    raw = (
        _meta_content(html_text, "article:published_time")
        or _meta_content(html_text, "datePublished")
        or _meta_content(html_text, "date")
        or _meta_content(html_text, "pubdate")
        or _json_ld_date(html_text)
    )
    return _normalize_page_timestamp(raw, replay_lock=replay_lock)


def _page_excerpt(html_text: str) -> str:
    body = _body_text(html_text)
    return _truncate_text(body, max_chars=1000)


def _meta_content(html_text: str, key: str) -> str:
    escaped_key = re.escape(key)
    patterns = [
        rf"<meta\b(?=[^>]*(?:property|name|itemprop)=['\"]{escaped_key}['\"])[^>]*\bcontent=['\"]([^'\"]+)['\"][^>]*>",
        rf"<meta\b(?=[^>]*\bcontent=['\"]([^'\"]+)['\"])[^>]*(?:property|name|itemprop)=['\"]{escaped_key}['\"][^>]*>",
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.I | re.S)
        if match:
            return _normalize_text(match.group(1))
    return ""


def _title_tag(html_text: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html_text)
    return _normalize_text(match.group(1)) if match else ""


def _json_ld_publisher(html_text: str) -> str:
    for item in _json_ld_objects(html_text):
        publisher = item.get("publisher") if isinstance(item, dict) else None
        if isinstance(publisher, dict):
            name = str(publisher.get("name") or "").strip()
            if name:
                return _normalize_text(name)
        elif isinstance(publisher, str) and publisher.strip():
            return _normalize_text(publisher)
    return ""


def _json_ld_date(html_text: str) -> str:
    for item in _json_ld_objects(html_text):
        for key in ["datePublished", "dateCreated", "dateModified"]:
            value = str(item.get(key) or "").strip() if isinstance(item, dict) else ""
            if value:
                return value
    return ""


def _json_ld_objects(html_text: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for match in re.finditer(r"(?is)<script[^>]+type=['\"]application/ld\+json['\"][^>]*>(.*?)</script>", html_text):
        try:
            payload = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            graph = payload.get("@graph")
            if isinstance(graph, list):
                objects.extend([item for item in graph if isinstance(item, dict)])
            objects.append(payload)
        elif isinstance(payload, list):
            objects.extend([item for item in payload if isinstance(item, dict)])
    return objects


def _body_text(html_text: str) -> str:
    body_match = re.search(r"(?is)<body[^>]*>(.*?)</body>", html_text)
    body = body_match.group(1) if body_match else html_text
    return _normalize_text(body)


def _normalize_page_timestamp(value: str, *, replay_lock: datetime) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            raw_date = datetime.fromisoformat(raw).date()
        except ValueError:
            return ""
        lock_date = replay_lock.date()
        if raw_date == lock_date:
            return ""
        return f"{raw}T00:00:00Z"
    try:
        parsed = parse_datetime(raw)
    except ValueError:
        return ""
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return ""
    return _iso_timestamp(parsed)


def _raw_page_filename(url: str, source_id: str) -> str:
    parsed = urlparse(url)
    path_suffix = _safe_filename(Path(parsed.path).name or "page")
    return f"{source_id}_{_safe_filename(parsed.netloc)}_{path_suffix}.html"


def _publisher_hint_from_url(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.hostname or "").lower()


def _is_http_url(url: str) -> bool:
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False
    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not any(
        [
            address.is_loopback,
            address.is_private,
            address.is_link_local,
            address.is_multicast,
            address.is_reserved,
            address.is_unspecified,
        ]
    )


def _sonar_message_text(response: Any) -> str:
    if not isinstance(response, dict):
        return ""
    parts = []
    for choice in response.get("choices", []) or []:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if isinstance(message, dict):
            content = str(message.get("content") or "").strip()
            if content:
                parts.append(content)
    return "\n".join(parts)


def _redact_secret_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"Bearer\s+[A-Za-z0-9._-]+", "Bearer [REDACTED]", value)
    text = re.sub(r"pplx-[A-Za-z0-9_-]+", "pplx-[REDACTED]", text)
    return re.sub(r"(api[_-]?key|token)=([^&\s]+)", r"\1=[REDACTED]", text, flags=re.I)


def _string_list(values: list[str] | tuple[str, ...] | str | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw_items = values.split(",")
    else:
        raw_items = list(values)
    return [str(item or "").strip() for item in raw_items if str(item or "").strip()]


def _max_prefix_number(candidates: list[SourceCandidate], prefix: str) -> int:
    max_number = 0
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    for candidate in candidates:
        match = pattern.match(candidate.source_id)
        if match:
            max_number = max(max_number, int(match.group(1)))
    return max_number


def _next_source_id(counters: dict[str, int], prefix: str) -> str:
    counters[prefix] = counters.get(prefix, 0) + 1
    return f"{prefix}-{counters[prefix]:03d}"
