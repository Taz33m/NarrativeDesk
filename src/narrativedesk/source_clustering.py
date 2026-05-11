from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import re
from statistics import fmean
from typing import Iterable, Literal

from narrativedesk.models import EvidenceItem, Narrative
from narrativedesk.replay import ReplayAudit

ClusterBasis = Literal["independence_cluster_id", "claim_text_fingerprint"]

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a",
    "after",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
}


@dataclass(frozen=True)
class SourceCluster:
    cluster_id: str
    cluster_basis: ClusterBasis
    source_count: int
    source_ids: list[str]
    narrative_ids: list[str]
    publishers: list[str]
    source_types: list[str]
    relation_counts: dict[str, int]
    average_fixture_originality_score: float | None
    derived_originality_score: float
    representative_claim: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SourceClusteringArtifact:
    allowed_source_count: int
    blocked_future_source_count: int
    cluster_count: int
    duplicate_cluster_count: int
    average_cluster_size: float | None
    average_derived_originality_score: float | None
    blocked_future_source_ids: list[str]
    clusters: list[SourceCluster]

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed_source_count": self.allowed_source_count,
            "blocked_future_source_count": self.blocked_future_source_count,
            "cluster_count": self.cluster_count,
            "duplicate_cluster_count": self.duplicate_cluster_count,
            "average_cluster_size": self.average_cluster_size,
            "average_derived_originality_score": self.average_derived_originality_score,
            "blocked_future_source_ids": self.blocked_future_source_ids,
            "clusters": [cluster.to_dict() for cluster in self.clusters],
        }


@dataclass(frozen=True)
class _EvidenceUse:
    narrative_id: str
    evidence: EvidenceItem


def compute_source_clustering(
    ranked_narratives: list[Narrative],
    audit: ReplayAudit,
) -> SourceClusteringArtifact:
    uses = _allowed_evidence_uses(ranked_narratives)
    clusters = [
        _build_cluster(cluster_id, basis, cluster_uses)
        for (cluster_id, basis), cluster_uses in _group_uses(uses).items()
    ]
    clusters = sorted(clusters, key=lambda item: item.cluster_id)
    allowed_source_ids = {use.evidence.source_id for use in uses}
    duplicate_cluster_count = sum(1 for cluster in clusters if cluster.source_count > 1)
    return SourceClusteringArtifact(
        allowed_source_count=len(allowed_source_ids),
        blocked_future_source_count=len(audit.blocked_source_ids),
        cluster_count=len(clusters),
        duplicate_cluster_count=duplicate_cluster_count,
        average_cluster_size=(
            round(len(allowed_source_ids) / len(clusters), 4)
            if clusters
            else None
        ),
        average_derived_originality_score=_weighted_cluster_average(clusters),
        blocked_future_source_ids=sorted(audit.blocked_source_ids),
        clusters=clusters,
    )


def _allowed_evidence_uses(ranked_narratives: list[Narrative]) -> list[_EvidenceUse]:
    uses: list[_EvidenceUse] = []
    for narrative in ranked_narratives:
        for evidence in narrative.all_evidence():
            uses.append(_EvidenceUse(narrative.narrative_id, evidence))
    return uses


def _group_uses(uses: list[_EvidenceUse]) -> dict[tuple[str, ClusterBasis], list[_EvidenceUse]]:
    grouped: dict[tuple[str, ClusterBasis], list[_EvidenceUse]] = {}
    for use in uses:
        cluster_id, basis = _cluster_key(use.evidence)
        grouped.setdefault((cluster_id, basis), []).append(use)
    return grouped


def _cluster_key(evidence: EvidenceItem) -> tuple[str, ClusterBasis]:
    explicit_cluster = evidence.independence_cluster_id.strip()
    if explicit_cluster:
        return explicit_cluster, "independence_cluster_id"
    claim_key = _claim_fingerprint(evidence.claim_extracted or evidence.claim)
    return f"claim-{claim_key}", "claim_text_fingerprint"


def _claim_fingerprint(value: str) -> str:
    tokens = [token for token in TOKEN_RE.findall(value.lower()) if token not in STOPWORDS]
    normalized = " ".join(tokens) or "empty"
    return sha256(normalized.encode("utf-8")).hexdigest()[:12]


def _build_cluster(
    cluster_id: str,
    basis: ClusterBasis,
    uses: list[_EvidenceUse],
) -> SourceCluster:
    sources = _unique_sources(uses)
    publishers = sorted({item.publisher or "unknown" for item in sources})
    source_count = len(sources)
    return SourceCluster(
        cluster_id=cluster_id,
        cluster_basis=basis,
        source_count=source_count,
        source_ids=sorted(item.source_id for item in sources),
        narrative_ids=sorted({use.narrative_id for use in uses}),
        publishers=publishers,
        source_types=sorted({item.source_type or "unknown" for item in sources}),
        relation_counts=_relation_counts(uses),
        average_fixture_originality_score=_average(item.originality_score for item in sources),
        derived_originality_score=_derived_originality_score(
            source_count=source_count,
            independent_publisher_count=len(publishers),
        ),
        representative_claim=_representative_claim(sources),
    )


def _unique_sources(uses: list[_EvidenceUse]) -> list[EvidenceItem]:
    by_source_id: dict[str, EvidenceItem] = {}
    for use in uses:
        by_source_id.setdefault(use.evidence.source_id, use.evidence)
    return sorted(by_source_id.values(), key=lambda item: item.source_id)


def _relation_counts(uses: list[_EvidenceUse]) -> dict[str, int]:
    counts = {"support": 0, "contradict": 0}
    for use in uses:
        counts[use.evidence.relation] = counts.get(use.evidence.relation, 0) + 1
    return counts


def _representative_claim(sources: list[EvidenceItem]) -> str:
    if not sources:
        return ""
    representative = sorted(
        sources,
        key=lambda item: (-item.evidence_quality, item.source_id),
    )[0]
    return representative.claim


def _derived_originality_score(
    *,
    source_count: int,
    independent_publisher_count: int,
) -> float:
    if source_count <= 0:
        return 0.0
    cluster_size_component = 1 / source_count
    publisher_diversity_component = independent_publisher_count / source_count
    return round((cluster_size_component + publisher_diversity_component) / 2, 4)


def _weighted_cluster_average(clusters: list[SourceCluster]) -> float | None:
    total_sources = sum(cluster.source_count for cluster in clusters)
    if total_sources == 0:
        return None
    weighted_sum = sum(
        cluster.derived_originality_score * cluster.source_count
        for cluster in clusters
    )
    return round(weighted_sum / total_sources, 6)


def _average(values: Iterable[float]) -> float | None:
    collected = list(values)
    if not collected:
        return None
    return round(fmean(collected), 4)
