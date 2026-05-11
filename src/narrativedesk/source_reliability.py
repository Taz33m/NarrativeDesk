from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import fmean
from typing import Iterable, Literal

from narrativedesk.models import EvidenceItem, Narrative
from narrativedesk.replay import ReplayAudit

LOW_QUALITY_SOURCE_THRESHOLD = 0.50
ReliabilityGroup = Literal["overall", "publisher", "source_type"]


@dataclass(frozen=True)
class SourceReliabilityBucket:
    group: ReliabilityGroup
    key: str
    allowed_source_count: int
    blocked_future_count: int
    average_evidence_quality: float | None
    average_independence: float | None
    average_originality_score: float | None
    low_quality_source_count: int
    source_ids: list[str]
    blocked_future_source_ids: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SourceReliabilityArtifact:
    overall: SourceReliabilityBucket
    by_publisher: list[SourceReliabilityBucket]
    by_source_type: list[SourceReliabilityBucket]

    def to_dict(self) -> dict[str, object]:
        return {
            "overall": self.overall.to_dict(),
            "by_publisher": [bucket.to_dict() for bucket in self.by_publisher],
            "by_source_type": [bucket.to_dict() for bucket in self.by_source_type],
        }


@dataclass(frozen=True)
class _SourceRecord:
    source_id: str
    publisher: str
    source_type: str
    evidence_quality: float
    independence: float
    originality_score: float
    replay_status: Literal["allowed", "blocked_future"]


def compute_source_reliability(
    ranked_narratives: list[Narrative],
    audit: ReplayAudit,
) -> SourceReliabilityArtifact:
    records = _source_records(ranked_narratives, audit)
    return SourceReliabilityArtifact(
        overall=_bucket("overall", "all_sources", records),
        by_publisher=_grouped_buckets("publisher", records),
        by_source_type=_grouped_buckets("source_type", records),
    )


def _source_records(ranked_narratives: list[Narrative], audit: ReplayAudit) -> list[_SourceRecord]:
    by_source_id: dict[str, _SourceRecord] = {}
    for evidence in _allowed_evidence(ranked_narratives):
        by_source_id.setdefault(evidence.source_id, _record_from_evidence(evidence, "allowed"))

    for item in audit.blocked_evidence:
        source_id = str(item["source_id"])
        by_source_id[source_id] = _record_from_blocked_evidence(item)

    return sorted(by_source_id.values(), key=lambda item: item.source_id)


def _allowed_evidence(ranked_narratives: list[Narrative]) -> Iterable[EvidenceItem]:
    for narrative in ranked_narratives:
        yield from narrative.all_evidence()


def _record_from_evidence(
    evidence: EvidenceItem,
    replay_status: Literal["allowed", "blocked_future"],
) -> _SourceRecord:
    return _SourceRecord(
        source_id=evidence.source_id,
        publisher=evidence.publisher or "unknown",
        source_type=evidence.source_type or "unknown",
        evidence_quality=evidence.evidence_quality,
        independence=evidence.independence,
        originality_score=evidence.originality_score,
        replay_status=replay_status,
    )


def _record_from_blocked_evidence(item: dict[str, object]) -> _SourceRecord:
    return _SourceRecord(
        source_id=str(item["source_id"]),
        publisher=str(item.get("publisher") or "unknown"),
        source_type=str(item.get("source_type") or "unknown"),
        evidence_quality=float(item.get("evidence_quality", 0.5)),
        independence=float(item.get("independence", 0.5)),
        originality_score=float(item.get("originality_score", 0.5)),
        replay_status="blocked_future",
    )


def _grouped_buckets(
    group: Literal["publisher", "source_type"],
    records: list[_SourceRecord],
) -> list[SourceReliabilityBucket]:
    grouped: dict[str, list[_SourceRecord]] = {}
    for record in records:
        key = record.publisher if group == "publisher" else record.source_type
        grouped.setdefault(key, []).append(record)
    return [
        _bucket(group, key, grouped[key])
        for key in sorted(grouped)
    ]


def _bucket(
    group: ReliabilityGroup,
    key: str,
    records: list[_SourceRecord],
) -> SourceReliabilityBucket:
    allowed = [item for item in records if item.replay_status == "allowed"]
    blocked = [item for item in records if item.replay_status == "blocked_future"]
    return SourceReliabilityBucket(
        group=group,
        key=key,
        allowed_source_count=len(allowed),
        blocked_future_count=len(blocked),
        average_evidence_quality=_average(item.evidence_quality for item in allowed),
        average_independence=_average(item.independence for item in allowed),
        average_originality_score=_average(item.originality_score for item in allowed),
        low_quality_source_count=sum(
            1 for item in allowed if item.evidence_quality < LOW_QUALITY_SOURCE_THRESHOLD
        ),
        source_ids=sorted(item.source_id for item in records),
        blocked_future_source_ids=sorted(item.source_id for item in blocked),
    )


def _average(values: Iterable[float]) -> float | None:
    collected = list(values)
    if not collected:
        return None
    return round(fmean(collected), 4)
