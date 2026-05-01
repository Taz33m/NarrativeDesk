import unittest

from narrativedesk.models import ScoreInputs
from narrativedesk.scoring import calculate_narrative_score


class ScoringTests(unittest.TestCase):
    def test_high_quality_narrative_scores_higher_than_crowded_unsupported_one(self):
        strong = ScoreInputs(
            evidence_strength=0.9,
            mechanism_specificity=0.9,
            source_independence=0.8,
            cross_sectional_fit=0.8,
            contradiction_resistance=0.7,
            timestamp_advantage=0.9,
            forward_observable_quality=0.9,
            crowding_risk=0.1,
            unsupported_claim_penalty=0.0,
        )
        weak = ScoreInputs(
            evidence_strength=0.6,
            mechanism_specificity=0.5,
            source_independence=0.3,
            cross_sectional_fit=0.4,
            contradiction_resistance=0.2,
            timestamp_advantage=0.8,
            forward_observable_quality=0.4,
            crowding_risk=0.9,
            unsupported_claim_penalty=0.6,
        )

        strong_score, _ = calculate_narrative_score(strong)
        weak_score, _ = calculate_narrative_score(weak)

        self.assertGreater(strong_score, weak_score)
        self.assertGreaterEqual(strong_score, 0.0)
        self.assertLessEqual(strong_score, 1.0)

    def test_penalties_reduce_score(self):
        base = ScoreInputs(
            evidence_strength=0.8,
            mechanism_specificity=0.8,
            source_independence=0.8,
            cross_sectional_fit=0.8,
            contradiction_resistance=0.8,
            timestamp_advantage=0.8,
            forward_observable_quality=0.8,
            crowding_risk=0.0,
            unsupported_claim_penalty=0.0,
        )
        penalized = ScoreInputs(
            evidence_strength=0.8,
            mechanism_specificity=0.8,
            source_independence=0.8,
            cross_sectional_fit=0.8,
            contradiction_resistance=0.8,
            timestamp_advantage=0.8,
            forward_observable_quality=0.8,
            crowding_risk=1.0,
            unsupported_claim_penalty=1.0,
        )

        base_score, _ = calculate_narrative_score(base)
        penalized_score, _ = calculate_narrative_score(penalized)

        self.assertLess(penalized_score, base_score)


if __name__ == "__main__":
    unittest.main()
