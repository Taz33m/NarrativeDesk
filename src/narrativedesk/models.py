from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal

Direction = Literal["bullish", "bearish", "neutral", "mixed"]
EvidenceRelation = Literal["support", "contradict"]
ValidationStatus = Literal[
    "pending",
    "partial",
    "validated",
    "invalidated",
    "consensus-leading",
    "validated-but-priced-in",
]


def parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def serialize_datetime(value: datetime) -> str:
    return value.isoformat()


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass(frozen=True)
class Event:
    event_id: str
    ticker: str
    company_name: str
    event_date: str
    event_timestamp: datetime
    event_type: str
    daily_return: float | None = None
    abnormal_return: float | None = None
    volume_ratio: float | None = None
    sector_etf_return: float | None = None
    peer_median_return: float | None = None
    event_summary: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        return cls(
            event_id=data["event_id"],
            ticker=data["ticker"],
            company_name=data.get("company_name", ""),
            event_date=data["event_date"],
            event_timestamp=parse_datetime(data["event_timestamp"]),
            event_type=data.get("event_type", "unknown"),
            daily_return=data.get("daily_return"),
            abnormal_return=data.get("abnormal_return"),
            volume_ratio=data.get("volume_ratio"),
            sector_etf_return=data.get("sector_etf_return"),
            peer_median_return=data.get("peer_median_return"),
            event_summary=data.get("event_summary", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["event_timestamp"] = serialize_datetime(self.event_timestamp)
        return data


@dataclass(frozen=True)
class EvidenceItem:
    source_id: str
    claim: str
    published_at: datetime
    source_type: str
    relation: EvidenceRelation
    publisher: str = ""
    url: str = ""
    support_strength: float = 0.5
    evidence_quality: float = 0.5
    independence: float = 0.5
    incentive_conflict: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any], relation: EvidenceRelation | None = None) -> EvidenceItem:
        return cls(
            source_id=data["source_id"],
            claim=data["claim"],
            published_at=parse_datetime(data["published_at"]),
            source_type=data.get("source_type", "unknown"),
            relation=relation or data.get("relation", "support"),
            publisher=data.get("publisher", ""),
            url=data.get("url", ""),
            support_strength=clamp01(float(data.get("support_strength", 0.5))),
            evidence_quality=clamp01(float(data.get("evidence_quality", 0.5))),
            independence=clamp01(float(data.get("independence", 0.5))),
            incentive_conflict=clamp01(float(data.get("incentive_conflict", 0.0))),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["published_at"] = serialize_datetime(self.published_at)
        return data


@dataclass(frozen=True)
class ScoreInputs:
    evidence_strength: float
    mechanism_specificity: float
    source_independence: float
    cross_sectional_fit: float
    contradiction_resistance: float
    timestamp_advantage: float
    forward_observable_quality: float
    crowding_risk: float
    unsupported_claim_penalty: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScoreInputs:
        return cls(
            evidence_strength=clamp01(float(data.get("evidence_strength", 0.0))),
            mechanism_specificity=clamp01(float(data.get("mechanism_specificity", 0.0))),
            source_independence=clamp01(float(data.get("source_independence", 0.0))),
            cross_sectional_fit=clamp01(float(data.get("cross_sectional_fit", 0.0))),
            contradiction_resistance=clamp01(float(data.get("contradiction_resistance", 0.0))),
            timestamp_advantage=clamp01(float(data.get("timestamp_advantage", 0.0))),
            forward_observable_quality=clamp01(float(data.get("forward_observable_quality", 0.0))),
            crowding_risk=clamp01(float(data.get("crowding_risk", 0.0))),
            unsupported_claim_penalty=clamp01(float(data.get("unsupported_claim_penalty", 0.0))),
        )

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class Narrative:
    narrative_id: str
    event_id: str
    ticker: str
    timestamp_created: datetime
    title: str
    narrative: str
    mechanism: str
    directional_implication: Direction
    time_horizon: str
    expected_observables: list[str]
    scoring_inputs: ScoreInputs
    supporting_evidence: list[EvidenceItem] = field(default_factory=list)
    contradicting_evidence: list[EvidenceItem] = field(default_factory=list)
    validation_status: ValidationStatus = "pending"
    scores: dict[str, float] = field(default_factory=dict)
    overall_narrative_score: float = 0.0
    rank: int | None = None
    confidence: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Narrative:
        supporting = [
            EvidenceItem.from_dict(item, "support") for item in data.get("supporting_evidence", [])
        ]
        contradicting = [
            EvidenceItem.from_dict(item, "contradict")
            for item in data.get("contradicting_evidence", [])
        ]
        return cls(
            narrative_id=data["narrative_id"],
            event_id=data["event_id"],
            ticker=data["ticker"],
            timestamp_created=parse_datetime(data["timestamp_created"]),
            title=data["title"],
            narrative=data["narrative"],
            mechanism=data["mechanism"],
            directional_implication=data.get("directional_implication", "mixed"),
            time_horizon=data.get("time_horizon", "20 trading days"),
            expected_observables=list(data.get("expected_observables", [])),
            scoring_inputs=ScoreInputs.from_dict(data.get("scoring_inputs", {})),
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            validation_status=data.get("validation_status", "pending"),
            scores={key: float(value) for key, value in data.get("scores", {}).items()},
            overall_narrative_score=float(data.get("overall_narrative_score", 0.0)),
            rank=data.get("rank"),
            confidence=data.get("confidence"),
        )

    def all_evidence(self) -> list[EvidenceItem]:
        return [*self.supporting_evidence, *self.contradicting_evidence]

    def to_ledger(self) -> dict[str, Any]:
        return {
            "narrative_id": self.narrative_id,
            "event_id": self.event_id,
            "ticker": self.ticker,
            "timestamp_created": serialize_datetime(self.timestamp_created),
            "title": self.title,
            "narrative": self.narrative,
            "mechanism": self.mechanism,
            "directional_implication": self.directional_implication,
            "time_horizon": self.time_horizon,
            "supporting_evidence": [item.to_dict() for item in self.supporting_evidence],
            "contradicting_evidence": [item.to_dict() for item in self.contradicting_evidence],
            "expected_observables": self.expected_observables,
            "scoring_inputs": self.scoring_inputs.to_dict(),
            "scores": self.scores,
            "overall_narrative_score": self.overall_narrative_score,
            "rank": self.rank,
            "confidence": self.confidence,
            "validation_status": self.validation_status,
        }
