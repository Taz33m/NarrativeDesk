from __future__ import annotations

from dataclasses import asdict, dataclass

from narrativedesk.models import EvidenceItem, Narrative
from narrativedesk.replay import ReplayAudit

LOW_EVIDENCE_QUALITY_THRESHOLD = 0.50


@dataclass(frozen=True)
class CitationQaSummary:
    allowed_source_count: int
    blocked_future_source_count: int
    returned_blocked_source_count: int
    narrative_count: int
    narratives_with_support_count: int
    missing_url_count: int
    missing_content_hash_count: int
    missing_publisher_count: int
    low_quality_evidence_count: int
    replay_filter_pass: bool
    support_coverage_pass: bool
    event_time_integrity_pass: bool
    provenance_ready: bool
    citation_qa_pass: bool

    def to_dict(self) -> dict[str, int | bool]:
        return asdict(self)


def run_citation_qa(narratives: list[Narrative], audit: ReplayAudit) -> CitationQaSummary:
    allowed_evidence = [
        evidence
        for narrative in narratives
        for evidence in narrative.all_evidence()
    ]
    unique_allowed = _unique_sources(allowed_evidence)
    returned_blocked_ids = {
        evidence.source_id
        for evidence in allowed_evidence
        if evidence.source_id in set(audit.blocked_source_ids)
    }
    narratives_with_support = [
        narrative
        for narrative in narratives
        if narrative.supporting_evidence
    ]

    missing_url_count = sum(1 for item in unique_allowed.values() if not item.url)
    missing_content_hash_count = sum(1 for item in unique_allowed.values() if not item.content_hash)
    missing_publisher_count = sum(1 for item in unique_allowed.values() if not item.publisher)
    replay_filter_pass = not returned_blocked_ids
    support_coverage_pass = len(narratives_with_support) == len(narratives)
    provenance_ready = (
        missing_url_count == 0
        and missing_content_hash_count == 0
        and missing_publisher_count == 0
    )
    event_time_integrity_pass = replay_filter_pass and support_coverage_pass

    return CitationQaSummary(
        allowed_source_count=len(unique_allowed),
        blocked_future_source_count=len(audit.blocked_source_ids),
        returned_blocked_source_count=len(returned_blocked_ids),
        narrative_count=len(narratives),
        narratives_with_support_count=len(narratives_with_support),
        missing_url_count=missing_url_count,
        missing_content_hash_count=missing_content_hash_count,
        missing_publisher_count=missing_publisher_count,
        low_quality_evidence_count=sum(
            1 for item in unique_allowed.values() if item.evidence_quality < LOW_EVIDENCE_QUALITY_THRESHOLD
        ),
        replay_filter_pass=replay_filter_pass,
        support_coverage_pass=support_coverage_pass,
        event_time_integrity_pass=event_time_integrity_pass,
        provenance_ready=provenance_ready,
        citation_qa_pass=event_time_integrity_pass and provenance_ready,
    )


def _unique_sources(evidence_items: list[EvidenceItem]) -> dict[str, EvidenceItem]:
    unique: dict[str, EvidenceItem] = {}
    for item in evidence_items:
        unique.setdefault(item.source_id, item)
    return unique
