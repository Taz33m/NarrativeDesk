from __future__ import annotations

import gzip
import html
import json
import re
import zlib
from csv import DictReader
from dataclasses import dataclass
from datetime import datetime, time as datetime_time, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from narrativedesk.models import parse_datetime
from narrativedesk.source_pack import sanitize_source_record, source_content_hash


class RealDataError(ValueError):
    """Raised when a real-data source pack cannot be built safely."""


REAL_EVIDENCE_SECTIONS = (
    "manual_sources",
    "news",
    "sec_filings",
    "sec_facts",
    "transcripts",
    "estimate_revisions",
)
REAL_OPTIONAL_SECTIONS = ("market_data", *REAL_EVIDENCE_SECTIONS)
LOCAL_MARKET_PROVIDERS = {"csv", "frozen_csv", "local_csv"}
SUPPORTED_MARKET_PROVIDERS = {"finnhub", *LOCAL_MARKET_PROVIDERS}
SUPPORTED_NEWS_PROVIDERS = {"finnhub"}
SUPPORTED_TRANSCRIPT_PROVIDERS = {"local_text", "text", "file"}
SUPPORTED_ESTIMATE_REVISION_PROVIDERS = {"csv", "frozen_csv", "local_csv"}


class JsonFetcher(Protocol):
    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any: ...

    def get_text(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str: ...


@dataclass(frozen=True)
class UrllibJsonFetcher:
    timeout_seconds: float = 20

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        raw, _charset = self._read_url(url, params=params, headers=headers)
        return json.loads(raw.decode("utf-8"))

    def get_text(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        raw, charset = self._read_url(url, params=params, headers=headers)
        return raw.decode(charset or "utf-8", errors="replace")

    def _read_url(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[bytes, str | None]:
        if params:
            clean_params = {key: value for key, value in params.items() if value is not None}
            url = f"{url}?{urlencode(clean_params)}"
        request = Request(url, headers=headers or {})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            raw = response.read()
            encoding = response.headers.get("Content-Encoding", "").lower()
            if encoding == "gzip":
                raw = gzip.decompress(raw)
            elif encoding == "deflate":
                raw = zlib.decompress(raw)
            return raw, response.headers.get_content_charset()


@dataclass
class FinnhubClient:
    token: str
    fetcher: JsonFetcher
    base_url: str = "https://finnhub.io/api/v1"

    def company_news(self, ticker: str, date_from: str, date_to: str) -> list[dict[str, Any]]:
        data = self.fetcher.get_json(
            f"{self.base_url}/company-news",
            params={
                "symbol": ticker.upper(),
                "from": date_from,
                "to": date_to,
                "token": self.token,
            },
        )
        if not isinstance(data, list):
            raise RealDataError(f"Finnhub company-news returned an unexpected payload for {ticker}")
        return data

    def stock_candles(
        self,
        ticker: str,
        *,
        resolution: str,
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        data = self.fetcher.get_json(
            f"{self.base_url}/stock/candle",
            params={
                "symbol": ticker.upper(),
                "resolution": resolution,
                "from": int(start.timestamp()),
                "to": int(end.timestamp()),
                "token": self.token,
            },
        )
        if not isinstance(data, dict):
            raise RealDataError(f"Finnhub stock/candle returned an unexpected payload for {ticker}")
        return data


@dataclass
class SecClient:
    user_agent: str
    fetcher: JsonFetcher

    def ticker_cik_map(self) -> dict[str, str]:
        data = self.fetcher.get_json(
            "https://www.sec.gov/files/company_tickers.json",
            headers=self._headers("www.sec.gov"),
        )
        if not isinstance(data, dict):
            raise RealDataError("SEC company_tickers returned an unexpected payload")

        cik_map: dict[str, str] = {}
        for company in data.values():
            if not isinstance(company, dict):
                continue
            ticker = str(company.get("ticker", "")).upper()
            cik = str(company.get("cik_str", "")).zfill(10)
            if ticker and cik:
                cik_map[ticker] = cik
        return cik_map

    def recent_filings(
        self,
        ticker: str,
        *,
        forms: list[str],
        count: int,
        cik: str | None = None,
    ) -> list[dict[str, Any]]:
        cik = cik or self.ticker_cik_map().get(ticker.upper())
        if not cik:
            raise RealDataError(f"Could not resolve SEC CIK for {ticker}")

        data = self.fetcher.get_json(
            f"https://data.sec.gov/submissions/CIK{cik}.json",
            headers=self._headers("data.sec.gov"),
        )
        if not isinstance(data, dict):
            raise RealDataError(f"SEC submissions returned an unexpected payload for {ticker}")

        recent = data.get("filings", {}).get("recent", {})
        if not isinstance(recent, dict):
            return []

        normalized_forms = {form.upper() for form in forms}
        filings: list[dict[str, Any]] = []
        form_values = recent.get("form", [])
        for idx, form in enumerate(form_values):
            if str(form).upper() not in normalized_forms:
                continue
            accession_formatted = _array_value(recent, "accessionNumber", idx)
            document = _array_value(recent, "primaryDocument", idx)
            filing_date = _array_value(recent, "filingDate", idx)
            accepted_at = _array_value(recent, "acceptanceDateTime", idx)
            accession = accession_formatted.replace("-", "")
            url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{cik.lstrip('0')}/{accession}/{document}"
            )
            filings.append(
                {
                    "cik": cik,
                    "company_name": data.get("name", ticker.upper()),
                    "form": str(form).upper(),
                    "filing_date": filing_date,
                    "accepted_at": accepted_at,
                    "accession": accession,
                    "accession_formatted": accession_formatted,
                    "document": document,
                    "url": url,
                }
            )
            if len(filings) >= count:
                break
        return filings

    def company_facts(self, ticker: str, *, cik: str | None = None) -> dict[str, Any]:
        cik = cik or self.ticker_cik_map().get(ticker.upper())
        if not cik:
            raise RealDataError(f"Could not resolve SEC CIK for {ticker}")
        data = self.fetcher.get_json(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
            headers=self._headers("data.sec.gov"),
        )
        if not isinstance(data, dict):
            raise RealDataError(f"SEC companyfacts returned an unexpected payload for {ticker}")
        data["_resolved_cik"] = cik
        return data

    def filing_document_text(self, url: str) -> str:
        return self.fetcher.get_text(url, headers=self._headers("www.sec.gov"))

    def _headers(self, host: str) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": host,
        }


def load_real_case_config(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def preview_real_case_config(config: dict[str, Any]) -> dict[str, Any]:
    metadata = config.get("case_metadata", {}) if isinstance(config, dict) else {}
    enabled_sections = [section for section in REAL_OPTIONAL_SECTIONS if config.get(section)]
    provider_requirements = []
    if _needs_finnhub_token(config):
        provider_requirements.append("FINNHUB_API_KEY")
    if config.get("sec_filings") or config.get("sec_facts"):
        provider_requirements.append("SEC_USER_AGENT")
    return {
        "case_id": metadata.get("case_id"),
        "ticker": str(metadata.get("ticker", "")).upper() or None,
        "event_timestamp": metadata.get("event_timestamp"),
        "enabled_sections": enabled_sections,
        "evidence_sections": [section for section in REAL_EVIDENCE_SECTIONS if config.get(section)],
        "provider_requirements": provider_requirements,
    }


def validate_real_case_config(
    config: dict[str, Any],
    *,
    base_path: str | Path | None = None,
    check_files: bool = False,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(config, dict):
        return ["real case config must be an object"]

    base_path = Path(base_path or ".")
    metadata = config.get("case_metadata")
    replay_timestamp: datetime | None = None
    if not isinstance(metadata, dict):
        errors.append("case_metadata is required")
    else:
        for field in ["case_id", "ticker", "company_name", "event_timestamp"]:
            if not metadata.get(field):
                errors.append(f"case_metadata.{field} is required")
        if metadata.get("data_provenance_mode") not in {None, "real-curated"}:
            errors.append("case_metadata.data_provenance_mode must be real-curated for real-data configs")
        if metadata.get("event_timestamp"):
            replay_timestamp = _validate_timestamp(
                metadata["event_timestamp"],
                errors,
                "case_metadata.event_timestamp",
            )

    if "event" in config and not isinstance(config["event"], dict):
        errors.append("event must be an object when present")
    if "narratives" in config and not isinstance(config["narratives"], list):
        errors.append("narratives must be a list when present")

    if config.get("market_data"):
        _validate_market_data_config(
            config["market_data"],
            replay_timestamp,
            errors,
            base_path=base_path,
            check_files=check_files,
        )
    if config.get("news"):
        _validate_news_config(config["news"], errors)
    if config.get("sec_filings"):
        _validate_sec_filings_config(config["sec_filings"], errors)
    if config.get("sec_facts"):
        _validate_sec_facts_config(config["sec_facts"], errors)
    if config.get("manual_sources") is not None:
        _validate_manual_sources_config(config["manual_sources"], errors)
    if config.get("transcripts"):
        _validate_transcripts_config(
            config["transcripts"],
            errors,
            base_path=base_path,
            check_files=check_files,
        )
    if config.get("estimate_revisions"):
        _validate_estimate_revisions_config(
            config["estimate_revisions"],
            errors,
            base_path=base_path,
            check_files=check_files,
        )

    if not any(config.get(section) for section in REAL_EVIDENCE_SECTIONS):
        errors.append(
            "Real source pack must include manual_sources, news, sec_filings, "
            "sec_facts, transcripts, or estimate_revisions"
        )
    return errors


def build_real_source_pack(
    config: dict[str, Any],
    *,
    finnhub_token: str | None = None,
    sec_user_agent: str | None = None,
    fetcher: JsonFetcher | None = None,
    retrieved_at: str | datetime | None = None,
    base_path: str | Path | None = None,
) -> dict[str, Any]:
    fetcher = fetcher or UrllibJsonFetcher()
    base_path = Path(base_path or ".")
    config_errors = validate_real_case_config(config, base_path=base_path, check_files=True)
    if config_errors:
        raise RealDataError("; ".join(config_errors))
    now = _iso_timestamp(_coerce_datetime(retrieved_at) if retrieved_at else datetime.now(timezone.utc))
    metadata = _build_case_metadata(config)
    replay_timestamp = _coerce_datetime(metadata["event_timestamp"])

    payload: dict[str, Any] = {
        "case_metadata": metadata,
        "sources": [],
        "narratives": list(config.get("narratives", [])),
    }
    if isinstance(config.get("event"), dict):
        payload["event"] = dict(config["event"])

    if config.get("market_data"):
        market_provider = str(config["market_data"].get("provider", "finnhub")).lower()
        if market_provider in {"csv", "frozen_csv", "local_csv"}:
            payload["market_snapshot"] = _build_market_snapshot_from_csv(
                metadata["ticker"],
                replay_timestamp,
                config["market_data"],
                base_path=base_path,
            )
        else:
            if not finnhub_token:
                raise RealDataError("FINNHUB_API_KEY is required when market_data is enabled")
            finnhub = FinnhubClient(finnhub_token, fetcher)
            payload["market_snapshot"] = _build_market_snapshot(
                finnhub,
                metadata["ticker"],
                replay_timestamp,
                config["market_data"],
            )

    existing_ids: set[str] = set()
    manual_sources = config.get("manual_sources", [])
    if not isinstance(manual_sources, list):
        raise RealDataError("manual_sources must be a list when present")
    for source in manual_sources:
        payload["sources"].append(
            _normalize_manual_source(source, replay_timestamp, retrieved_at=now, existing_ids=existing_ids)
        )

    if config.get("news"):
        if not finnhub_token:
            raise RealDataError("FINNHUB_API_KEY is required when news is enabled")
        finnhub = FinnhubClient(finnhub_token, fetcher)
        payload["sources"].extend(
            _build_finnhub_news_sources(
                finnhub,
                metadata["ticker"],
                replay_timestamp,
                config["news"],
                retrieved_at=now,
                existing_ids=existing_ids,
            )
        )

    if config.get("sec_filings"):
        if not sec_user_agent:
            raise RealDataError("SEC_USER_AGENT is required when sec_filings is enabled")
        sec = SecClient(sec_user_agent, fetcher)
        payload["sources"].extend(
            _build_sec_filing_sources(
                sec,
                metadata["ticker"],
                replay_timestamp,
                config["sec_filings"],
                retrieved_at=now,
                existing_ids=existing_ids,
            )
        )

    if config.get("sec_facts"):
        if not sec_user_agent:
            raise RealDataError("SEC_USER_AGENT is required when sec_facts is enabled")
        sec = SecClient(sec_user_agent, fetcher)
        payload["sources"].extend(
            _build_sec_fact_sources(
                sec,
                metadata["ticker"],
                replay_timestamp,
                config["sec_facts"],
                retrieved_at=now,
                existing_ids=existing_ids,
            )
        )

    if config.get("transcripts"):
        payload["sources"].extend(
            _build_transcript_sources(
                config["transcripts"],
                replay_timestamp,
                retrieved_at=now,
                existing_ids=existing_ids,
                base_path=base_path,
            )
        )

    if config.get("estimate_revisions"):
        payload["sources"].extend(
            _build_estimate_revision_sources(
                config["estimate_revisions"],
                replay_timestamp,
                retrieved_at=now,
                existing_ids=existing_ids,
                base_path=base_path,
            )
        )

    if not payload["sources"]:
        raise RealDataError(
            "Real source pack must include manual_sources, news, sec_filings, "
            "sec_facts, transcripts, or estimate_revisions"
        )
    return payload


def _validate_market_data_config(
    config: Any,
    replay_timestamp: datetime | None,
    errors: list[str],
    *,
    base_path: Path,
    check_files: bool,
) -> None:
    if not isinstance(config, dict):
        errors.append("market_data must be an object")
        return
    provider = str(config.get("provider", "finnhub")).lower()
    if provider not in SUPPORTED_MARKET_PROVIDERS:
        errors.append(f"Unsupported market_data provider: {provider}")
        return
    if provider in LOCAL_MARKET_PROVIDERS:
        _validate_local_path(
            config.get("path") or config.get("csv_path"),
            "market_data.path",
            errors,
            base_path=base_path,
            check_files=check_files,
        )
    if "peers" in config and not isinstance(config["peers"], list):
        errors.append("market_data.peers must be a list when present")
    if replay_timestamp and provider == "finnhub":
        resolution = str(config.get("resolution", "D")).upper()
        if (
            resolution in {"D", "W", "M"}
            and replay_timestamp.hour * 60 * 60 + replay_timestamp.minute * 60 + replay_timestamp.second < 16 * 60 * 60
            and not bool(config.get("allow_event_day_daily_close", False))
        ):
            errors.append(
                "Daily Finnhub candles cannot safely represent an intraday replay lock; "
                "use an intraday resolution or set allow_event_day_daily_close for a post-close replay."
            )


def _validate_news_config(config: Any, errors: list[str]) -> None:
    if not isinstance(config, dict):
        errors.append("news must be an object")
        return
    provider = str(config.get("provider", "finnhub")).lower()
    if provider not in SUPPORTED_NEWS_PROVIDERS:
        errors.append(f"Unsupported news provider: {provider}")


def _validate_sec_filings_config(config: Any, errors: list[str]) -> None:
    if not isinstance(config, dict):
        errors.append("sec_filings must be an object")
        return
    if "forms" in config and not isinstance(config["forms"], list):
        errors.append("sec_filings.forms must be a list when present")
    if "count" in config and (not isinstance(config["count"], int) or isinstance(config["count"], bool) or config["count"] < 1):
        errors.append("sec_filings.count must be a positive integer when present")


def _validate_sec_facts_config(config: Any, errors: list[str]) -> None:
    if not isinstance(config, dict):
        errors.append("sec_facts must be an object")
        return
    concepts = config.get("concepts")
    if not isinstance(concepts, list) or not concepts:
        errors.append("sec_facts.concepts must be a non-empty list")
        return
    for idx, concept in enumerate(concepts):
        if not isinstance(concept, dict):
            errors.append(f"sec_facts.concepts[{idx}] must be an object")
            continue
        if not concept.get("tag"):
            errors.append(f"sec_facts.concepts[{idx}].tag is required")


def _validate_manual_sources_config(config: Any, errors: list[str]) -> None:
    if not isinstance(config, list):
        errors.append("manual_sources must be a list when present")
        return
    seen_ids: set[str] = set()
    for idx, item in enumerate(config):
        if not isinstance(item, dict):
            errors.append(f"manual_sources[{idx}] must be an object")
            continue
        source_id = str(item.get("source_id") or "").strip()
        if source_id:
            if source_id in seen_ids:
                errors.append(f"Duplicate source_id in real-data config: {source_id}")
            seen_ids.add(source_id)
        if not item.get("claim_extracted"):
            errors.append(f"manual_sources[{idx}].claim_extracted is required")
        if item.get("published_at"):
            _validate_timestamp(item["published_at"], errors, f"manual_sources[{idx}].published_at")
        else:
            errors.append(f"manual_sources[{idx}].published_at is required")


def _validate_transcripts_config(
    config: Any,
    errors: list[str],
    *,
    base_path: Path,
    check_files: bool,
) -> None:
    try:
        items = _configured_items(config, field_name="transcripts")
    except RealDataError as exc:
        errors.append(str(exc))
        return
    seen_ids: set[str] = set()
    for idx, item in enumerate(items):
        provider = str(item.get("provider", "local_text")).lower()
        if provider not in SUPPORTED_TRANSCRIPT_PROVIDERS:
            errors.append(f"Unsupported transcript provider: {provider}")
        _validate_local_path(
            item.get("path") or item.get("text_path"),
            f"transcripts[{idx}].path",
            errors,
            base_path=base_path,
            check_files=check_files,
        )
        if item.get("source_id"):
            source_id = str(item["source_id"])
            if source_id in seen_ids:
                errors.append(f"Duplicate source_id in real-data config: {source_id}")
            seen_ids.add(source_id)
        if item.get("published_at"):
            _validate_timestamp(item["published_at"], errors, f"transcripts[{idx}].published_at")
        else:
            errors.append(f"transcripts[{idx}].published_at is required")


def _validate_estimate_revisions_config(
    config: Any,
    errors: list[str],
    *,
    base_path: Path,
    check_files: bool,
) -> None:
    if not isinstance(config, dict):
        errors.append("estimate_revisions must be an object")
        return
    provider = str(config.get("provider", "csv")).lower()
    if provider not in SUPPORTED_ESTIMATE_REVISION_PROVIDERS:
        errors.append(f"Unsupported estimate_revisions provider: {provider}")
        return
    _validate_local_path(
        config.get("path") or config.get("csv_path"),
        "estimate_revisions.path",
        errors,
        base_path=base_path,
        check_files=check_files,
    )


def _validate_timestamp(value: Any, errors: list[str], field: str) -> datetime | None:
    try:
        return _coerce_datetime(value)
    except RealDataError as exc:
        errors.append(f"{field}: {exc}")
        return None


def _validate_local_path(
    value: Any,
    field: str,
    errors: list[str],
    *,
    base_path: Path,
    check_files: bool,
) -> None:
    if not value:
        errors.append(f"{field} is required")
        return
    path = Path(str(value))
    if not path.is_absolute():
        path = base_path / path
    if check_files and not path.exists():
        errors.append(f"{field} does not exist: {path}")


def _needs_finnhub_token(config: dict[str, Any]) -> bool:
    market_data = config.get("market_data")
    if isinstance(market_data, dict):
        market_provider = str(market_data.get("provider", "finnhub")).lower()
        if market_provider not in LOCAL_MARKET_PROVIDERS:
            return True
    return bool(config.get("news"))


def _build_case_metadata(config: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(config.get("case_metadata", {}))
    if not metadata:
        raise RealDataError("case_metadata is required")
    for field in ["case_id", "ticker", "company_name", "event_timestamp"]:
        if not metadata.get(field):
            raise RealDataError(f"case_metadata.{field} is required")
    metadata["ticker"] = str(metadata["ticker"]).upper()
    metadata["data_provenance_mode"] = "real-curated"
    return metadata


def _build_market_snapshot(
    finnhub: FinnhubClient,
    ticker: str,
    replay_timestamp: datetime,
    config: dict[str, Any],
) -> dict[str, Any]:
    resolution = str(config.get("resolution", "D")).upper()
    lookback_days = int(config.get("lookback_days", 40 if resolution in {"D", "W", "M"} else 5))
    start = (
        _coerce_market_bound(config.get("from"), replay_timestamp)
        if config.get("from")
        else replay_timestamp - timedelta(days=lookback_days)
    )
    end = _coerce_market_bound(config.get("to"), replay_timestamp) if config.get("to") else replay_timestamp

    peers = [str(item).upper() for item in config.get("peers", [])]
    sector_symbol = str(config.get("sector_symbol", "")).upper()
    allow_daily_close = bool(config.get("allow_event_day_daily_close", False))

    event_bar = _build_bar_from_candles(
        ticker,
        finnhub.stock_candles(ticker, resolution=resolution, start=start, end=end),
        replay_timestamp,
        resolution=resolution,
        allow_daily_close=allow_daily_close,
    )
    snapshot: dict[str, Any] = {"event_bar": event_bar, "peer_bars": []}

    for peer in peers:
        snapshot["peer_bars"].append(
            _build_bar_from_candles(
                peer,
                finnhub.stock_candles(peer, resolution=resolution, start=start, end=end),
                replay_timestamp,
                resolution=resolution,
                allow_daily_close=allow_daily_close,
            )
        )

    if sector_symbol:
        snapshot["sector_bar"] = _build_bar_from_candles(
            sector_symbol,
            finnhub.stock_candles(sector_symbol, resolution=resolution, start=start, end=end),
            replay_timestamp,
            resolution=resolution,
            allow_daily_close=allow_daily_close,
        )
    return snapshot


def _build_market_snapshot_from_csv(
    ticker: str,
    replay_timestamp: datetime,
    config: dict[str, Any],
    *,
    base_path: Path,
) -> dict[str, Any]:
    raw_path = config.get("path") or config.get("csv_path")
    if not raw_path:
        raise RealDataError("market_data.path is required for csv market data")
    csv_path = Path(str(raw_path))
    if not csv_path.is_absolute():
        csv_path = base_path / csv_path
    rows = _load_price_csv(csv_path, config, replay_timestamp)

    peers = [str(item).upper() for item in config.get("peers", [])]
    sector_symbol = str(config.get("sector_symbol", "")).upper()
    snapshot: dict[str, Any] = {
        "event_bar": _build_bar_from_csv_rows(ticker, rows, replay_timestamp, config),
        "peer_bars": [
            _build_bar_from_csv_rows(peer, rows, replay_timestamp, config)
            for peer in peers
        ],
    }
    if sector_symbol:
        snapshot["sector_bar"] = _build_bar_from_csv_rows(
            sector_symbol,
            rows,
            replay_timestamp,
            config,
        )
    return snapshot


def _load_price_csv(
    path: Path,
    config: dict[str, Any],
    replay_timestamp: datetime,
) -> list[dict[str, Any]]:
    if not path.exists():
        raise RealDataError(f"CSV market data file does not exist: {path}")
    date_column = str(config.get("date_column", "date"))
    ticker_column = str(config.get("ticker_column", "ticker"))
    open_column = str(config.get("open_column", "open"))
    close_column = str(config.get("close_column", "close"))
    volume_column = str(config.get("volume_column", "volume"))
    average_volume_column = str(config.get("average_volume_column", "average_volume"))

    rows = []
    with path.open(newline="") as handle:
        reader = DictReader(handle)
        for row in reader:
            normalized = {str(key).strip().lower(): value for key, value in row.items() if key}
            try:
                raw_timestamp = str(_csv_value(normalized, date_column))
                rows.append(
                    {
                        "ticker": str(_csv_value(normalized, ticker_column)).upper(),
                        "as_of": _parse_csv_market_timestamp(
                            raw_timestamp,
                            config,
                            replay_timestamp,
                        ),
                        "is_daily_close": _is_date_only_timestamp(raw_timestamp),
                        "open": float(_csv_value(normalized, open_column)),
                        "close": float(_csv_value(normalized, close_column)),
                        "volume": _optional_float(_csv_value(normalized, volume_column, default=None)),
                        "average_volume": _optional_float(
                            _csv_value(normalized, average_volume_column, default=None)
                        ),
                    }
                )
            except (TypeError, ValueError) as exc:
                raise RealDataError(f"Invalid market CSV row in {path}: {row}") from exc
    if not rows:
        raise RealDataError(f"CSV market data file has no rows: {path}")
    return sorted(rows, key=lambda row: (row["ticker"], row["as_of"]))


def _build_bar_from_csv_rows(
    symbol: str,
    rows: list[dict[str, Any]],
    replay_timestamp: datetime,
    config: dict[str, Any],
) -> dict[str, Any]:
    normalized_symbol = symbol.upper()
    allow_daily_close = bool(config.get("allow_event_day_daily_close", False))
    window = int(config.get("average_volume_window", 20))
    symbol_rows = [row for row in rows if row["ticker"] == normalized_symbol]
    eligible = [row for row in symbol_rows if row["as_of"] <= replay_timestamp]
    if not eligible:
        raise RealDataError(f"No CSV market rows were available for {normalized_symbol} before the replay lock")
    selected = eligible[-1]
    if (
        selected["as_of"].astimezone(replay_timestamp.tzinfo).date()
        == replay_timestamp.astimezone(replay_timestamp.tzinfo).date()
        and _local_seconds(replay_timestamp) < 16 * 60 * 60
        and selected.get("is_daily_close")
        and not allow_daily_close
    ):
        raise RealDataError(
            "Daily CSV bars cannot safely represent an intraday replay lock; "
            "use intraday timestamps or set allow_event_day_daily_close for a post-close replay."
        )

    prior = [row for row in symbol_rows if row["as_of"] < selected["as_of"] and row["volume"]]
    prior_volumes = [float(row["volume"]) for row in prior[-window:]]
    result = {
        "symbol": normalized_symbol,
        "open": selected["open"],
        "close": selected["close"],
        "as_of": _iso_timestamp(selected["as_of"]),
    }
    if selected["volume"] is not None:
        result["volume"] = selected["volume"]
    if selected["average_volume"] is not None:
        result["average_volume"] = selected["average_volume"]
    elif prior_volumes:
        result["average_volume"] = round(sum(prior_volumes) / len(prior_volumes), 6)
    return result


def _build_bar_from_candles(
    symbol: str,
    payload: dict[str, Any],
    replay_timestamp: datetime,
    *,
    resolution: str,
    allow_daily_close: bool,
) -> dict[str, Any]:
    if payload.get("s") != "ok":
        raise RealDataError(f"Finnhub candle payload for {symbol} was not ok")

    candles = _normalize_candles(symbol, payload)
    eligible = [candle for candle in candles if candle["as_of"] <= replay_timestamp]
    if not eligible:
        raise RealDataError(f"No {symbol} candles were available before the replay lock")

    if resolution in {"D", "W", "M"}:
        latest = eligible[-1]
        if (
            resolution == "D"
            and latest["as_of"].astimezone(timezone.utc).date()
            == replay_timestamp.astimezone(timezone.utc).date()
            and _local_seconds(replay_timestamp) < 16 * 60 * 60
            and not allow_daily_close
        ):
            raise RealDataError(
                "Daily Finnhub candles cannot safely represent an intraday replay lock; "
                "use an intraday resolution or set allow_event_day_daily_close for a post-close replay."
            )
        previous_volumes = [float(candle["volume"]) for candle in eligible[:-1] if candle["volume"]]
        result = {
            "symbol": symbol.upper(),
            "open": latest["open"],
            "close": latest["close"],
            "as_of": _iso_timestamp(latest["as_of"]),
        }
        if latest["volume"] is not None:
            result["volume"] = latest["volume"]
        if previous_volumes:
            result["average_volume"] = round(sum(previous_volumes) / len(previous_volumes), 6)
        return result

    local_date = replay_timestamp.astimezone(replay_timestamp.tzinfo).date()
    same_day = [
        candle
        for candle in eligible
        if candle["as_of"].astimezone(replay_timestamp.tzinfo).date() == local_date
    ]
    selected = same_day or [eligible[-1]]
    total_volume = sum(float(candle["volume"] or 0) for candle in selected)
    result = {
        "symbol": symbol.upper(),
        "open": selected[0]["open"],
        "close": selected[-1]["close"],
        "as_of": _iso_timestamp(selected[-1]["as_of"]),
    }
    if total_volume:
        result["volume"] = round(total_volume, 6)
    return result


def _normalize_candles(symbol: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    timestamps = payload.get("t", [])
    opens = payload.get("o", [])
    closes = payload.get("c", [])
    volumes = payload.get("v", [])
    if not timestamps or len(timestamps) != len(opens) or len(timestamps) != len(closes):
        raise RealDataError(f"Finnhub candle payload for {symbol} is incomplete")

    candles = []
    for idx, epoch in enumerate(timestamps):
        candles.append(
            {
                "as_of": datetime.fromtimestamp(int(epoch), timezone.utc),
                "open": float(opens[idx]),
                "close": float(closes[idx]),
                "volume": float(volumes[idx]) if idx < len(volumes) and volumes[idx] is not None else None,
            }
        )
    return sorted(candles, key=lambda item: item["as_of"])


def _build_finnhub_news_sources(
    finnhub: FinnhubClient,
    ticker: str,
    replay_timestamp: datetime,
    config: dict[str, Any],
    *,
    retrieved_at: str,
    existing_ids: set[str],
) -> list[dict[str, Any]]:
    date_from = str(config.get("from") or replay_timestamp.date().isoformat())
    date_to = str(config.get("to") or replay_timestamp.date().isoformat())
    max_articles = int(config.get("max_articles", 10))
    supported = [str(item) for item in config.get("default_supported_narrative_ids", [])]
    contradicted = [str(item) for item in config.get("default_contradicted_narrative_ids", [])]

    articles = finnhub.company_news(ticker, date_from, date_to)
    sources = []
    for article in articles[:max_articles]:
        if not isinstance(article, dict):
            continue
        published_at = _datetime_from_epoch(article.get("datetime"))
        headline = str(article.get("headline") or f"{ticker.upper()} company news")
        summary = str(article.get("summary") or "").strip()
        text = headline if not summary else f"{headline}\n\n{summary}"
        article_id = str(article.get("id") or len(sources) + 1)
        url = str(article.get("url") or f"finnhub://company-news/{ticker.upper()}/{article_id}")
        source = _source_record(
            source_id=_next_source_id("NEWS", existing_ids),
            source_type="news_article",
            publisher=str(article.get("source") or "Finnhub company news"),
            title=headline,
            url=url,
            published_at=published_at,
            retrieved_at=retrieved_at,
            replay_timestamp=replay_timestamp,
            claim_extracted=_truncate_claim(text),
            document_text=text,
            supported_narrative_ids=supported,
            contradicted_narrative_ids=contradicted,
            independence_cluster_id=f"news-{_slug(article.get('source') or 'finnhub')}",
            originality_score=0.65,
            support_strength=0.45,
            evidence_quality=0.55,
            independence=0.7,
            incentive_conflict=0.15,
        )
        sources.append(source)
    return sources


def _build_sec_filing_sources(
    sec: SecClient,
    ticker: str,
    replay_timestamp: datetime,
    config: dict[str, Any],
    *,
    retrieved_at: str,
    existing_ids: set[str],
) -> list[dict[str, Any]]:
    forms = [str(item).upper() for item in config.get("forms", ["8-K", "10-Q", "10-K"])]
    count = int(config.get("count", 3))
    cik = str(config["cik"]).zfill(10) if config.get("cik") else None
    supported = [str(item) for item in config.get("default_supported_narrative_ids", [])]
    contradicted = [str(item) for item in config.get("default_contradicted_narrative_ids", [])]
    include_document_text = bool(config.get("include_document_text", False))
    document_text_max_chars = int(config.get("document_text_max_chars", 12000))
    filings = sec.recent_filings(ticker, forms=forms, count=count, cik=cik)

    sources = []
    for filing in filings:
        published_at = _parse_sec_accepted_at(filing.get("accepted_at"), filing.get("filing_date"))
        title = f"{ticker.upper()} {filing['form']} filed {filing['filing_date']}"
        claim = f"{filing.get('company_name', ticker.upper())} filed {filing['form']} on {filing['filing_date']}."
        document_text = claim
        if include_document_text:
            document_text = _extract_sec_document_text(
                sec.filing_document_text(str(filing["url"])),
                max_chars=document_text_max_chars,
            )
            claim = f"{claim} Filing document text was retrieved from SEC EDGAR."
        sources.append(
            _source_record(
                source_id=_next_source_id("SEC", existing_ids),
                source_type="sec_filing",
                publisher="SEC EDGAR",
                title=title,
                url=str(filing["url"]),
                published_at=published_at,
                retrieved_at=retrieved_at,
                replay_timestamp=replay_timestamp,
                claim_extracted=claim,
                document_text=document_text,
                supported_narrative_ids=supported,
                contradicted_narrative_ids=contradicted,
                independence_cluster_id="sec-edgar",
                originality_score=0.9,
                support_strength=0.6,
                evidence_quality=0.9,
                independence=0.95,
                incentive_conflict=0.05,
            )
        )
    return sources


def _build_sec_fact_sources(
    sec: SecClient,
    ticker: str,
    replay_timestamp: datetime,
    config: dict[str, Any],
    *,
    retrieved_at: str,
    existing_ids: set[str],
) -> list[dict[str, Any]]:
    cik = str(config["cik"]).zfill(10) if config.get("cik") else None
    facts_payload = sec.company_facts(ticker, cik=cik)
    resolved_cik = str(facts_payload.get("_resolved_cik") or cik or "").zfill(10)
    company_name = str(facts_payload.get("entityName") or ticker.upper())
    concepts = config.get("concepts", [])
    if not isinstance(concepts, list) or not concepts:
        raise RealDataError("sec_facts.concepts must be a non-empty list")
    supported = [str(item) for item in config.get("default_supported_narrative_ids", [])]
    contradicted = [str(item) for item in config.get("default_contradicted_narrative_ids", [])]
    max_facts = int(config.get("max_facts_per_concept", 1))

    sources = []
    for concept_config in concepts:
        if not isinstance(concept_config, dict):
            raise RealDataError("sec_facts.concepts entries must be objects")
        taxonomy = str(concept_config.get("taxonomy", "us-gaap"))
        tag = str(concept_config.get("tag", ""))
        unit = str(concept_config.get("unit", "USD"))
        label = str(concept_config.get("label") or tag)
        fact_rows = (
            facts_payload.get("facts", {})
            .get(taxonomy, {})
            .get(tag, {})
            .get("units", {})
            .get(unit, [])
        )
        if not isinstance(fact_rows, list):
            continue
        selected_rows = _select_sec_fact_rows(fact_rows, max_count=max_facts)
        for fact in selected_rows:
            filed_date = str(fact.get("filed") or fact.get("end") or "")
            if not filed_date:
                continue
            published_at = _coerce_datetime(f"{filed_date}T00:00:00Z")
            accession = str(fact.get("accn") or "")
            source_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{resolved_cik.lstrip('0')}/{accession.replace('-', '')}/"
                if accession and resolved_cik.strip("0")
                else f"https://data.sec.gov/api/xbrl/companyfacts/CIK{resolved_cik}.json"
            )
            claim = _sec_fact_claim(company_name, label, fact, unit)
            sources.append(
                _source_record(
                    source_id=_next_source_id("XBRL", existing_ids),
                    source_type="sec_xbrl_fact",
                    publisher="SEC EDGAR XBRL",
                    title=f"{ticker.upper()} {label} XBRL fact filed {filed_date}",
                    url=source_url,
                    published_at=published_at,
                    retrieved_at=retrieved_at,
                    replay_timestamp=replay_timestamp,
                    claim_extracted=claim,
                    document_text=claim,
                    supported_narrative_ids=supported,
                    contradicted_narrative_ids=contradicted,
                    independence_cluster_id="sec-xbrl",
                    originality_score=0.9,
                    support_strength=0.55,
                    evidence_quality=0.9,
                    independence=0.95,
                    incentive_conflict=0.05,
                )
            )
    return sources


def _build_transcript_sources(
    config: Any,
    replay_timestamp: datetime,
    *,
    retrieved_at: str,
    existing_ids: set[str],
    base_path: Path,
) -> list[dict[str, Any]]:
    items = _configured_items(config, field_name="transcripts")
    sources = []
    for item in items:
        provider = str(item.get("provider", "local_text")).lower()
        if provider not in {"local_text", "text", "file"}:
            raise RealDataError(f"Unsupported transcript provider: {provider}")
        raw_path = item.get("path") or item.get("text_path")
        if not raw_path:
            raise RealDataError("transcript item path is required for local_text provider")
        path = Path(str(raw_path))
        if not path.is_absolute():
            path = base_path / path
        if not path.exists():
            raise RealDataError(f"Transcript file does not exist: {path}")
        document_text = _normalize_plaintext_document(path.read_text())
        published_at = _coerce_datetime(item.get("published_at"))
        claim = str(item.get("claim_extracted") or _truncate_claim(document_text)).strip()
        sources.append(
            _source_record(
                source_id=_source_id_or_next(item.get("source_id"), "TRN", existing_ids),
                source_type=str(item.get("source_type") or "earnings_transcript"),
                publisher=str(item.get("publisher") or "Curated transcript"),
                title=str(item.get("title") or f"Transcript published {_iso_timestamp(published_at)}"),
                url=str(item.get("url") or f"file://{path.name}"),
                published_at=published_at,
                retrieved_at=retrieved_at,
                replay_timestamp=replay_timestamp,
                claim_extracted=claim,
                document_text=document_text,
                supported_narrative_ids=_ids_from_config(item, "supported_narrative_ids"),
                contradicted_narrative_ids=_ids_from_config(item, "contradicted_narrative_ids"),
                independence_cluster_id=str(item.get("independence_cluster_id") or "company-transcript"),
                originality_score=float(item.get("originality_score", 0.8)),
                support_strength=float(item.get("support_strength", 0.65)),
                evidence_quality=float(item.get("evidence_quality", 0.78)),
                independence=float(item.get("independence", 0.7)),
                incentive_conflict=float(item.get("incentive_conflict", 0.2)),
            )
        )
    return sources


def _build_estimate_revision_sources(
    config: dict[str, Any],
    replay_timestamp: datetime,
    *,
    retrieved_at: str,
    existing_ids: set[str],
    base_path: Path,
) -> list[dict[str, Any]]:
    if not isinstance(config, dict):
        raise RealDataError("estimate_revisions must be an object")
    provider = str(config.get("provider", "csv")).lower()
    if provider not in {"csv", "frozen_csv", "local_csv"}:
        raise RealDataError(f"Unsupported estimate_revisions provider: {provider}")
    raw_path = config.get("path") or config.get("csv_path")
    if not raw_path:
        raise RealDataError("estimate_revisions.path is required for csv provider")
    csv_path = Path(str(raw_path))
    if not csv_path.is_absolute():
        csv_path = base_path / csv_path
    rows = _load_estimate_revision_rows(csv_path, config)
    max_rows = int(config.get("max_rows", len(rows)))
    supported = _ids_from_config(config, "default_supported_narrative_ids")
    contradicted = _ids_from_config(config, "default_contradicted_narrative_ids")

    sources = []
    for row in rows[:max_rows]:
        published_at = _coerce_datetime(row["published_at"])
        metric = row["metric"]
        period = row["period"]
        old_value = row.get("old_estimate")
        new_value = row.get("new_estimate")
        unit = row.get("unit") or ""
        publisher = row.get("publisher") or config.get("publisher") or "Curated estimate revision"
        title = row.get("title") or f"{metric} estimate revision for {period}"
        url = row.get("url") or config.get("url") or f"estimate-revision://{_slug(title)}"
        if old_value not in {None, ""}:
            change_text = f"changed from {old_value} to {new_value}"
        else:
            change_text = f"was updated to {new_value}"
        claim = (
            f"{publisher} {change_text} for {metric} in {period}"
            f"{(' ' + unit) if unit else ''}; published {_iso_timestamp(published_at)}."
        )
        sources.append(
            _source_record(
                source_id=_source_id_or_next(row.get("source_id"), "EST", existing_ids),
                source_type="estimate_revision",
                publisher=str(publisher),
                title=str(title),
                url=str(url),
                published_at=published_at,
                retrieved_at=retrieved_at,
                replay_timestamp=replay_timestamp,
                claim_extracted=claim,
                document_text=json.dumps(row, sort_keys=True),
                supported_narrative_ids=_ids_from_row(row, "supported_narrative_ids", fallback=supported),
                contradicted_narrative_ids=_ids_from_row(row, "contradicted_narrative_ids", fallback=contradicted),
                independence_cluster_id=str(row.get("independence_cluster_id") or "estimate-revisions"),
                originality_score=0.7,
                support_strength=0.58,
                evidence_quality=0.72,
                independence=0.65,
                incentive_conflict=0.2,
            )
        )
    return sources


def _configured_items(config: Any, *, field_name: str) -> list[dict[str, Any]]:
    if isinstance(config, list):
        items = config
        defaults: dict[str, Any] = {}
    elif isinstance(config, dict):
        if "items" in config:
            raw_items = config["items"]
            if not isinstance(raw_items, list):
                raise RealDataError(f"{field_name}.items must be a list")
            defaults = {
                key: value
                for key, value in config.items()
                if key not in {"items", "path", "text_path"}
            }
            items = [{**defaults, **item} for item in raw_items if isinstance(item, dict)]
            if len(items) != len(raw_items):
                raise RealDataError(f"{field_name}.items entries must be objects")
        else:
            items = [config]
    else:
        raise RealDataError(f"{field_name} must be an object or list")
    if not items:
        raise RealDataError(f"{field_name} must contain at least one item")
    return items


def _load_estimate_revision_rows(path: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    if not path.exists():
        raise RealDataError(f"Estimate revision CSV file does not exist: {path}")
    columns = {
        "published_at": str(config.get("published_at_column", "published_at")),
        "metric": str(config.get("metric_column", "metric")),
        "period": str(config.get("period_column", "period")),
        "old_estimate": str(config.get("old_estimate_column", "old_estimate")),
        "new_estimate": str(config.get("new_estimate_column", "new_estimate")),
        "unit": str(config.get("unit_column", "unit")),
        "publisher": str(config.get("publisher_column", "publisher")),
        "title": str(config.get("title_column", "title")),
        "url": str(config.get("url_column", "url")),
        "source_id": str(config.get("source_id_column", "source_id")),
        "supported_narrative_ids": str(config.get("supported_narrative_ids_column", "supported_narrative_ids")),
        "contradicted_narrative_ids": str(config.get("contradicted_narrative_ids_column", "contradicted_narrative_ids")),
    }

    rows = []
    with path.open(newline="") as handle:
        reader = DictReader(handle)
        for raw_row in reader:
            normalized = {str(key).strip().lower(): value for key, value in raw_row.items() if key}
            row = {field: _csv_value(normalized, column, default="") for field, column in columns.items()}
            if not row["published_at"] or not row["metric"] or not row["period"] or not row["new_estimate"]:
                raise RealDataError(f"Invalid estimate revision CSV row in {path}: {raw_row}")
            _coerce_datetime(str(row["published_at"]))
            rows.append(row)
    if not rows:
        raise RealDataError(f"Estimate revision CSV file has no rows: {path}")
    return sorted(rows, key=lambda row: _coerce_datetime(str(row["published_at"])))


def _normalize_plaintext_document(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        raise RealDataError("Document text is empty")
    return normalized


def _ids_from_config(config: dict[str, Any], field: str) -> list[str]:
    return _split_ids(config.get(field) or config.get(f"default_{field}") or [])


def _ids_from_row(row: dict[str, Any], field: str, *, fallback: list[str]) -> list[str]:
    value = row.get(field)
    if value in {None, ""}:
        return list(fallback)
    return _split_ids(value)


def _split_ids(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [
        item.strip()
        for item in str(value).split("|")
        if item.strip()
    ]


def _normalize_manual_source(
    source: dict[str, Any],
    replay_timestamp: datetime,
    *,
    retrieved_at: str,
    existing_ids: set[str],
) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise RealDataError("manual_sources entries must be objects")
    data = dict(source)
    if data.get("source_id"):
        data["source_id"] = str(data["source_id"])
        if data["source_id"] in existing_ids:
            raise RealDataError(f"Duplicate source_id in real-data config: {data['source_id']}")
        existing_ids.add(data["source_id"])
    else:
        data["source_id"] = _next_source_id("SRC", existing_ids)

    if not data.get("claim_extracted"):
        raise RealDataError(f"manual source {data['source_id']} needs claim_extracted")
    published_at = _coerce_datetime(data.get("published_at"))
    data.setdefault("retrieved_at", retrieved_at)
    data.setdefault("availability_status", _availability_status(published_at, replay_timestamp))
    data.setdefault("supported_narrative_ids", [])
    data.setdefault("contradicted_narrative_ids", [])
    data.setdefault("originality_score", 0.7)
    data.setdefault("support_strength", 0.5)
    data.setdefault("evidence_quality", 0.65)
    data.setdefault("independence", 0.7)
    data.setdefault("incentive_conflict", 0.15)
    data.setdefault("independence_cluster_id", f"manual-{_slug(data.get('publisher', 'source'))}")
    data.setdefault("source_type", "curated_source")
    data.setdefault("publisher", "Curated source")
    data.setdefault("title", str(data["claim_extracted"])[:90])
    data.setdefault("url", f"manual://{data['source_id']}")
    if not data.get("content_hash"):
        hash_text = str(data.get("document_text") or data.get("raw_text") or data["claim_extracted"])
        data["content_hash"] = source_content_hash(hash_text)
    return sanitize_source_record(data)


def _source_record(
    *,
    source_id: str,
    source_type: str,
    publisher: str,
    title: str,
    url: str,
    published_at: datetime,
    retrieved_at: str,
    replay_timestamp: datetime,
    claim_extracted: str,
    document_text: str,
    supported_narrative_ids: list[str],
    contradicted_narrative_ids: list[str],
    independence_cluster_id: str,
    originality_score: float,
    support_strength: float,
    evidence_quality: float,
    independence: float,
    incentive_conflict: float,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_type": source_type,
        "publisher": publisher,
        "title": title,
        "url": url,
        "published_at": _iso_timestamp(published_at),
        "retrieved_at": retrieved_at,
        "content_hash": source_content_hash(document_text),
        "availability_status": _availability_status(published_at, replay_timestamp),
        "originality_score": originality_score,
        "independence_cluster_id": independence_cluster_id,
        "claim_extracted": claim_extracted,
        "document_text": document_text,
        "supported_narrative_ids": supported_narrative_ids,
        "contradicted_narrative_ids": contradicted_narrative_ids,
        "support_strength": support_strength,
        "evidence_quality": evidence_quality,
        "independence": independence,
        "incentive_conflict": incentive_conflict,
    }


def _next_source_id(prefix: str, existing_ids: set[str]) -> str:
    idx = 1
    while True:
        source_id = f"{prefix}-{idx:03d}"
        if source_id not in existing_ids:
            existing_ids.add(source_id)
            return source_id
        idx += 1


def _source_id_or_next(value: Any, prefix: str, existing_ids: set[str]) -> str:
    if not value:
        return _next_source_id(prefix, existing_ids)
    source_id = str(value)
    if source_id in existing_ids:
        raise RealDataError(f"Duplicate source_id in real-data config: {source_id}")
    existing_ids.add(source_id)
    return source_id


def _availability_status(published_at: datetime, replay_timestamp: datetime) -> str:
    return "allowed" if published_at <= replay_timestamp else "blocked_future"


def _coerce_datetime(value: str | datetime | None) -> datetime:
    if value is None:
        raise RealDataError("timestamp value is required")
    if isinstance(value, datetime):
        return value
    try:
        parsed = parse_datetime(value)
    except ValueError as exc:
        raise RealDataError(f"Invalid timestamp: {value}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RealDataError(f"Timestamp must include a timezone offset: {value}")
    return parsed


def _coerce_market_bound(value: str | datetime, replay_timestamp: datetime) -> datetime:
    if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return datetime.fromisoformat(value).replace(tzinfo=replay_timestamp.tzinfo or timezone.utc)
    return _coerce_datetime(value)


def _parse_csv_market_timestamp(
    value: str,
    config: dict[str, Any],
    replay_timestamp: datetime,
) -> datetime:
    cleaned = value.strip()
    if not cleaned:
        raise RealDataError("CSV market row has an empty date")
    if _is_date_only_timestamp(cleaned):
        tz = replay_timestamp.tzinfo or timezone.utc
        close_time = str(config.get("daily_close_time", "16:00:00"))
        hour, minute, second = _parse_time_parts(close_time)
        return datetime.combine(
            datetime.fromisoformat(cleaned).date(),
            datetime_time(hour, minute, second, tzinfo=tz),
        )
    return _coerce_datetime(cleaned)


def _is_date_only_timestamp(value: str) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", value.strip()))


def _parse_time_parts(value: str) -> tuple[int, int, int]:
    parts = value.split(":")
    if len(parts) not in {2, 3}:
        raise RealDataError(f"Invalid daily_close_time: {value}")
    hour = int(parts[0])
    minute = int(parts[1])
    second = int(parts[2]) if len(parts) == 3 else 0
    return hour, minute, second


def _csv_value(row: dict[str, Any], column: str, *, default: Any = "") -> Any:
    return row.get(column.lower(), default)


def _optional_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    return float(value)


def _datetime_from_epoch(value: Any) -> datetime:
    try:
        return datetime.fromtimestamp(int(value), timezone.utc)
    except (TypeError, ValueError) as exc:
        raise RealDataError(f"Invalid epoch timestamp from provider: {value}") from exc


def _parse_sec_accepted_at(accepted_at: Any, filing_date: Any) -> datetime:
    if accepted_at:
        value = str(accepted_at)
        if value.endswith("Z"):
            return _coerce_datetime(value)
        if re.match(r"^\d{4}-\d{2}-\d{2}T", value):
            return _coerce_datetime(f"{value.rstrip('Z')}+00:00")
    if filing_date:
        return _coerce_datetime(f"{filing_date}T00:00:00Z")
    raise RealDataError("SEC filing is missing filing_date")


def _select_sec_fact_rows(fact_rows: list[dict[str, Any]], *, max_count: int) -> list[dict[str, Any]]:
    rows = [row for row in fact_rows if isinstance(row, dict) and row.get("val") is not None]
    rows.sort(key=lambda row: (str(row.get("filed") or ""), str(row.get("end") or "")), reverse=True)
    return rows[:max_count]


def _sec_fact_claim(company_name: str, label: str, fact: dict[str, Any], unit: str) -> str:
    value = fact.get("val")
    form = fact.get("form", "filing")
    filed = fact.get("filed", "unknown date")
    period = fact.get("end") or fact.get("fy") or "unknown period"
    accession = fact.get("accn", "unknown accession")
    return (
        f"{company_name} reported {label} of {value} {unit} for period {period}; "
        f"source form {form}, filed {filed}, accession {accession}."
    )


def _extract_sec_document_text(raw_text: str, *, max_chars: int) -> str:
    cleaned = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", raw_text)
    cleaned = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", cleaned)
    cleaned = re.sub(r"(?is)<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        raise RealDataError("SEC filing document text was empty after HTML normalization")
    if max_chars > 0 and len(cleaned) > max_chars:
        return cleaned[:max_chars].rstrip()
    return cleaned


def _array_value(data: dict[str, Any], key: str, idx: int) -> str:
    values = data.get(key, [])
    if idx >= len(values):
        return ""
    return str(values[idx] or "")


def _iso_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _local_seconds(value: datetime) -> int:
    return value.hour * 60 * 60 + value.minute * 60 + value.second


def _truncate_claim(text: str, limit: int = 280) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}..."


def _slug(value: Any) -> str:
    text = str(value or "source").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "source"
