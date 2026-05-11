from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from narrativedesk.models import Narrative
from narrativedesk.replay import ReplayAudit

UNSUPPORTED_PENALTY_THRESHOLD = 0.10


@dataclass(frozen=True)
class ModelComparison:
    system_id: str
    selected_narrative_id: str | None
    selected_rank: int | None
    validated: bool | None
    selection_reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvaluationSummary:
    validated_narrative_ids: list[str]
    missing_validated_narrative_ids: list[str]
    validated_rank: int | None
    narrative_recall_at_3: bool | None
    top_ranked_validated: bool | None
    unsupported_claim_penalty_avg: float
    unsupported_claim_penalty_max: float
    high_unsupported_claim_count: int
    blocked_future_source_count: int
    allowed_source_count: int
    model_comparisons: list[ModelComparison]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validated_narrative_ids(validation: dict[str, Any] | None) -> list[str]:
    if not validation:
        return []
    rows = validation.get("rows")
    if not isinstance(rows, list):
        return []
    return sorted(
        {
            str(row["narrative_id"])
            for row in rows
            if isinstance(row, dict)
            and row.get("label") == "validated"
            and row.get("narrative_id")
        }
    )


def evaluate_replay(
    narratives: list[Narrative],
    audit: ReplayAudit,
    validation: dict[str, Any] | None = None,
) -> EvaluationSummary:
    rank_by_id = {
        narrative.narrative_id: narrative.rank
        for narrative in narratives
        if narrative.rank is not None
    }
    validated_ids = validated_narrative_ids(validation)
    missing_validated_ids = [
        narrative_id for narrative_id in validated_ids if narrative_id not in rank_by_id
    ]
    validated_ranks = sorted(
        rank_by_id[narrative_id]
        for narrative_id in validated_ids
        if narrative_id in rank_by_id
    )
    validated_rank = validated_ranks[0] if validated_ranks else None

    penalties = [
        narrative.scoring_inputs.unsupported_claim_penalty
        for narrative in narratives
    ]
    penalty_avg = round(sum(penalties) / len(penalties), 6) if penalties else 0.0
    penalty_max = round(max(penalties), 6) if penalties else 0.0
    validated_set = set(validated_ids)

    top_ranked = min(
        narratives,
        key=lambda narrative: narrative.rank if narrative.rank is not None else 999_999,
        default=None,
    )
    headline_baseline = max(
        narratives,
        key=lambda narrative: (
            narrative.scoring_inputs.crowding_risk,
            narrative.scoring_inputs.evidence_strength,
            narrative.narrative_id,
        ),
        default=None,
    )
    model_comparisons = [
        _comparison_row(
            "headline_baseline",
            headline_baseline,
            validated_set if validated_ids else None,
            "Selects the most crowded allowed narrative as a proxy for surface consensus.",
        ),
        _comparison_row(
            "evidence_only",
            _select_evidence_only(narratives),
            validated_set if validated_ids else None,
            "Ablation that selects the strongest evidence score without mechanism or contradiction terms.",
        ),
        _comparison_row(
            "no_contradiction_penalty",
            _select_no_contradiction_penalty(narratives),
            validated_set if validated_ids else None,
            "Ablation that reranks without contradiction resistance or unsupported-claim penalty.",
        ),
        _comparison_row(
            "quality_weighted",
            _select_quality_weighted(narratives),
            validated_set if validated_ids else None,
            "Ablation that selects the strongest evidence score weighted by allowed source quality.",
        ),
        _comparison_row(
            "narrativedesk_tournament",
            top_ranked,
            validated_set if validated_ids else None,
            "Selects the highest deterministic narrative score after replay filtering.",
        ),
    ]

    return EvaluationSummary(
        validated_narrative_ids=validated_ids,
        missing_validated_narrative_ids=missing_validated_ids,
        validated_rank=validated_rank,
        narrative_recall_at_3=(
            validated_rank <= 3
            if validated_rank is not None
            else False if validated_ids else None
        ),
        top_ranked_validated=(
            validated_rank == 1
            if validated_rank is not None
            else False if validated_ids else None
        ),
        unsupported_claim_penalty_avg=penalty_avg,
        unsupported_claim_penalty_max=penalty_max,
        high_unsupported_claim_count=sum(
            1 for penalty in penalties if penalty >= UNSUPPORTED_PENALTY_THRESHOLD
        ),
        blocked_future_source_count=len(audit.blocked_source_ids),
        allowed_source_count=len(audit.allowed_source_ids),
        model_comparisons=model_comparisons,
    )


def _select_evidence_only(narratives: list[Narrative]) -> Narrative | None:
    return max(
        narratives,
        key=lambda narrative: (
            narrative.scoring_inputs.evidence_strength,
            _allowed_source_quality(narrative),
            narrative.scoring_inputs.source_independence,
            narrative.narrative_id,
        ),
        default=None,
    )


def _select_no_contradiction_penalty(narratives: list[Narrative]) -> Narrative | None:
    return max(
        narratives,
        key=lambda narrative: (
            _no_contradiction_ablation_score(narrative),
            narrative.scoring_inputs.evidence_strength,
            narrative.narrative_id,
        ),
        default=None,
    )


def _select_quality_weighted(narratives: list[Narrative]) -> Narrative | None:
    return max(
        narratives,
        key=lambda narrative: (
            narrative.scoring_inputs.evidence_strength * _allowed_source_quality(narrative),
            narrative.scoring_inputs.source_independence,
            narrative.narrative_id,
        ),
        default=None,
    )


def _allowed_source_quality(narrative: Narrative) -> float:
    evidence = narrative.all_evidence()
    if not evidence:
        return 0.0
    return sum(item.evidence_quality for item in evidence) / len(evidence)


def _no_contradiction_ablation_score(narrative: Narrative) -> float:
    inputs = narrative.scoring_inputs
    return (
        inputs.evidence_strength * 0.25
        + inputs.mechanism_specificity * 0.20
        + inputs.source_independence * 0.15
        + inputs.cross_sectional_fit * 0.15
        + inputs.timestamp_advantage * 0.10
        + inputs.forward_observable_quality * 0.10
        - inputs.crowding_risk * 0.05
    )


def _comparison_row(
    system_id: str,
    narrative: Narrative | None,
    validated_set: set[str] | None,
    selection_reason: str,
) -> ModelComparison:
    if narrative is None:
        return ModelComparison(
            system_id=system_id,
            selected_narrative_id=None,
            selected_rank=None,
            validated=None,
            selection_reason=selection_reason,
        )
    return ModelComparison(
        system_id=system_id,
        selected_narrative_id=narrative.narrative_id,
        selected_rank=narrative.rank,
        validated=None if validated_set is None else narrative.narrative_id in validated_set,
        selection_reason=selection_reason,
    )


def summarize_case_evaluations(case_evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [
        item
        for item in case_evaluations
        if item["evaluation"]["narrative_recall_at_3"] is not None
    ]
    if not evaluated:
        recall_rate = None
        top_ranked_rate = None
    else:
        recall_rate = sum(
            1 for item in evaluated if item["evaluation"]["narrative_recall_at_3"]
        ) / len(evaluated)
        top_ranked_rate = sum(
            1 for item in evaluated if item["evaluation"]["top_ranked_validated"]
        ) / len(evaluated)

    unsupported_avgs = [
        item["evaluation"]["unsupported_claim_penalty_avg"]
        for item in case_evaluations
    ]
    model_rates: dict[str, float | None] = {}
    model_ids = sorted(
        {
            row["system_id"]
            for item in case_evaluations
            for row in item["evaluation"].get("model_comparisons", [])
        }
    )
    for model_id in model_ids:
        rows = [
            row
            for item in case_evaluations
            for row in item["evaluation"].get("model_comparisons", [])
            if row["system_id"] == model_id and row["validated"] is not None
        ]
        model_rates[f"{model_id}_validated_rate"] = (
            sum(1 for row in rows if row["validated"]) / len(rows)
            if rows
            else None
        )

    citation_rows = [
        item["citation_qa"]
        for item in case_evaluations
        if isinstance(item.get("citation_qa"), dict)
    ]
    reliability_rows = [
        item["source_reliability"]["overall"]
        for item in case_evaluations
        if isinstance(item.get("source_reliability"), dict)
        and isinstance(item["source_reliability"].get("overall"), dict)
    ]
    clustering_rows = [
        item["source_clustering"]
        for item in case_evaluations
        if isinstance(item.get("source_clustering"), dict)
    ]

    return {
        "case_count": len(case_evaluations),
        "evaluated_case_count": len(evaluated),
        "narrative_recall_at_3_rate": recall_rate,
        "top_ranked_validated_rate": top_ranked_rate,
        **model_rates,
        "blocked_future_source_count": sum(
            item["evaluation"]["blocked_future_source_count"]
            for item in case_evaluations
        ),
        "unsupported_claim_penalty_avg": (
            round(sum(unsupported_avgs) / len(unsupported_avgs), 6)
            if unsupported_avgs
            else 0.0
        ),
        "citation_qa_pass_rate": _bool_rate(citation_rows, "citation_qa_pass"),
        "provenance_ready_rate": _bool_rate(citation_rows, "provenance_ready"),
        "replay_filter_pass_rate": _bool_rate(citation_rows, "replay_filter_pass"),
        "support_coverage_pass_rate": _bool_rate(citation_rows, "support_coverage_pass"),
        "missing_url_count": sum(int(row.get("missing_url_count", 0)) for row in citation_rows),
        "missing_content_hash_count": sum(
            int(row.get("missing_content_hash_count", 0)) for row in citation_rows
        ),
        "low_quality_evidence_count": sum(
            int(row.get("low_quality_evidence_count", 0)) for row in citation_rows
        ),
        "source_reliability_avg_evidence_quality": _weighted_average(
            reliability_rows,
            "average_evidence_quality",
            "allowed_source_count",
        ),
        "source_reliability_avg_independence": _weighted_average(
            reliability_rows,
            "average_independence",
            "allowed_source_count",
        ),
        "source_reliability_avg_originality": _weighted_average(
            reliability_rows,
            "average_originality_score",
            "allowed_source_count",
        ),
        "source_cluster_count": sum(int(row.get("cluster_count", 0)) for row in clustering_rows),
        "source_duplicate_cluster_count": sum(
            int(row.get("duplicate_cluster_count", 0)) for row in clustering_rows
        ),
        "source_clustering_avg_derived_originality": _weighted_average(
            clustering_rows,
            "average_derived_originality_score",
            "allowed_source_count",
        ),
    }


def _bool_rate(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [row.get(key) for row in rows if row.get(key) is not None]
    if not values:
        return None
    return sum(1 for value in values if bool(value)) / len(values)


def _weighted_average(
    rows: list[dict[str, Any]],
    value_key: str,
    weight_key: str,
) -> float | None:
    weighted_sum = 0.0
    total_weight = 0
    for row in rows:
        value = row.get(value_key)
        weight = int(row.get(weight_key, 0))
        if value is None or weight <= 0:
            continue
        weighted_sum += float(value) * weight
        total_weight += weight
    if total_weight == 0:
        return None
    return round(weighted_sum / total_weight, 6)
