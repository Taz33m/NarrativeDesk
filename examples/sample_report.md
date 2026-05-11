# NarrativeDesk Event Report: ORION

> Research support output. Not investment advice.

## Data Note

This sample report is generated from a synthetic fixture. Real event reports must include source URLs, publication timestamps, and raw document hashes.

## Event

- Event ID: `EVT-ORION-2025-08-07`
- Company: Orion Streaming Holdings (`ORION`)
- Timestamp lock: `2025-08-07T10:00:00-04:00`
- Event type: earnings/guidance
- Daily return: -11.4%
- Abnormal return: -10.2%
- Volume ratio: 2.40x
- Sector ETF return: -0.8%
- Peer median return: -1.2%

Synthetic demo event: a liquid streaming company sells off after earnings. The fixture is designed to exercise replay filtering, narrative verification, and validation separation.

## Replay Audit

- Allowed sources: SRC-001, SRC-002, SRC-003, SRC-004, SRC-005, SRC-006, SRC-007, SRC-008
- Blocked future sources: SRC-009
- Removed from `NARR-001`: SRC-009

## Source Map

| Source | Status | Type | Publisher | Narratives | Relations |
| --- | --- | --- | --- | --- | --- |
| SRC-001 | allowed | earnings_release | Orion Streaming Holdings | NARR-001 | support |
| SRC-002 | allowed | earnings_transcript | Orion Streaming Holdings | NARR-001, NARR-004 | contradict, support |
| SRC-003 | allowed | earnings_release | Orion Streaming Holdings | NARR-001 | contradict |
| SRC-004 | allowed | financial_media | Synthetic Market News | NARR-002 | support |
| SRC-005 | allowed | earnings_release | Orion Streaming Holdings | NARR-002 | contradict |
| SRC-006 | allowed | market_data | Synthetic Price Feed | NARR-003 | support |
| SRC-007 | allowed | market_data | Synthetic Price Feed | NARR-003 | contradict |
| SRC-008 | allowed | earnings_release | Orion Streaming Holdings | NARR-004 | support |
| SRC-009 | blocked_future | analyst_revision | n/a | NARR-001 | support |

## Citation QA

- Replay filter: pass
- Support coverage: pass
- Event-time integrity: pass
- Citation QA: miss
- Provenance-ready allowed sources: miss
- Returned blocked sources: 0
- Narratives with support: 4/4
- Missing URLs: 8
- Missing content hashes: 8
- Low-quality evidence sources: 1

## Source Reliability

Blocked future sources are counted for auditability but excluded from scoring and ranking.
- Allowed sources: 8
- Blocked future sources: 1
- Average evidence quality: 0.80
- Average independence: 0.82
- Average originality score: 0.50
- Low-quality evidence sources: 1
- Blocked source IDs: SRC-009

| Publisher | Allowed | Blocked Future | Evidence Quality | Independence | Originality |
| --- | ---: | ---: | ---: | ---: | ---: |
| Orion Streaming Holdings | 5 | 0 | 0.84 | 0.88 | 0.50 |
| Synthetic Market News | 1 | 0 | 0.45 | 0.38 | 0.50 |
| Synthetic Price Feed | 2 | 0 | 0.86 | 0.90 | 0.50 |
| unknown | 0 | 1 | n/a | n/a | n/a |

## Source Clustering

Clusters use replay-safe allowed evidence only. Future-dated source text stays quarantined.
- Allowed sources clustered: 8
- Blocked future sources excluded: 1
- Cluster count: 8
- Duplicate clusters: 0
- Average derived originality: 1.00

| Cluster | Basis | Sources | Publishers | Derived Originality | Representative Claim |
| --- | --- | --- | --- | ---: | --- |
| claim-0f01554a436c | claim_text_fingerprint | SRC-003 | Orion Streaming Holdings | 1.00 | Current-quarter revenue still exceeded consensus expectations. |
| claim-182dc277689d | claim_text_fingerprint | SRC-002 | Orion Streaming Holdings | 1.00 | Multiple analyst questions focused on churn, customer acquisition costs, and net additions. |
| claim-280d3ca6e07b | claim_text_fingerprint | SRC-005 | Orion Streaming Holdings | 1.00 | Gross margin improved year over year despite higher content spend. |
| claim-38006d17fd5a | claim_text_fingerprint | SRC-008 | Orion Streaming Holdings | 1.00 | Full-year free cash flow guidance was maintained despite lower near-term net additions. |
| claim-580edf61be2d | claim_text_fingerprint | SRC-001 | Orion Streaming Holdings | 1.00 | The company lowered next-quarter net addition guidance relative to prior management commentary. |
| claim-6bdb98326c41 | claim_text_fingerprint | SRC-007 | Synthetic Price Feed | 1.00 | Orion underperformed its peer median by roughly ten percentage points during the event window. |
| claim-772595a6ed95 | claim_text_fingerprint | SRC-006 | Synthetic Price Feed | 1.00 | The sector ETF was negative on the event morning. |
| claim-8a13cc3153f0 | claim_text_fingerprint | SRC-004 | Synthetic Market News | 1.00 | Early headlines framed the selloff around margin disappointment and rising content spend. |

## Narrative Verification Ranking

| Rank | Narrative | Direction | Score | Horizon |
| ---: | --- | --- | ---: | --- |
| 1 | Forward demand slowdown | bearish | 0.78 | 20 trading days |
| 2 | Overreaction to noisy guidance | bullish | 0.60 | 20 trading days |
| 3 | Sector-wide derating | mixed | 0.51 | 5 trading days |
| 4 | Margin compression | bearish | 0.51 | 5 trading days |

## #1: Forward demand slowdown

The selloff is primarily driven by concern that future subscriber and revenue growth are slowing, not by a one-time margin issue.

Mechanism: Lower expected subscriber growth would reduce forward revenue estimates and compress the valuation multiple for a growth-sensitive equity.

Expected observables:
- Analysts reduce forward revenue or subscriber estimates within 30 days
- The stock underperforms a peer basket over the next 20 trading days
- Future company commentary focuses on acquisition efficiency or churn

Supporting evidence:
- `SRC-001` (earnings_release): The company lowered next-quarter net addition guidance relative to prior management commentary.
- `SRC-002` (earnings_transcript): Multiple analyst questions focused on churn, customer acquisition costs, and net additions.

Contradicting evidence:
- `SRC-003` (earnings_release): Current-quarter revenue still exceeded consensus expectations.

Score components:
- evidence_strength: 0.84
- mechanism_specificity: 0.88
- source_independence: 0.75
- cross_sectional_fit: 0.76
- contradiction_resistance: 0.62
- timestamp_advantage: 0.82
- forward_observable_quality: 0.90
- crowding_risk: 0.31
- unsupported_claim_penalty: 0.03

## #2: Overreaction to noisy guidance

The market may be overreacting to conservative guidance that does not materially change long-term cash-flow power.

Mechanism: If the guidance reset is conservative and fundamentals stabilize, the initial selloff could reverse as investors reprice the event as temporary noise.

Expected observables:
- Revenue estimates stabilize after the first wave of revisions
- Management or channel data indicates demand is not deteriorating
- The stock recovers relative to peers after headline pressure fades

Supporting evidence:
- `SRC-008` (earnings_release): Full-year free cash flow guidance was maintained despite lower near-term net additions.

Contradicting evidence:
- `SRC-002` (earnings_transcript): Multiple analyst questions focused on churn, customer acquisition costs, and net additions.

Score components:
- evidence_strength: 0.52
- mechanism_specificity: 0.70
- source_independence: 0.66
- cross_sectional_fit: 0.48
- contradiction_resistance: 0.42
- timestamp_advantage: 0.78
- forward_observable_quality: 0.82
- crowding_risk: 0.22
- unsupported_claim_penalty: 0.06

## #3: Sector-wide derating

The move reflects a broader derating of streaming and internet media equities rather than a company-specific issue.

Mechanism: Higher discount rates or weaker risk appetite would compress multiples across the group, causing peer-correlated price action.

Expected observables:
- Peers and sector ETF experience comparable drawdowns
- Company-specific estimate revisions are limited
- Price action tracks macro or sector factors more than company disclosures

Supporting evidence:
- `SRC-006` (market_data): The sector ETF was negative on the event morning.

Contradicting evidence:
- `SRC-007` (market_data): Orion underperformed its peer median by roughly ten percentage points during the event window.

Score components:
- evidence_strength: 0.40
- mechanism_specificity: 0.67
- source_independence: 0.71
- cross_sectional_fit: 0.18
- contradiction_resistance: 0.28
- timestamp_advantage: 0.86
- forward_observable_quality: 0.55
- crowding_risk: 0.26
- unsupported_claim_penalty: 0.04

## #4: Margin compression

The stock moved because investors focused on near-term gross margin pressure from content spend and platform costs.

Mechanism: Lower margins would reduce near-term earnings and free cash flow, pressuring valuation if investors view the cost increase as recurring.

Expected observables:
- Near-term EPS estimates decline more than revenue estimates
- Management emphasizes cost control in follow-up commentary
- Peers with similar margin pressure also trade down

Supporting evidence:
- `SRC-004` (financial_media): Early headlines framed the selloff around margin disappointment and rising content spend.

Contradicting evidence:
- `SRC-005` (earnings_release): Gross margin improved year over year despite higher content spend.

Score components:
- evidence_strength: 0.54
- mechanism_specificity: 0.72
- source_independence: 0.42
- cross_sectional_fit: 0.39
- contradiction_resistance: 0.35
- timestamp_advantage: 0.76
- forward_observable_quality: 0.63
- crowding_risk: 0.58
- unsupported_claim_penalty: 0.10

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
