from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from narrativedesk.models import clamp01

ValidationWindow = Literal["T+1", "T+5", "T+20", "T+60"]


@dataclass(frozen=True)
class ValidationSignals:
    window: ValidationWindow
    peer_relative_return: float | None = None
    estimate_revision_score: float | None = None
    disclosure_validation_score: float | None = None
    consensus_adoption_score: float | None = None
    tradeability_score: float | None = None

    def composite_score(self) -> float:
        values = [
            self.price_validation_score(),
            self.estimate_revision_score,
            self.disclosure_validation_score,
            self.consensus_adoption_score,
            self.tradeability_score,
        ]
        present = [clamp01(value) for value in values if value is not None]
        if not present:
            return 0.0
        return sum(present) / len(present)

    def price_validation_score(self) -> float | None:
        if self.peer_relative_return is None:
            return None
        # MVP heuristic: stronger absolute peer-relative move implies stronger market validation.
        return clamp01(abs(self.peer_relative_return) / 0.15)


def label_validation(signals: ValidationSignals) -> str:
    score = signals.composite_score()
    if score >= 0.75:
        return "validated"
    if score >= 0.50:
        return "partial"
    if score <= 0.20:
        return "invalidated"
    return "inconclusive"
