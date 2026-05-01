from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Iterable

from narrativedesk.models import Narrative, ScoreInputs, clamp01


@dataclass(frozen=True)
class ScoreWeights:
    evidence_strength: float = 0.20
    mechanism_specificity: float = 0.15
    source_independence: float = 0.15
    cross_sectional_fit: float = 0.10
    contradiction_resistance: float = 0.10
    timestamp_advantage: float = 0.10
    forward_observable_quality: float = 0.10
    crowding_risk: float = 0.05
    unsupported_claim_penalty: float = 0.05

    @property
    def positive_total(self) -> float:
        return (
            self.evidence_strength
            + self.mechanism_specificity
            + self.source_independence
            + self.cross_sectional_fit
            + self.contradiction_resistance
            + self.timestamp_advantage
            + self.forward_observable_quality
        )


DEFAULT_SCORE_WEIGHTS = ScoreWeights()


def calculate_narrative_score(
    inputs: ScoreInputs,
    weights: ScoreWeights = DEFAULT_SCORE_WEIGHTS,
) -> tuple[float, dict[str, float]]:
    positive_components = {
        "evidence_strength": inputs.evidence_strength * weights.evidence_strength,
        "mechanism_specificity": inputs.mechanism_specificity * weights.mechanism_specificity,
        "source_independence": inputs.source_independence * weights.source_independence,
        "cross_sectional_fit": inputs.cross_sectional_fit * weights.cross_sectional_fit,
        "contradiction_resistance": inputs.contradiction_resistance
        * weights.contradiction_resistance,
        "timestamp_advantage": inputs.timestamp_advantage * weights.timestamp_advantage,
        "forward_observable_quality": inputs.forward_observable_quality
        * weights.forward_observable_quality,
    }
    penalty_components = {
        "crowding_risk_penalty": inputs.crowding_risk * weights.crowding_risk,
        "unsupported_claim_penalty": inputs.unsupported_claim_penalty
        * weights.unsupported_claim_penalty,
    }

    positive_score = sum(positive_components.values()) / weights.positive_total
    penalty_score = sum(penalty_components.values()) / weights.positive_total
    final_score = clamp01(positive_score - penalty_score)

    score_breakdown = {
        **positive_components,
        **penalty_components,
        "positive_score_normalized": positive_score,
        "penalty_score_normalized": penalty_score,
        "overall_narrative_score": final_score,
    }
    return final_score, score_breakdown


def score_narrative(
    narrative: Narrative,
    weights: ScoreWeights = DEFAULT_SCORE_WEIGHTS,
) -> Narrative:
    score, breakdown = calculate_narrative_score(narrative.scoring_inputs, weights)
    return replace(narrative, scores=breakdown, overall_narrative_score=score)


def rank_narratives(
    narratives: Iterable[Narrative],
    weights: ScoreWeights = DEFAULT_SCORE_WEIGHTS,
) -> list[Narrative]:
    scored = [score_narrative(narrative, weights) for narrative in narratives]
    ranked = sorted(scored, key=lambda item: item.overall_narrative_score, reverse=True)
    return [replace(narrative, rank=index) for index, narrative in enumerate(ranked, start=1)]


def weights_as_dict(weights: ScoreWeights = DEFAULT_SCORE_WEIGHTS) -> dict[str, float]:
    return asdict(weights)
