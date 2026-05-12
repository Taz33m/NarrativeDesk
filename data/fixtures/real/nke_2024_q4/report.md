# NarrativeDesk Event Report: NKE

> Research support output. Not investment advice.

## Data Note

This report is generated from a real-curated replay bundle. Treat it as research support only; public use requires curator review of source URLs, publication timestamps, raw document hashes, and validation status.

## Event

- Event ID: `EVT-REAL-NKE-2024-06-27`
- Company: NIKE, Inc. (`NKE`)
- Timestamp lock: `2024-06-28T10:00:00-04:00`
- Event type: earnings/guidance
- Daily return: -20.0%
- Abnormal return: -19.6%
- Volume ratio: n/a
- Sector ETF return: -0.4%
- Peer median return: -0.4%

Real-curated NIKE fiscal 2024 fourth-quarter earnings and fiscal 2025 guidance replay with timestamped citations, replay-locked evidence, and held-out validation. Research and education only; not investment advice.

## Replay Audit

- Allowed sources: NKE-INVEST-001, NKE-INVEST-002, NKE-IR-001, NKE-MB-001, NKE-MKT-001, NKE-MKT-BENCH-001, NKE-NASDAQ-001, NKE-SEC-001
- Blocked future sources: NKE-IR-FUT-001
- Removed from `NARR-NKE-001`: NKE-IR-FUT-001
- Removed from `NARR-NKE-002`: NKE-IR-FUT-001
- Removed from `NARR-NKE-004`: NKE-IR-FUT-001

## Source Map

| Source | Status | Type | Publisher | Narratives | Relations |
| --- | --- | --- | --- | --- | --- |
| NKE-INVEST-001 | allowed | news | Investopedia | NARR-NKE-001, NARR-NKE-004 | contradict, support |
| NKE-INVEST-002 | allowed | news | Investopedia | NARR-NKE-001, NARR-NKE-003, NARR-NKE-004 | contradict, support |
| NKE-IR-001 | allowed | company_release | NIKE Investor Relations | NARR-NKE-001, NARR-NKE-002, NARR-NKE-004 | contradict, support |
| NKE-MB-001 | allowed | transcript | MarketBeat / Quartr | NARR-NKE-001, NARR-NKE-002, NARR-NKE-003, NARR-NKE-004 | contradict, support |
| NKE-MKT-001 | allowed | market_data | Frozen market bars | NARR-NKE-001, NARR-NKE-002, NARR-NKE-004 | contradict, support |
| NKE-MKT-BENCH-001 | allowed | market_data | Frozen market bars | NARR-NKE-001, NARR-NKE-003 | support |
| NKE-NASDAQ-001 | allowed | company_release | Nasdaq / Business Wire | NARR-NKE-001, NARR-NKE-002, NARR-NKE-004 | support |
| NKE-SEC-001 | allowed | filing | SEC EDGAR | NARR-NKE-001, NARR-NKE-002 | support |
| NKE-IR-FUT-001 | blocked_future | company_release | n/a | NARR-NKE-001, NARR-NKE-002, NARR-NKE-004 | contradict, support |

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
- Blocked future sources: 1
- Average evidence quality: 0.78
- Average independence: 0.71
- Average originality score: 0.76
- Low-quality evidence sources: 0
- Blocked source IDs: NKE-IR-FUT-001

| Publisher | Allowed | Blocked Future | Evidence Quality | Independence | Originality |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frozen market bars | 2 | 0 | 0.80 | 0.84 | 0.80 |
| Investopedia | 2 | 0 | 0.74 | 0.74 | 0.74 |
| MarketBeat / Quartr | 1 | 0 | 0.78 | 0.70 | 0.77 |
| NIKE Investor Relations | 1 | 0 | 0.86 | 0.58 | 0.86 |
| Nasdaq / Business Wire | 1 | 0 | 0.78 | 0.56 | 0.72 |
| SEC EDGAR | 1 | 0 | 0.76 | 0.68 | 0.66 |
| unknown | 0 | 1 | n/a | n/a | n/a |

## Source Clustering

Clusters use replay-safe allowed evidence only. Future-dated source text stays quarantined.
- Allowed sources clustered: 8
- Blocked future sources excluded: 1
- Cluster count: 6
- Duplicate clusters: 2
- Average derived originality: 0.75

| Cluster | Basis | Sources | Publishers | Derived Originality | Representative Claim |
| --- | --- | --- | --- | ---: | --- |
| earnings-transcript | independence_cluster_id | NKE-MB-001 | MarketBeat / Quartr | 1.00 | The MarketBeat/Quartr earnings transcript recorded CFO Matthew Friend saying NIKE expected fiscal 2025 reported revenue to be down mid-single digits, the first half down high single digits, and first-quarter revenue down approximately 10%, citing classic footwear franchise management, digital challenges, muted wholesale order books, and a softer Greater China outlook. |
| financial-news | independence_cluster_id | NKE-INVEST-001, NKE-INVEST-002 | Investopedia | 0.50 | Investopedia reported after the release that NIKE revenue missed analyst estimates, the company said results drove it to update fiscal 2025 guidance, and shares fell in extended trading despite net income and EPS coming in above year-earlier levels and estimates. |
| issuer-release | independence_cluster_id | NKE-IR-001 | NIKE Investor Relations | 1.00 | NIKE reported fiscal 2024 fourth-quarter revenue of $12.6 billion, down 2% reported, NIKE Direct revenue down 8% reported, gross margin up 110 basis points to 44.7%, diluted EPS of $0.99, and management said fourth-quarter challenges led it to update the fiscal 2025 outlook. |
| issuer-release-mirrors | independence_cluster_id | NKE-NASDAQ-001 | Nasdaq / Business Wire | 1.00 | Nasdaq carried the Business Wire version of NIKE fiscal 2024 fourth-quarter results at 4:15 p.m. EDT, including the revenue decline, NIKE Direct decline, gross-margin increase, EPS result, and management comments about updating fiscal 2025 outlook. |
| market-bars | independence_cluster_id | NKE-MKT-001, NKE-MKT-BENCH-001 | Frozen market bars | 0.50 | Frozen market bars use NIKE close-to-close prices around the event: $90.52 on June 27, 2024 and $72.44 on June 28, 2024, implying a -19.97% event move before peer adjustment. |
| sec-edgar | independence_cluster_id | NKE-SEC-001 | SEC EDGAR | 1.00 | NIKE filed a Form 8-K on June 27, 2024 stating it issued a press release disclosing financial results for the fiscal quarter and year ended May 31, 2024 and furnished the release as Exhibit 99.1. |

## Narrative Verification Ranking

| Rank | Narrative | Direction | Score | Horizon |
| ---: | --- | --- | ---: | --- |
| 1 | Fiscal 2025 demand reset | bearish | 0.80 | 60 trading days |
| 2 | Direct channel reset | bearish | 0.72 | 60 trading days |
| 3 | China and consumer softness | bearish | 0.61 | 60 trading days |
| 4 | Margin and EPS resilience | mixed | 0.51 | 60 trading days |

## #1: Fiscal 2025 demand reset

Investors repriced NIKE after the company lowered the fiscal 2025 revenue outlook, with the selloff centered on weaker forward demand rather than the reported quarter alone.

Mechanism: The event-time evidence showed a revenue miss, explicit fiscal 2025 outlook reset, a first-quarter decline guide, and weak digital/lifestyle demand. That created a direct mechanism from lower future revenue expectations to the abnormal stock move.

Expected observables:
- Later reported results should show revenue pressure extending beyond the fourth-quarter release.
- Follow-up commentary should keep turnaround timing, demand, or guidance credibility central.
- The explanation should survive even if gross margin and EPS were stronger than the headline revenue story.

Supporting evidence:
- `NKE-IR-001` (company_release): NIKE reported fiscal 2024 fourth-quarter revenue of $12.6 billion, down 2% reported, NIKE Direct revenue down 8% reported, gross margin up 110 basis points to 44.7%, diluted EPS of $0.99, and management said fourth-quarter challenges led it to update the fiscal 2025 outlook.
- `NKE-SEC-001` (filing): NIKE filed a Form 8-K on June 27, 2024 stating it issued a press release disclosing financial results for the fiscal quarter and year ended May 31, 2024 and furnished the release as Exhibit 99.1.
- `NKE-NASDAQ-001` (company_release): Nasdaq carried the Business Wire version of NIKE fiscal 2024 fourth-quarter results at 4:15 p.m. EDT, including the revenue decline, NIKE Direct decline, gross-margin increase, EPS result, and management comments about updating fiscal 2025 outlook.
- `NKE-INVEST-001` (news): Investopedia reported after the release that NIKE revenue missed analyst estimates, the company said results drove it to update fiscal 2025 guidance, and shares fell in extended trading despite net income and EPS coming in above year-earlier levels and estimates.
- `NKE-INVEST-002` (news): Investopedia reported before the market open on June 28, 2024 that NIKE shares were down about 15% premarket after lower-than-expected quarterly revenue and lowered fiscal 2025 sales guidance, including management commentary that first-quarter revenue was expected to decline approximately 10%.
- `NKE-MB-001` (transcript): The MarketBeat/Quartr earnings transcript recorded CFO Matthew Friend saying NIKE expected fiscal 2025 reported revenue to be down mid-single digits, the first half down high single digits, and first-quarter revenue down approximately 10%, citing classic footwear franchise management, digital challenges, muted wholesale order books, and a softer Greater China outlook.
- `NKE-MKT-001` (market_data): Frozen market bars use NIKE close-to-close prices around the event: $90.52 on June 27, 2024 and $72.44 on June 28, 2024, implying a -19.97% event move before peer adjustment.
- `NKE-MKT-BENCH-001` (market_data): Frozen benchmark bars use SPY close-to-close prices around the NIKE event: $538.15 on June 27, 2024 and $536.03 on June 28, 2024, making NIKE underperform the broad-market benchmark on the event day.

Contradicting evidence:
- None after replay filtering.

Score components:
- evidence_strength: 0.86
- mechanism_specificity: 0.87
- source_independence: 0.72
- cross_sectional_fit: 0.82
- contradiction_resistance: 0.78
- timestamp_advantage: 0.90
- forward_observable_quality: 0.84
- crowding_risk: 0.38
- unsupported_claim_penalty: 0.04

## #2: Direct channel reset

The move could be explained by investors reassessing NIKE Direct and digital channel execution after the company reported declines in Direct, digital, and key lifestyle franchises.

Mechanism: Direct and digital weakness made the channel strategy look less durable, but the explanation is narrower than the full fiscal 2025 demand reset because it does not fully explain the guide-down and broad revenue repricing.

Expected observables:
- Future results should keep NIKE Direct and digital revenue declines central.
- Management should continue discussing franchise management or channel rebalancing.
- The narrative should weaken if total revenue pressure, not channel mix alone, dominates validation evidence.

Supporting evidence:
- `NKE-IR-001` (company_release): NIKE reported fiscal 2024 fourth-quarter revenue of $12.6 billion, down 2% reported, NIKE Direct revenue down 8% reported, gross margin up 110 basis points to 44.7%, diluted EPS of $0.99, and management said fourth-quarter challenges led it to update the fiscal 2025 outlook.
- `NKE-SEC-001` (filing): NIKE filed a Form 8-K on June 27, 2024 stating it issued a press release disclosing financial results for the fiscal quarter and year ended May 31, 2024 and furnished the release as Exhibit 99.1.
- `NKE-NASDAQ-001` (company_release): Nasdaq carried the Business Wire version of NIKE fiscal 2024 fourth-quarter results at 4:15 p.m. EDT, including the revenue decline, NIKE Direct decline, gross-margin increase, EPS result, and management comments about updating fiscal 2025 outlook.
- `NKE-MB-001` (transcript): The MarketBeat/Quartr earnings transcript recorded CFO Matthew Friend saying NIKE expected fiscal 2025 reported revenue to be down mid-single digits, the first half down high single digits, and first-quarter revenue down approximately 10%, citing classic footwear franchise management, digital challenges, muted wholesale order books, and a softer Greater China outlook.
- `NKE-MKT-001` (market_data): Frozen market bars use NIKE close-to-close prices around the event: $90.52 on June 27, 2024 and $72.44 on June 28, 2024, implying a -19.97% event move before peer adjustment.

Contradicting evidence:
- None after replay filtering.

Score components:
- evidence_strength: 0.78
- mechanism_specificity: 0.79
- source_independence: 0.66
- cross_sectional_fit: 0.70
- contradiction_resistance: 0.68
- timestamp_advantage: 0.86
- forward_observable_quality: 0.74
- crowding_risk: 0.44
- unsupported_claim_penalty: 0.06

## #3: China and consumer softness

The selloff may have reflected macro and geographic concerns, especially weaker Greater China and uneven consumer trends across discretionary markets.

Mechanism: China and consumer caution are plausible contributors, but they are less specific to the observed abnormal move than the company-level fiscal 2025 revenue reset and channel details available before the lock.

Expected observables:
- Future commentary should cite Greater China or macro uncertainty as the main driver.
- Peer consumer discretionary names should show related pressure if the explanation is mostly macro.
- The narrative should weaken if company-specific guide-down evidence explains more of the move.

Supporting evidence:
- `NKE-INVEST-002` (news): Investopedia reported before the market open on June 28, 2024 that NIKE shares were down about 15% premarket after lower-than-expected quarterly revenue and lowered fiscal 2025 sales guidance, including management commentary that first-quarter revenue was expected to decline approximately 10%.
- `NKE-MB-001` (transcript): The MarketBeat/Quartr earnings transcript recorded CFO Matthew Friend saying NIKE expected fiscal 2025 reported revenue to be down mid-single digits, the first half down high single digits, and first-quarter revenue down approximately 10%, citing classic footwear franchise management, digital challenges, muted wholesale order books, and a softer Greater China outlook.
- `NKE-MKT-BENCH-001` (market_data): Frozen benchmark bars use SPY close-to-close prices around the NIKE event: $538.15 on June 27, 2024 and $536.03 on June 28, 2024, making NIKE underperform the broad-market benchmark on the event day.

Contradicting evidence:
- None after replay filtering.

Score components:
- evidence_strength: 0.66
- mechanism_specificity: 0.62
- source_independence: 0.64
- cross_sectional_fit: 0.56
- contradiction_resistance: 0.60
- timestamp_advantage: 0.84
- forward_observable_quality: 0.62
- crowding_risk: 0.50
- unsupported_claim_penalty: 0.10

## #4: Margin and EPS resilience

A competing interpretation was that investors could look past the sales outlook because fourth-quarter EPS and gross margin were resilient.

Mechanism: Gross margin and EPS evidence supported operational resilience, but the large negative price reaction and guidance reset contradicted a margin-led explanation for the abnormal move.

Expected observables:
- Follow-up discussion should emphasize margin expansion and EPS resilience over demand weakness.
- The stock reaction should be less negative if margin resilience dominates investor interpretation.
- The narrative should weaken if later results show revenue declines despite margin progress.

Supporting evidence:
- `NKE-NASDAQ-001` (company_release): Nasdaq carried the Business Wire version of NIKE fiscal 2024 fourth-quarter results at 4:15 p.m. EDT, including the revenue decline, NIKE Direct decline, gross-margin increase, EPS result, and management comments about updating fiscal 2025 outlook.

Contradicting evidence:
- `NKE-IR-001` (company_release): NIKE reported fiscal 2024 fourth-quarter revenue of $12.6 billion, down 2% reported, NIKE Direct revenue down 8% reported, gross margin up 110 basis points to 44.7%, diluted EPS of $0.99, and management said fourth-quarter challenges led it to update the fiscal 2025 outlook.
- `NKE-INVEST-001` (news): Investopedia reported after the release that NIKE revenue missed analyst estimates, the company said results drove it to update fiscal 2025 guidance, and shares fell in extended trading despite net income and EPS coming in above year-earlier levels and estimates.
- `NKE-INVEST-002` (news): Investopedia reported before the market open on June 28, 2024 that NIKE shares were down about 15% premarket after lower-than-expected quarterly revenue and lowered fiscal 2025 sales guidance, including management commentary that first-quarter revenue was expected to decline approximately 10%.
- `NKE-MB-001` (transcript): The MarketBeat/Quartr earnings transcript recorded CFO Matthew Friend saying NIKE expected fiscal 2025 reported revenue to be down mid-single digits, the first half down high single digits, and first-quarter revenue down approximately 10%, citing classic footwear franchise management, digital challenges, muted wholesale order books, and a softer Greater China outlook.
- `NKE-MKT-001` (market_data): Frozen market bars use NIKE close-to-close prices around the event: $90.52 on June 27, 2024 and $72.44 on June 28, 2024, implying a -19.97% event move before peer adjustment.

Score components:
- evidence_strength: 0.58
- mechanism_specificity: 0.54
- source_independence: 0.54
- cross_sectional_fit: 0.36
- contradiction_resistance: 0.40
- timestamp_advantage: 0.82
- forward_observable_quality: 0.50
- crowding_risk: 0.34
- unsupported_claim_penalty: 0.14

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
- Validated narrative IDs: NARR-NKE-001
- Validated narrative rank: #1
- Narrative Recall@3: pass
- Replay rank #1 validated: pass
- Average unsupported claim penalty: 0.09
- Max unsupported claim penalty: 0.14
- High unsupported-claim penalty narratives: 2
- Blocked future source count: 1

## Model Comparison

| System | Selected Narrative | Rank | Validated | Selection Rule |
| --- | --- | ---: | --- | --- |
| headline_baseline | NARR-NKE-003 | #3 | miss | Selects the most crowded allowed narrative as a proxy for surface consensus. |
| evidence_only | NARR-NKE-001 | #1 | pass | Ablation that selects the strongest evidence score without mechanism or contradiction terms. |
| no_contradiction_penalty | NARR-NKE-001 | #1 | pass | Ablation that reranks without contradiction resistance or unsupported-claim penalty. |
| quality_weighted | NARR-NKE-001 | #1 | pass | Ablation that selects the strongest evidence score weighted by allowed source quality. |
| narrativedesk_tournament | NARR-NKE-001 | #1 | pass | Selects the highest deterministic narrative score after replay filtering. |

## Future Validation Fixture

Validation data is shown separately from event-time evidence so it cannot leak into generation.
- Note: Real-curated validation fixture. Held-out future evidence stays separate from event-time replay inputs.
- Future validation source IDs: NKE-IR-FUT-001

| Window | Label | Expected Observable | Future Sources | Validation Outcome |
| --- | --- | --- | --- | --- |
| T+60 | validated | Later reported results should show revenue pressure extending beyond the fourth-quarter release. | NKE-IR-FUT-001 | Held-out Q1 fiscal 2025 results reported revenue down 10% reported and NIKE Direct revenue down 13%, supporting the replay-time fiscal 2025 demand reset narrative. |
| T+60 | pending | Future results should keep NIKE Direct and digital revenue declines central. | NKE-IR-FUT-001 | Held-out Q1 results showed NIKE Direct revenue down 13%, but the public validation label remains pending because the broader demand reset better explains the event-time move. |
| T+60 | pending | Future commentary should cite Greater China or macro uncertainty as the main driver. | NKE-IR-FUT-001 | Pending separate curation of the geographic and macro contribution; held-out Q1 results showed declines across geographies but the replay winner was broader. |
| T+60 | invalidated | Follow-up discussion should emphasize margin expansion and EPS resilience over demand weakness. | NKE-IR-FUT-001 | Held-out Q1 results still showed gross-margin improvement, but revenue, Direct, wholesale, and EPS declined, weakening a margin-led explanation for the original selloff. |
