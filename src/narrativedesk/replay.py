from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Iterable

from narrativedesk.models import EvidenceItem, Narrative, parse_datetime


@dataclass(frozen=True)
class ReplayAudit:
    replay_timestamp: datetime
    allowed_source_ids: list[str]
    blocked_source_ids: list[str]
    removed_evidence_by_narrative: dict[str, list[str]]
    blocked_evidence: list[dict[str, object]]

    @property
    def has_blocked_sources(self) -> bool:
        return bool(self.blocked_source_ids)

    def to_dict(self) -> dict[str, object]:
        return {
            "replay_timestamp": self.replay_timestamp.isoformat(),
            "allowed_source_ids": self.allowed_source_ids,
            "blocked_source_ids": self.blocked_source_ids,
            "removed_evidence_by_narrative": self.removed_evidence_by_narrative,
            "blocked_evidence": self.blocked_evidence,
        }


def is_source_allowed(evidence: EvidenceItem, replay_timestamp: datetime | str) -> bool:
    timestamp = parse_datetime(replay_timestamp)
    if not _has_timezone_offset(timestamp):
        raise ValueError("replay timestamp must include a timezone offset")
    if not _has_timezone_offset(evidence.published_at):
        raise ValueError(f"{evidence.source_id} published_at must include a timezone offset")
    if evidence.availability_status == "blocked_future":
        return False
    return evidence.published_at <= timestamp


def _has_timezone_offset(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def blocked_evidence_audit_record(
    narrative_id: str,
    evidence: EvidenceItem,
) -> dict[str, object]:
    blocked_reason = (
        "marked_blocked_future"
        if evidence.availability_status == "blocked_future"
        else "published_after_replay_timestamp"
    )
    return {
        "source_id": evidence.source_id,
        "narrative_id": narrative_id,
        "published_at": evidence.published_at.isoformat(),
        "source_type": evidence.source_type,
        "relation": evidence.relation,
        "availability_status": "blocked_future",
        "replay_status": "blocked_future",
        "blocked_reason": blocked_reason,
    }


def split_evidence_for_replay(
    evidence_items: Iterable[EvidenceItem],
    replay_timestamp: datetime | str,
) -> tuple[list[EvidenceItem], list[EvidenceItem]]:
    allowed: list[EvidenceItem] = []
    blocked: list[EvidenceItem] = []
    for evidence in evidence_items:
        if is_source_allowed(evidence, replay_timestamp):
            allowed.append(evidence)
        else:
            blocked.append(evidence)
    return allowed, blocked


def filter_narrative_for_replay(
    narrative: Narrative,
    replay_timestamp: datetime | str,
) -> tuple[Narrative, list[EvidenceItem]]:
    allowed_support, blocked_support = split_evidence_for_replay(
        narrative.supporting_evidence,
        replay_timestamp,
    )
    allowed_contradict, blocked_contradict = split_evidence_for_replay(
        narrative.contradicting_evidence,
        replay_timestamp,
    )
    filtered = replace(
        narrative,
        supporting_evidence=allowed_support,
        contradicting_evidence=allowed_contradict,
    )
    return filtered, [*blocked_support, *blocked_contradict]


def filter_narratives_for_replay(
    narratives: Iterable[Narrative],
    replay_timestamp: datetime | str,
) -> tuple[list[Narrative], ReplayAudit]:
    timestamp = parse_datetime(replay_timestamp)
    filtered_narratives: list[Narrative] = []
    allowed_ids: set[str] = set()
    blocked_ids: set[str] = set()
    removed: dict[str, list[str]] = {}
    blocked_evidence: list[dict[str, object]] = []

    for narrative in narratives:
        filtered, blocked = filter_narrative_for_replay(narrative, timestamp)
        filtered_narratives.append(filtered)
        for evidence in filtered.all_evidence():
            allowed_ids.add(evidence.source_id)
        if blocked:
            removed[narrative.narrative_id] = [item.source_id for item in blocked]
            for evidence in blocked:
                blocked_ids.add(evidence.source_id)
                blocked_evidence.append(blocked_evidence_audit_record(narrative.narrative_id, evidence))

    audit = ReplayAudit(
        replay_timestamp=timestamp,
        allowed_source_ids=sorted(allowed_ids),
        blocked_source_ids=sorted(blocked_ids),
        removed_evidence_by_narrative=removed,
        blocked_evidence=sorted(
            blocked_evidence,
            key=lambda item: (str(item["narrative_id"]), str(item["source_id"])),
        ),
    )
    return filtered_narratives, audit
