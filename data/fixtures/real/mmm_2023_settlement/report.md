# NarrativeDesk Event Report: MMM

> Research support output. Not investment advice.

## Data Note

This report is generated from a real-curated replay bundle. Treat it as research support only; public use requires curator review of source URLs, publication timestamps, raw document hashes, and validation status.

## Event

- Event ID: `EVT-REAL-MMM-2023-08-29`
- Company: 3M Company (`MMM`)
- Timestamp lock: `2023-08-29T16:10:00-04:00`
- Event type: litigation settlement
- Daily return: 1.4%
- Abnormal return: 0.4%
- Volume ratio: n/a
- Sector ETF return: 1.2%
- Peer median return: 1.0%

Real-curated 3M Combat Arms settlement replay with timestamped citations, replay-locked evidence, and held-out validation. Research and education only; not investment advice.

## Replay Audit

- Allowed sources: MMM-AP-001, MMM-CNBC-001, MMM-CNBC-002, MMM-INVEST-001, MMM-IR-001, MMM-MKT-001, MMM-MKT-002, MMM-SEC-001
- Blocked future sources: MMM-FUT-001, MMM-FUT-002
- Removed from `NARR-MMM-001`: MMM-FUT-001, MMM-FUT-002
- Removed from `NARR-MMM-002`: MMM-FUT-001
- Removed from `NARR-MMM-003`: MMM-FUT-001, MMM-FUT-002

## Source Map

| Source | Status | Type | Publisher | Narratives | Relations |
| --- | --- | --- | --- | --- | --- |
| MMM-AP-001 | allowed | news | Associated Press | NARR-MMM-001, NARR-MMM-004 | support |
| MMM-CNBC-001 | allowed | news | CNBC | NARR-MMM-001, NARR-MMM-003 | contradict, support |
| MMM-CNBC-002 | allowed | news | CNBC | NARR-MMM-001, NARR-MMM-002 | support |
| MMM-INVEST-001 | allowed | market_commentary | Investopedia | NARR-MMM-001, NARR-MMM-003 | contradict, support |
| MMM-IR-001 | allowed | company_release | 3M News Center | NARR-MMM-001, NARR-MMM-003, NARR-MMM-004 | support |
| MMM-MKT-001 | allowed | market_data | Frozen market bars | NARR-MMM-001, NARR-MMM-002, NARR-MMM-003 | contradict, support |
| MMM-MKT-002 | allowed | market_data | Frozen market bars | NARR-MMM-001 | support |
| MMM-SEC-001 | allowed | filing | 3M Investor Relations / SEC filing | NARR-MMM-001, NARR-MMM-003, NARR-MMM-004 | support |
| MMM-FUT-001 | blocked_future | company_release | n/a | NARR-MMM-001, NARR-MMM-002, NARR-MMM-003 | contradict, support |
| MMM-FUT-002 | blocked_future | filing | n/a | NARR-MMM-001, NARR-MMM-003 | contradict, support |

## Citation QA

- Replay filter: pass
- Support coverage: pass
- Event-time integrity: pass
- Citation QA: pass
- Provenance-ready allowed sources: pass
- Returned blocked sources: 0
- Narratives with support: 4/4
- Missing URLs: 0
- Missing content hashes: 0
- Low-quality evidence sources: 0

## Source Reliability

Blocked future sources are counted for auditability but excluded from scoring and ranking.
- Allowed sources: 8
- Blocked future sources: 2
- Average evidence quality: 0.76
- Average independence: 0.74
- Average originality score: 0.74
- Low-quality evidence sources: 0
- Blocked source IDs: MMM-FUT-001, MMM-FUT-002

| Publisher | Allowed | Blocked Future | Evidence Quality | Independence | Originality |
| --- | ---: | ---: | ---: | ---: | ---: |
| 3M Investor Relations / SEC filing | 1 | 0 | 0.88 | 0.86 | 0.88 |
| 3M News Center | 1 | 0 | 0.86 | 0.58 | 0.88 |
| Associated Press | 1 | 0 | 0.76 | 0.80 | 0.74 |
| CNBC | 2 | 0 | 0.75 | 0.77 | 0.74 |
| Frozen market bars | 2 | 0 | 0.69 | 0.71 | 0.62 |
| Investopedia | 1 | 0 | 0.70 | 0.72 | 0.68 |
| unknown | 0 | 2 | n/a | n/a | n/a |

## Source Clustering

Clusters use replay-safe allowed evidence only. Future-dated source text stays quarantined.
- Allowed sources clustered: 8
- Blocked future sources excluded: 2
- Cluster count: 6
- Duplicate clusters: 2
- Average derived originality: 0.75

| Cluster | Basis | Sources | Publishers | Derived Originality | Representative Claim |
| --- | --- | --- | --- | ---: | --- |
| financial-news-cnbc | independence_cluster_id | MMM-CNBC-001, MMM-CNBC-002 | CNBC | 0.50 | CNBC reported that 3M agreed to pay $6.01 billion to settle nearly 260,000 military-earplug lawsuits, that the litigation had become the largest mass tort in U.S. history, and that some analyst estimates of potential liability had been as high as $10 billion. |
| issuer-release | independence_cluster_id | MMM-IR-001 | 3M News Center | 1.00 | 3M announced on August 29, 2023 that it reached an agreement to resolve Combat Arms Earplug litigation for $6.0 billion from 2023 to 2029, structured as $5.0 billion in cash and $1.0 billion in 3M common stock, and said the agreement was not an admission of liability. |
| market-bars | independence_cluster_id | MMM-MKT-001, MMM-MKT-002 | Frozen market bars | 0.50 | Frozen market bars use MMM close-to-close prices around the settlement: $81.65 before the event day and $82.79 at the August 29, 2023 close, implying a positive event move before peer adjustment. |
| market-commentary | independence_cluster_id | MMM-INVEST-001 | Investopedia | 1.00 | Investopedia reported before markets opened on August 29, 2023 that 3M's board approved a $6 billion earplug settlement, below analyst expectations of $10 billion to $15 billion, and that the news was causing a slight rise in 3M shares. |
| sec-edgar | independence_cluster_id | MMM-SEC-001 | 3M Investor Relations / SEC filing | 1.00 | 3M's August 29, 2023 Form 8-K described the Combat Arms settlement, a $6.01 billion contribution from 2023 to 2029, a 98% participation threshold, no admission of liability, and an approximately $4.2 billion third-quarter pre-tax charge. |
| wire-news-ap | independence_cluster_id | MMM-AP-001 | Associated Press | 1.00 | Associated Press reported on August 29, 2023 that 3M agreed to pay $6 billion to settle earplug lawsuits from U.S. service members, with payments through 2029 and no admission of liability. |

## Narrative Verification Ranking

| Rank | Narrative | Direction | Score | Horizon |
| ---: | --- | --- | ---: | --- |
| 1 | Litigation overhang compression | bullish | 0.80 | 120 trading days |
| 2 | Residual legal stack dominates | bearish | 0.63 | 120 trading days |
| 3 | Settlement charge burden | bearish | 0.62 | 120 trading days |
| 4 | No-liability optics | mixed | 0.53 | 120 trading days |

## #1: Litigation overhang compression

Investors treated the Combat Arms settlement as a measurable reduction in one of 3M's largest legal overhangs, even though other liabilities remained.

Mechanism: The agreement converted a large mass-tort uncertainty into a structured payment schedule with participation thresholds and an identified charge, reducing tail-risk uncertainty enough to support a positive abnormal move.

Expected observables:
- Future company evidence should show high claimant participation or settlement implementation progress.
- Held-out sources should preserve the settlement amount and timing rather than reopening the litigation overhang.
- Residual PFAS and other liabilities may remain, but validation should center the Combat Arms overhang becoming more bounded.

Supporting evidence:
- `MMM-IR-001` (company_release): 3M announced on August 29, 2023 that it reached an agreement to resolve Combat Arms Earplug litigation for $6.0 billion from 2023 to 2029, structured as $5.0 billion in cash and $1.0 billion in 3M common stock, and said the agreement was not an admission of liability.
- `MMM-SEC-001` (filing): 3M's August 29, 2023 Form 8-K described the Combat Arms settlement, a $6.01 billion contribution from 2023 to 2029, a 98% participation threshold, no admission of liability, and an approximately $4.2 billion third-quarter pre-tax charge.
- `MMM-CNBC-001` (news): CNBC reported that 3M agreed to pay $6.01 billion to settle nearly 260,000 military-earplug lawsuits, that the litigation had become the largest mass tort in U.S. history, and that some analyst estimates of potential liability had been as high as $10 billion.
- `MMM-CNBC-002` (news): CNBC reported at 3:39 p.m. EDT on August 29, 2023 that the earplug settlement relieved one major legal overhang but that 3M still faced PFAS and other legal exposure, including a $10.3 billion water-utilities settlement awaiting approval.
- `MMM-AP-001` (news): Associated Press reported on August 29, 2023 that 3M agreed to pay $6 billion to settle earplug lawsuits from U.S. service members, with payments through 2029 and no admission of liability.
- `MMM-INVEST-001` (market_commentary): Investopedia reported before markets opened on August 29, 2023 that 3M's board approved a $6 billion earplug settlement, below analyst expectations of $10 billion to $15 billion, and that the news was causing a slight rise in 3M shares.
- `MMM-MKT-001` (market_data): Frozen market bars use MMM close-to-close prices around the settlement: $81.65 before the event day and $82.79 at the August 29, 2023 close, implying a positive event move before peer adjustment.
- `MMM-MKT-002` (market_data): Frozen benchmark bars use DOW from $46.34 to $46.89 and the Dow Jones Industrial Average from 34,559.98 to 34,852.67 on August 29, 2023 to measure the MMM move against industrial and market context.

Contradicting evidence:
- None after replay filtering.

Score components:
- evidence_strength: 0.86
- mechanism_specificity: 0.87
- source_independence: 0.78
- cross_sectional_fit: 0.68
- contradiction_resistance: 0.76
- timestamp_advantage: 0.90
- forward_observable_quality: 0.86
- crowding_risk: 0.38
- unsupported_claim_penalty: 0.04

## #2: Residual legal stack dominates

A competing explanation was that investors remained focused on 3M's broader legal stack, especially PFAS exposure, rather than assigning much value to the earplug settlement.

Mechanism: Same-day coverage emphasized that the earplug deal did not resolve all 3M legal liabilities. That was real counterevidence, but it did not explain why the settlement itself reduced a distinct mass-tort overhang.

Expected observables:
- Future validation should center PFAS or other liabilities rather than earplug settlement progress if this narrative wins.
- The stock reaction should not show positive abnormal support if residual legal risk dominates.
- The narrative should weaken if held-out sources confirm high participation in the Combat Arms settlement.

Supporting evidence:
- `MMM-CNBC-002` (news): CNBC reported at 3:39 p.m. EDT on August 29, 2023 that the earplug settlement relieved one major legal overhang but that 3M still faced PFAS and other legal exposure, including a $10.3 billion water-utilities settlement awaiting approval.

Contradicting evidence:
- `MMM-MKT-001` (market_data): Frozen market bars use MMM close-to-close prices around the settlement: $81.65 before the event day and $82.79 at the August 29, 2023 close, implying a positive event move before peer adjustment.

Score components:
- evidence_strength: 0.72
- mechanism_specificity: 0.70
- source_independence: 0.76
- cross_sectional_fit: 0.48
- contradiction_resistance: 0.50
- timestamp_advantage: 0.86
- forward_observable_quality: 0.68
- crowding_risk: 0.82
- unsupported_claim_penalty: 0.10

## #3: Settlement charge burden

The move could have reflected concern that the settlement still imposed a multi-year cash, stock, and earnings charge burden on 3M.

Mechanism: 3M disclosed a $6.0 billion contribution schedule and a third-quarter pre-tax charge, creating a plausible burden narrative. The burden was visible, but it was also the price of reducing litigation uncertainty.

Expected observables:
- Future disclosures should focus on cash strain, financing pressure, or inability to satisfy settlement terms.
- The burden narrative should weaken if future company evidence confirms participation progress and cash election clarity.
- Market evidence should be negative relative to industrial peers if the charge burden dominates.

Supporting evidence:
- `MMM-IR-001` (company_release): 3M announced on August 29, 2023 that it reached an agreement to resolve Combat Arms Earplug litigation for $6.0 billion from 2023 to 2029, structured as $5.0 billion in cash and $1.0 billion in 3M common stock, and said the agreement was not an admission of liability.
- `MMM-SEC-001` (filing): 3M's August 29, 2023 Form 8-K described the Combat Arms settlement, a $6.01 billion contribution from 2023 to 2029, a 98% participation threshold, no admission of liability, and an approximately $4.2 billion third-quarter pre-tax charge.

Contradicting evidence:
- `MMM-CNBC-001` (news): CNBC reported that 3M agreed to pay $6.01 billion to settle nearly 260,000 military-earplug lawsuits, that the litigation had become the largest mass tort in U.S. history, and that some analyst estimates of potential liability had been as high as $10 billion.
- `MMM-INVEST-001` (market_commentary): Investopedia reported before markets opened on August 29, 2023 that 3M's board approved a $6 billion earplug settlement, below analyst expectations of $10 billion to $15 billion, and that the news was causing a slight rise in 3M shares.
- `MMM-MKT-001` (market_data): Frozen market bars use MMM close-to-close prices around the settlement: $81.65 before the event day and $82.79 at the August 29, 2023 close, implying a positive event move before peer adjustment.

Score components:
- evidence_strength: 0.70
- mechanism_specificity: 0.74
- source_independence: 0.62
- cross_sectional_fit: 0.38
- contradiction_resistance: 0.54
- timestamp_advantage: 0.88
- forward_observable_quality: 0.70
- crowding_risk: 0.58
- unsupported_claim_penalty: 0.08

## #4: No-liability optics

Another explanation was that the market focused on 3M's no-admission language and continued product-defense posture rather than the economics of the settlement.

Mechanism: The no-admission language reduced reputational and legal read-through but was less directly tied to valuation than the quantified settlement amount, charge, and participation thresholds.

Expected observables:
- Future validation should cite litigation posture rather than participation milestones if this narrative wins.
- The explanation should remain secondary if held-out evidence centers economics and claimant participation.
- Follow-up sources should maintain the distinction between settlement economics and admission of liability.

Supporting evidence:
- `MMM-IR-001` (company_release): 3M announced on August 29, 2023 that it reached an agreement to resolve Combat Arms Earplug litigation for $6.0 billion from 2023 to 2029, structured as $5.0 billion in cash and $1.0 billion in 3M common stock, and said the agreement was not an admission of liability.
- `MMM-SEC-001` (filing): 3M's August 29, 2023 Form 8-K described the Combat Arms settlement, a $6.01 billion contribution from 2023 to 2029, a 98% participation threshold, no admission of liability, and an approximately $4.2 billion third-quarter pre-tax charge.
- `MMM-AP-001` (news): Associated Press reported on August 29, 2023 that 3M agreed to pay $6 billion to settle earplug lawsuits from U.S. service members, with payments through 2029 and no admission of liability.

Contradicting evidence:
- None after replay filtering.

Score components:
- evidence_strength: 0.58
- mechanism_specificity: 0.56
- source_independence: 0.54
- cross_sectional_fit: 0.42
- contradiction_resistance: 0.52
- timestamp_advantage: 0.86
- forward_observable_quality: 0.46
- crowding_risk: 0.50
- unsupported_claim_penalty: 0.11

## Scoring Weights

- evidence_strength: 0.20
- mechanism_specificity: 0.15
- source_independence: 0.15
- cross_sectional_fit: 0.10
- contradiction_resistance: 0.10
- timestamp_advantage: 0.10
- forward_observable_quality: 0.10
- crowding_risk: 0.05
- unsupported_claim_penalty: 0.05

## Evaluation Checks

These deterministic checks use the ranked replay output plus separately loaded validation rows.
- Validated narrative IDs: NARR-MMM-001
- Validated narrative rank: #1
- Narrative Recall@3: pass
- Replay rank #1 validated: pass
- Average unsupported claim penalty: 0.08
- Max unsupported claim penalty: 0.11
- High unsupported-claim penalty narratives: 2
- Blocked future source count: 2

## Model Comparison

| System | Selected Narrative | Rank | Validated | Selection Rule |
| --- | --- | ---: | --- | --- |
| headline_baseline | NARR-MMM-002 | #2 | miss | Selects the most crowded allowed narrative as a proxy for surface consensus. |
| evidence_only | NARR-MMM-001 | #1 | pass | Ablation that selects the strongest evidence score without mechanism or contradiction terms. |
| no_contradiction_penalty | NARR-MMM-001 | #1 | pass | Ablation that reranks without contradiction resistance or unsupported-claim penalty. |
| quality_weighted | NARR-MMM-001 | #1 | pass | Ablation that selects the strongest evidence score weighted by allowed source quality. |
| narrativedesk_tournament | NARR-MMM-001 | #1 | pass | Selects the highest deterministic narrative score after replay filtering. |

## Future Validation Fixture

Validation data is shown separately from event-time evidence so it cannot leak into generation.
- Note: Real-curated validation fixture. Held-out future evidence stays separate from event-time replay inputs.
- Future validation source IDs: MMM-FUT-001, MMM-FUT-002

| Window | Label | Expected Observable | Future Sources | Validation Outcome |
| --- | --- | --- | --- | --- |
| T+60 | validated | Future company evidence should show high claimant participation or settlement implementation progress. | MMM-FUT-001, MMM-FUT-002 | Held-out 3M evidence said claimant participation was on track to exceed the 98% threshold and later filing language preserved the settlement structure, validating litigation overhang compression as the replay winner. |
| T+60 | partial | Future validation should center PFAS or other liabilities rather than earplug settlement progress if this narrative wins. | MMM-FUT-001 | Residual legal exposure remained relevant, but the held-out validation evidence directly centered Combat Arms participation and settlement implementation. |
| T+60 | invalidated | The burden narrative should weaken if future company evidence confirms participation progress and cash election clarity. | MMM-FUT-001 | 3M later said participation was on track to exceed the threshold and elected cash for the stock component, weakening the idea that settlement burden was the primary event narrative. |
| T+60 | pending | Future validation should cite litigation posture rather than participation milestones if this narrative wins. | none | The no-liability posture remained part of the case file but did not become the central held-out validation evidence. |
