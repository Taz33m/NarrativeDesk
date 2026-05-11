from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import median
from typing import Any

from narrativedesk.models import parse_datetime


@dataclass(frozen=True)
class MarketBar:
    symbol: str
    open: float
    close: float
    volume: float | None = None
    average_volume: float | None = None
    timestamp: datetime | None = None
    as_of: datetime | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MarketBar:
        return cls(
            symbol=data["symbol"],
            open=float(data["open"]),
            close=float(data["close"]),
            volume=float(data["volume"]) if data.get("volume") is not None else None,
            average_volume=(
                float(data["average_volume"]) if data.get("average_volume") is not None else None
            ),
            timestamp=parse_datetime(data["timestamp"]) if data.get("timestamp") else None,
            as_of=parse_datetime(data["as_of"]) if data.get("as_of") else None,
        )

    def simple_return(self) -> float:
        if self.open == 0:
            raise ValueError(f"{self.symbol} open price cannot be zero")
        return round((self.close / self.open) - 1, 6)

    def volume_ratio(self) -> float | None:
        if self.volume is None or self.average_volume is None:
            return None
        if self.average_volume == 0:
            raise ValueError(f"{self.symbol} average_volume cannot be zero")
        return round(self.volume / self.average_volume, 6)


def _bar_replay_timestamps(bar: MarketBar) -> tuple[datetime, ...]:
    return tuple(item for item in (bar.timestamp, bar.as_of) if item is not None)


def _has_timezone_offset(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _validate_bar_replay_lock(
    bar: MarketBar,
    replay_timestamp: datetime | str | None,
) -> None:
    if replay_timestamp is None:
        return

    lock = parse_datetime(replay_timestamp)
    if not _has_timezone_offset(lock):
        raise ValueError("market replay timestamp must include a timezone offset")
    bar_timestamps = _bar_replay_timestamps(bar)
    if not bar_timestamps:
        raise ValueError(f"{bar.symbol} market bar must include timestamp or as_of")
    for bar_timestamp in bar_timestamps:
        if not _has_timezone_offset(bar_timestamp):
            raise ValueError(f"{bar.symbol} market bar timestamp must include a timezone offset")
        if bar_timestamp > lock:
            raise ValueError(
                f"{bar.symbol} market bar timestamp {bar_timestamp.isoformat()} "
                f"is after replay timestamp {lock.isoformat()}"
            )


def compute_event_market_metrics(
    snapshot: dict[str, Any],
    replay_timestamp: datetime | str | None = None,
) -> dict[str, float | None]:
    event_bar = MarketBar.from_dict(snapshot["event_bar"])
    peer_bars = [MarketBar.from_dict(item) for item in snapshot.get("peer_bars", [])]
    sector_bar = (
        MarketBar.from_dict(snapshot["sector_bar"]) if snapshot.get("sector_bar") else None
    )

    for bar in [event_bar, *peer_bars, *([sector_bar] if sector_bar else [])]:
        _validate_bar_replay_lock(bar, replay_timestamp)

    daily_return = event_bar.simple_return()
    peer_median_return = (
        round(median(peer.simple_return() for peer in peer_bars), 6) if peer_bars else None
    )
    sector_etf_return = sector_bar.simple_return() if sector_bar else None
    abnormal_return = (
        round(daily_return - peer_median_return, 6)
        if peer_median_return is not None
        else None
    )

    return {
        "daily_return": daily_return,
        "abnormal_return": abnormal_return,
        "volume_ratio": event_bar.volume_ratio(),
        "sector_etf_return": sector_etf_return,
        "peer_median_return": peer_median_return,
    }
