# NarrativeDesk Event Report: SAVE

> Research support output. Not investment advice.

## Data Note

This report is generated from a real-curated replay bundle. Treat it as research support only; public use requires curator review of source URLs, publication timestamps, raw document hashes, and validation status.

## Event

- Event ID: `EVT-REAL-SAVE-2024-01-16`
- Company: Spirit Airlines, Inc. (`SAVE`)
- Timestamp lock: `2024-01-16T16:10:00-05:00`
- Event type: regulatory/antitrust shock
- Daily return: -47.1%
- Abnormal return: -46.6%
- Volume ratio: n/a
- Sector ETF return: 0.8%
- Peer median return: -0.5%

Real-curated Spirit Airlines regulatory shock replay after the JetBlue acquisition was blocked. Research and education only; not investment advice.

## Replay Audit

- Allowed sources: SAVE-AP-001, SAVE-CNBC-001, SAVE-DOJ-001, SAVE-MF-001, SAVE-MKT-001, SAVE-MKT-002, SAVE-REUTERS-001
- Blocked future sources: SAVE-FUT-001, SAVE-FUT-002
- Removed from `NARR-SAVE-001`: SAVE-FUT-001, SAVE-FUT-002
- Removed from `NARR-SAVE-002`: SAVE-FUT-001
- Removed from `NARR-SAVE-003`: SAVE-FUT-001, SAVE-FUT-002

## Source Map

| Source | Status | Type | Publisher | Narratives | Relations |
| --- | --- | --- | --- | --- | --- |
| SAVE-AP-001 | allowed | news | Associated Press / WBUR | NARR-SAVE-001, NARR-SAVE-003, NARR-SAVE-004 | contradict, support |
| SAVE-CNBC-001 | allowed | news | CNBC | NARR-SAVE-001, NARR-SAVE-002, NARR-SAVE-003, NARR-SAVE-004 | contradict, support |
| SAVE-DOJ-001 | allowed | agency_statement | U.S. Department of Justice | NARR-SAVE-001, NARR-SAVE-003, NARR-SAVE-004 | contradict, support |
| SAVE-MF-001 | allowed | market_commentary | The Motley Fool | NARR-SAVE-001, NARR-SAVE-002 | support |
| SAVE-MKT-001 | allowed | market_data | Frozen market bars | NARR-SAVE-001, NARR-SAVE-004 | contradict, support |
| SAVE-MKT-002 | allowed | market_data | Frozen market bars | NARR-SAVE-001, NARR-SAVE-004 | contradict, support |
| SAVE-REUTERS-001 | allowed | news | Reuters / Investing.com | NARR-SAVE-001, NARR-SAVE-003, NARR-SAVE-004 | contradict, support |
| SAVE-FUT-001 | blocked_future | company_statement | n/a | NARR-SAVE-001, NARR-SAVE-002, NARR-SAVE-003 | contradict, support |
| SAVE-FUT-002 | blocked_future | news | n/a | NARR-SAVE-001, NARR-SAVE-003 | contradict, support |

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
- Allowed sources: 7
- Blocked future sources: 2
- Average evidence quality: 0.75
- Average independence: 0.76
- Average originality score: 0.72
- Low-quality evidence sources: 0
- Blocked source IDs: SAVE-FUT-001, SAVE-FUT-002

| Publisher | Allowed | Blocked Future | Evidence Quality | Independence | Originality |
| --- | ---: | ---: | ---: | ---: | ---: |
| Associated Press / WBUR | 1 | 0 | 0.76 | 0.78 | 0.74 |
| CNBC | 1 | 0 | 0.80 | 0.76 | 0.78 |
| Frozen market bars | 2 | 0 | 0.71 | 0.71 | 0.62 |
| Reuters / Investing.com | 1 | 0 | 0.76 | 0.78 | 0.74 |
| The Motley Fool | 1 | 0 | 0.66 | 0.68 | 0.66 |
| U.S. Department of Justice | 1 | 0 | 0.88 | 0.88 | 0.90 |
| unknown | 0 | 2 | n/a | n/a | n/a |

## Source Clustering

Clusters use replay-safe allowed evidence only. Future-dated source text stays quarantined.
- Allowed sources clustered: 7
- Blocked future sources excluded: 2
- Cluster count: 6
- Duplicate clusters: 1
- Average derived originality: 0.86

| Cluster | Basis | Sources | Publishers | Derived Originality | Representative Claim |
| --- | --- | --- | --- | ---: | --- |
| financial-news-cnbc | independence_cluster_id | SAVE-CNBC-001 | CNBC | 1.00 | CNBC reported at 1:04 p.m. EST on January 16, 2024 that a federal judge blocked JetBlue's purchase of Spirit, that the DOJ argued the deal was anticompetitive, that the companies disagreed and were evaluating next steps, and that Spirit shares lost 47% Tuesday while JetBlue gained about 5%. |
| government-antitrust | independence_cluster_id | SAVE-DOJ-001 | U.S. Department of Justice | 1.00 | The Justice Department stated on January 16, 2024 that the U.S. District Court blocked JetBlue's $3.8 billion acquisition of Spirit and described the ruling as protection against anticompetitive harm. |
| market-bars | independence_cluster_id | SAVE-MKT-001, SAVE-MKT-002 | Frozen market bars | 0.50 | Frozen market bars use SAVE close-to-close prices around the ruling: $14.97 before the decision and $7.92 at the January 16, 2024 close, implying a roughly -47.1% event move before peer adjustment. |
| market-commentary | independence_cluster_id | SAVE-MF-001 | The Motley Fool | 1.00 | The Motley Fool reported on January 16, 2024 that Spirit shares were down more than 50% while JetBlue rose after the federal court blocked the proposed acquisition, sending both companies back to stand-alone planning. |
| wire-news-ap | independence_cluster_id | SAVE-AP-001 | Associated Press / WBUR | 1.00 | Associated Press reporting carried by WBUR said a federal judge blocked JetBlue from buying Spirit, said the deal would reduce competition, and emphasized Spirit as an important low-cost airline for price-sensitive travelers. |
| wire-news-reuters | independence_cluster_id | SAVE-REUTERS-001 | Reuters / Investing.com | 1.00 | Reuters reporting through Investing.com said the court blocked JetBlue's planned $3.8 billion acquisition of Spirit after agreeing with the DOJ that the deal was anticompetitive and would harm ticket buyers. |

## Narrative Verification Ranking

| Rank | Narrative | Direction | Score | Horizon |
| ---: | --- | --- | ---: | --- |
| 1 | Merger optionality collapse | bearish | 0.84 | 60 trading days |
| 2 | Standalone balance sheet stress | bearish | 0.67 | 60 trading days |
| 3 | Appeal path preserved value | mixed | 0.54 | 60 trading days |
| 4 | Airline regulatory read-through | bearish | 0.51 | 60 trading days |

## #1: Merger optionality collapse

Investors repriced Spirit after the court ruling removed most of the embedded JetBlue acquisition optionality from the equity story.

Mechanism: The ruling directly blocked the $3.8 billion acquisition path, turning a deal-spread security back into a standalone ultra-low-cost carrier with weaker financing optionality. Same-day market evidence showed the move was concentrated in Spirit rather than airline peers.

Expected observables:
- Future company statements should confirm that legal and regulatory conditions made the transaction impossible to close.
- Held-out validation should show the merger agreement terminated rather than merely delayed.
- The abnormal move should remain much larger than airline peer moves around the replay lock.

Supporting evidence:
- `SAVE-DOJ-001` (agency_statement): The Justice Department stated on January 16, 2024 that the U.S. District Court blocked JetBlue's $3.8 billion acquisition of Spirit and described the ruling as protection against anticompetitive harm.
- `SAVE-CNBC-001` (news): CNBC reported at 1:04 p.m. EST on January 16, 2024 that a federal judge blocked JetBlue's purchase of Spirit, that the DOJ argued the deal was anticompetitive, that the companies disagreed and were evaluating next steps, and that Spirit shares lost 47% Tuesday while JetBlue gained about 5%.
- `SAVE-AP-001` (news): Associated Press reporting carried by WBUR said a federal judge blocked JetBlue from buying Spirit, said the deal would reduce competition, and emphasized Spirit as an important low-cost airline for price-sensitive travelers.
- `SAVE-REUTERS-001` (news): Reuters reporting through Investing.com said the court blocked JetBlue's planned $3.8 billion acquisition of Spirit after agreeing with the DOJ that the deal was anticompetitive and would harm ticket buyers.
- `SAVE-MF-001` (market_commentary): The Motley Fool reported on January 16, 2024 that Spirit shares were down more than 50% while JetBlue rose after the federal court blocked the proposed acquisition, sending both companies back to stand-alone planning.
- `SAVE-MKT-001` (market_data): Frozen market bars use SAVE close-to-close prices around the ruling: $14.97 before the decision and $7.92 at the January 16, 2024 close, implying a roughly -47.1% event move before peer adjustment.
- `SAVE-MKT-002` (market_data): Frozen airline peer bars use AAL from $13.08 to $13.19 and DAL from $37.29 to $36.63 on January 16, 2024, showing the Spirit decline was far larger than peer airline moves.

Contradicting evidence:
- None after replay filtering.

Score components:
- evidence_strength: 0.87
- mechanism_specificity: 0.90
- source_independence: 0.82
- cross_sectional_fit: 0.88
- contradiction_resistance: 0.80
- timestamp_advantage: 0.92
- forward_observable_quality: 0.84
- crowding_risk: 0.36
- unsupported_claim_penalty: 0.04

## #2: Standalone balance sheet stress

The selloff could also reflect investors refocusing on Spirit as a standalone airline with debt, aircraft, and demand pressures once the deal support weakened.

Mechanism: Replay-time reporting already noted Spirit had been struggling with grounded airplanes and softer travel demand. The ruling mattered partly because it forced those standalone operating risks back into the valuation.

Expected observables:
- Future disclosures should emphasize refinancing, liquidity, or profitability actions.
- Validation should separate standalone stress from the immediate loss of merger consideration.
- If this narrative is primary, later sources should focus more on solvency than antitrust termination.

Supporting evidence:
- `SAVE-CNBC-001` (news): CNBC reported at 1:04 p.m. EST on January 16, 2024 that a federal judge blocked JetBlue's purchase of Spirit, that the DOJ argued the deal was anticompetitive, that the companies disagreed and were evaluating next steps, and that Spirit shares lost 47% Tuesday while JetBlue gained about 5%.
- `SAVE-MF-001` (market_commentary): The Motley Fool reported on January 16, 2024 that Spirit shares were down more than 50% while JetBlue rose after the federal court blocked the proposed acquisition, sending both companies back to stand-alone planning.

Contradicting evidence:
- None after replay filtering.

Score components:
- evidence_strength: 0.74
- mechanism_specificity: 0.72
- source_independence: 0.70
- cross_sectional_fit: 0.66
- contradiction_resistance: 0.58
- timestamp_advantage: 0.86
- forward_observable_quality: 0.68
- crowding_risk: 0.72
- unsupported_claim_penalty: 0.09

## #3: Appeal path preserved value

A competing explanation was that the market reaction over-discounted the ruling because JetBlue and Spirit could still appeal or evaluate legal next steps.

Mechanism: The companies disagreed with the ruling and evaluated next steps, but that path was lower quality at the replay lock because the court and DOJ evidence directly blocked the transaction mechanism.

Expected observables:
- Future evidence should show a successful appeal or revived merger path if this narrative wins.
- The narrative should weaken if the companies terminate the agreement because closing conditions cannot be met.
- Market recovery should be broad and durable if appeal optionality remains central.

Supporting evidence:
- `SAVE-CNBC-001` (news): CNBC reported at 1:04 p.m. EST on January 16, 2024 that a federal judge blocked JetBlue's purchase of Spirit, that the DOJ argued the deal was anticompetitive, that the companies disagreed and were evaluating next steps, and that Spirit shares lost 47% Tuesday while JetBlue gained about 5%.

Contradicting evidence:
- `SAVE-DOJ-001` (agency_statement): The Justice Department stated on January 16, 2024 that the U.S. District Court blocked JetBlue's $3.8 billion acquisition of Spirit and described the ruling as protection against anticompetitive harm.
- `SAVE-AP-001` (news): Associated Press reporting carried by WBUR said a federal judge blocked JetBlue from buying Spirit, said the deal would reduce competition, and emphasized Spirit as an important low-cost airline for price-sensitive travelers.
- `SAVE-REUTERS-001` (news): Reuters reporting through Investing.com said the court blocked JetBlue's planned $3.8 billion acquisition of Spirit after agreeing with the DOJ that the deal was anticompetitive and would harm ticket buyers.

Score components:
- evidence_strength: 0.62
- mechanism_specificity: 0.58
- source_independence: 0.64
- cross_sectional_fit: 0.42
- contradiction_resistance: 0.38
- timestamp_advantage: 0.82
- forward_observable_quality: 0.60
- crowding_risk: 0.80
- unsupported_claim_penalty: 0.13

## #4: Airline regulatory read-through

The ruling may have been read as a broader regulatory warning for airline consolidation rather than a Spirit-specific deal-value collapse.

Mechanism: News coverage raised questions about other airline deals, but peer market bars showed the extreme move was isolated in Spirit, making the read-through less specific than lost merger optionality.

Expected observables:
- Other airline merger targets or peers should show similar abnormal pressure if this narrative dominates.
- Future regulatory commentary should generalize the ruling beyond Spirit and JetBlue.
- The explanation should weaken if Spirit-specific termination evidence becomes the validation anchor.

Supporting evidence:
- `SAVE-DOJ-001` (agency_statement): The Justice Department stated on January 16, 2024 that the U.S. District Court blocked JetBlue's $3.8 billion acquisition of Spirit and described the ruling as protection against anticompetitive harm.
- `SAVE-AP-001` (news): Associated Press reporting carried by WBUR said a federal judge blocked JetBlue from buying Spirit, said the deal would reduce competition, and emphasized Spirit as an important low-cost airline for price-sensitive travelers.
- `SAVE-REUTERS-001` (news): Reuters reporting through Investing.com said the court blocked JetBlue's planned $3.8 billion acquisition of Spirit after agreeing with the DOJ that the deal was anticompetitive and would harm ticket buyers.

Contradicting evidence:
- `SAVE-CNBC-001` (news): CNBC reported at 1:04 p.m. EST on January 16, 2024 that a federal judge blocked JetBlue's purchase of Spirit, that the DOJ argued the deal was anticompetitive, that the companies disagreed and were evaluating next steps, and that Spirit shares lost 47% Tuesday while JetBlue gained about 5%.
- `SAVE-MKT-001` (market_data): Frozen market bars use SAVE close-to-close prices around the ruling: $14.97 before the decision and $7.92 at the January 16, 2024 close, implying a roughly -47.1% event move before peer adjustment.
- `SAVE-MKT-002` (market_data): Frozen airline peer bars use AAL from $13.08 to $13.19 and DAL from $37.29 to $36.63 on January 16, 2024, showing the Spirit decline was far larger than peer airline moves.

Score components:
- evidence_strength: 0.58
- mechanism_specificity: 0.50
- source_independence: 0.68
- cross_sectional_fit: 0.32
- contradiction_resistance: 0.46
- timestamp_advantage: 0.80
- forward_observable_quality: 0.46
- crowding_risk: 0.62
- unsupported_claim_penalty: 0.12

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
- Validated narrative IDs: NARR-SAVE-001
- Validated narrative rank: #1
- Narrative Recall@3: pass
- Replay rank #1 validated: pass
- Average unsupported claim penalty: 0.10
- Max unsupported claim penalty: 0.13
- High unsupported-claim penalty narratives: 2
- Blocked future source count: 2

## Model Comparison

| System | Selected Narrative | Rank | Validated | Selection Rule |
| --- | --- | ---: | --- | --- |
| headline_baseline | NARR-SAVE-003 | #3 | miss | Selects the most crowded allowed narrative as a proxy for surface consensus. |
| evidence_only | NARR-SAVE-001 | #1 | pass | Ablation that selects the strongest evidence score without mechanism or contradiction terms. |
| no_contradiction_penalty | NARR-SAVE-001 | #1 | pass | Ablation that reranks without contradiction resistance or unsupported-claim penalty. |
| quality_weighted | NARR-SAVE-001 | #1 | pass | Ablation that selects the strongest evidence score weighted by allowed source quality. |
| narrativedesk_tournament | NARR-SAVE-001 | #1 | pass | Selects the highest deterministic narrative score after replay filtering. |

## Future Validation Fixture

Validation data is shown separately from event-time evidence so it cannot leak into generation.
- Note: Real-curated validation fixture. Held-out future evidence stays separate from event-time replay inputs.
- Future validation source IDs: SAVE-FUT-001, SAVE-FUT-002

| Window | Label | Expected Observable | Future Sources | Validation Outcome |
| --- | --- | --- | --- | --- |
| T+60 | validated | Held-out validation should show the merger agreement terminated rather than merely delayed. | SAVE-FUT-001, SAVE-FUT-002 | Held-out March 4 company and news evidence showed JetBlue and Spirit terminated the merger agreement because regulatory obstacles made timely closing unlikely, validating merger optionality collapse as the replay winner. |
| T+60 | partial | Future disclosures should emphasize refinancing, liquidity, or profitability actions. | SAVE-FUT-001 | Spirit did discuss standalone initiatives, refinancing, and profitability steps, but the validation source was still anchored to termination of the merger path. |
| T+60 | invalidated | The narrative should weaken if the companies terminate the agreement because closing conditions cannot be met. | SAVE-FUT-001, SAVE-FUT-002 | The companies terminated the agreement rather than preserving a live appeal-led deal path, weakening the appeal optionality explanation. |
| T+60 | pending | Other airline merger targets or peers should show similar abnormal pressure if this narrative dominates. | none | The validation fixture keeps broader airline regulatory read-through pending because the held-out evidence was specific to JetBlue and Spirit. |
