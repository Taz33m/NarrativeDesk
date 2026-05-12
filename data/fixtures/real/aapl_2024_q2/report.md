# NarrativeDesk Event Report: AAPL

> Research support output. Not investment advice.

## Data Note

This report is generated from a real-curated replay bundle. Treat it as research support only; public use requires curator review of source URLs, publication timestamps, raw document hashes, and validation status.

## Event

- Event ID: `EVT-REAL-AAPL-2024-05-02`
- Company: Apple Inc. (`AAPL`)
- Timestamp lock: `2024-05-03T10:00:00-04:00`
- Event type: earnings/guidance
- Daily return: 7.9%
- Abnormal return: 7.9%
- Volume ratio: n/a
- Sector ETF return: 0.0%
- Peer median return: 0.0%

Real-curated Apple Q2 2024 earnings replay with timestamped citations, replay-locked evidence, and held-out validation. Research and education only; not investment advice.

## Replay Audit

- Allowed sources: MKT-AAPL-001, MKT-BENCH-001, PUB-MACRUMORS-001, PUB-NASDAQ-001, SEC-030, SEC-031, SEC-033
- Blocked future sources: SEC-027
- Removed from `NARR-AAPL-001`: SEC-027

## Source Map

| Source | Status | Type | Publisher | Narratives | Relations |
| --- | --- | --- | --- | --- | --- |
| MKT-AAPL-001 | allowed | market_data | Frozen market bars | NARR-AAPL-001 | support |
| MKT-BENCH-001 | allowed | market_data | Frozen market bars | NARR-AAPL-001, NARR-AAPL-003, NARR-AAPL-004 | support |
| PUB-MACRUMORS-001 | allowed | news | MacRumors | NARR-AAPL-001, NARR-AAPL-002, NARR-AAPL-003 | support |
| PUB-NASDAQ-001 | allowed | company_release | Nasdaq / Business Wire | NARR-AAPL-001, NARR-AAPL-002 | support |
| SEC-030 | allowed | filing | SEC EDGAR | NARR-AAPL-001, NARR-AAPL-002, NARR-AAPL-003, NARR-AAPL-004 | support |
| SEC-031 | allowed | filing | SEC EDGAR | NARR-AAPL-001 | support |
| SEC-033 | allowed | filing | SEC EDGAR | NARR-AAPL-001, NARR-AAPL-003, NARR-AAPL-004 | contradict, support |
| SEC-027 | blocked_future | filing | n/a | NARR-AAPL-001 | support |

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
- Blocked future sources: 1
- Average evidence quality: 0.73
- Average independence: 0.72
- Average originality score: 0.75
- Low-quality evidence sources: 0
- Blocked source IDs: SEC-027

| Publisher | Allowed | Blocked Future | Evidence Quality | Independence | Originality |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frozen market bars | 2 | 0 | 0.80 | 0.85 | 0.80 |
| MacRumors | 1 | 0 | 0.76 | 0.72 | 0.72 |
| Nasdaq / Business Wire | 1 | 0 | 0.82 | 0.55 | 0.82 |
| SEC EDGAR | 3 | 0 | 0.65 | 0.70 | 0.70 |
| unknown | 0 | 1 | n/a | n/a | n/a |

## Source Clustering

Clusters use replay-safe allowed evidence only. Future-dated source text stays quarantined.
- Allowed sources clustered: 7
- Blocked future sources excluded: 1
- Cluster count: 4
- Duplicate clusters: 2
- Average derived originality: 0.57

| Cluster | Basis | Sources | Publishers | Derived Originality | Representative Claim |
| --- | --- | --- | --- | ---: | --- |
| issuer-release-mirrors | independence_cluster_id | PUB-NASDAQ-001 | Nasdaq / Business Wire | 1.00 | Nasdaq / Business Wire published Apple's fiscal Q2 2024 results release at 4:30 PM EDT on May 2, 2024, including lower year-over-year revenue, an all-time Services revenue record, a March-quarter EPS record, a dividend increase, and authorization for up to $110 billion in additional share repurchases. |
| manual-sec-edgar | independence_cluster_id | SEC-030, SEC-031, SEC-033 | SEC EDGAR | 0.33 | Segment Operating Performance The following table shows net sales by reportable segment for the three- and six-month periods ended March 30, 2024 and April 1, 2023 (dollars in millions): Three Months Ended Six Months Ended March 30, 2024 April 1, 2023 Change March 30, 2024 April 1, 2023 Change Net sales by reportable segment: Americas $ 37,273 $ 37,784 (1) % $ 87,703 $ 87,062 1 % Europe 24,123 23,945 1 % 54,520 51,626 6 % Greater China 16,372 17,812 (8) % 37,191 41,717 (11) % Japan 6,262 7,176 (13) % 14,029 13,931 1 % Rest of Asia Pacific 6,723 8,119 (17) % 16,885 17,654 (4) % Total net sales $ 90,753 $ 94,836 (4) % $ 210,328 $ 211,990 (1) % Americas Americas net sales were relatively flat during the second quarter of 2024 compared to the second quarter of 2023, with lower net sales of iPhone and iPad offset by higher net sales of Services. Year-over-year Americas net sales were relatively flat during the first six months of 2024, with higher net sales of Services offset by lower net s |
| market-bars | independence_cluster_id | MKT-AAPL-001, MKT-BENCH-001 | Frozen market bars | 0.50 | AAPL frozen market bar: opened at 173.03, closed at 186.65, with volume unavailable on 2024-05-03T09:30:00-04:00. |
| technology-news | independence_cluster_id | PUB-MACRUMORS-001 | MacRumors | 1.00 | MacRumors reported shortly after Apple's Q2 2024 release that Services set an all-time quarterly record, iPhone revenue fell by more than $5 billion year over year, and Apple authorized an additional $110 billion for share repurchases. |

## Narrative Verification Ranking

| Rank | Narrative | Direction | Score | Horizon |
| ---: | --- | --- | ---: | --- |
| 1 | Capital return reset | bullish | 0.68 | 20 trading days |
| 2 | Services mix resilience | bullish | 0.66 | 20 trading days |
| 3 | Hardware demand pressure | bearish | 0.60 | 20 trading days |
| 4 | Greater China pressure | bearish | 0.58 | 20 trading days |

## #1: Capital return reset

Investors focused on Apple's capital return reset after the company disclosed a new authorization to repurchase up to $110 billion of common stock and raised the quarterly dividend.

Mechanism: A larger repurchase authorization and higher dividend can change the near-term equity story from reported revenue softness to capital-return support for per-share value.

Expected observables:
- Capital return should be prominent in near-term investor discussion.
- Per-share support should matter more than reported product revenue weakness if the buyback narrative dominates.
- Follow-up filings should preserve evidence of the newly authorized repurchase program.

Supporting evidence:
- `SEC-030` (filing): Segment Operating Performance The following table shows net sales by reportable segment for the three- and six-month periods ended March 30, 2024 and April 1, 2023 (dollars in millions): Three Months Ended Six Months Ended March 30, 2024 April 1, 2023 Change March 30, 2024 April 1, 2023 Change Net sales by reportable segment: Americas $ 37,273 $ 37,784 (1) % $ 87,703 $ 87,062 1 % Europe 24,123 23,945 1 % 54,520 51,626 6 % Greater China 16,372 17,812 (8) % 37,191 41,717 (11) % Japan 6,262 7,176 (13) % 14,029 13,931 1 % Rest of Asia Pacific 6,723 8,119 (17) % 16,885 17,654 (4) % Total net sales $ 90,753 $ 94,836 (4) % $ 210,328 $ 211,990 (1) % Americas Americas net sales were relatively flat during the second quarter of 2024 compared to the second quarter of 2023, with lower net sales of iPhone and iPad offset by higher net sales of Services. Year-over-year Americas net sales were relatively flat during the first six months of 2024, with higher net sales of Services offset by lower net s
- `SEC-031` (filing): Item 2.02 Results of Operations and Financial Condition. On May 2, 2024, Apple Inc. (“Apple”) issued a press release regarding Apple’s financial results for its second fiscal quarter ended March 30, 2024. A copy of Apple’s press release is attached hereto as Exhibit 99.1. The information contained in this Current Report shall not be deemed “filed” for purposes of Section 18 of the Securities Exchange Act of 1934, as amended (the “Exchange Act”), or incorporated by reference in any filing under the Securities Act of 1933, as amended, or the Exchange Act, except as shall be expressly set forth by specific reference in such a filing. Item 9.01 Financial Statements and Exhibits. (d) Exhibits. Exhibit Number Exhibit Description 99.1 Press release issued by Apple Inc. on May 2, 2024. 104 Inline XBRL for the cover page of this Current Report on Form 8-K. SIGNATURE Pursuant to the requirements of the Securities Exchange Act of 1934, the Registrant has duly caused this report to be signed on it
- `MKT-AAPL-001` (market_data): AAPL frozen market bar: opened at 173.03, closed at 186.65, with volume unavailable on 2024-05-03T09:30:00-04:00.
- `MKT-BENCH-001` (market_data): Frozen benchmark market bars showed daily returns of XLK 0.00%, XLC 0.00%, XLY 0.00%; benchmark median return was 0.00%.
- `PUB-MACRUMORS-001` (news): MacRumors reported shortly after Apple's Q2 2024 release that Services set an all-time quarterly record, iPhone revenue fell by more than $5 billion year over year, and Apple authorized an additional $110 billion for share repurchases.
- `PUB-NASDAQ-001` (company_release): Nasdaq / Business Wire published Apple's fiscal Q2 2024 results release at 4:30 PM EDT on May 2, 2024, including lower year-over-year revenue, an all-time Services revenue record, a March-quarter EPS record, a dividend increase, and authorization for up to $110 billion in additional share repurchases.

Contradicting evidence:
- `SEC-033` (filing): Segment Operating Performance The following table shows net sales by reportable segment for the three months ended December 30, 2023 and December 31, 2022 (dollars in millions): Three Months Ended December 30, 2023 December 31, 2022 Change Net sales by reportable segment: Americas $ 50,430 $ 49,278 2 % Europe 30,397 27,681 10 % Greater China 20,819 23,905 (13) % Japan 7,767 6,755 15 % Rest of Asia Pacific 10,162 9,535 7 % Total net sales $ 119,575 $ 117,154 2 % Americas Americas net sales increased 2% or $1.2 billion during the first quarter of 2024 compared to the same quarter in 2023 due primarily to higher net sales of Services and iPhone, partially offset by lower net sales of iPad. The strength in foreign currencies relative to the U.S. dollar had a net favorable year-over-year impact on Americas net sales during the first quarter of 2024. Europe Europe net sales increased 10% or $2.7 billion during the first quarter of 2024 compared to the same quarter in 2023 due primarily to hi

Score components:
- evidence_strength: 0.82
- mechanism_specificity: 0.84
- source_independence: 0.42
- cross_sectional_fit: 0.58
- contradiction_resistance: 0.70
- timestamp_advantage: 0.90
- forward_observable_quality: 0.70
- crowding_risk: 0.44
- unsupported_claim_penalty: 0.06

## #2: Services mix resilience

The quarter was interpreted through Services resilience: Services revenue grew while several product categories declined, giving investors a higher-margin offset to weaker hardware demand.

Mechanism: Services growth and mix can protect gross margin and earnings quality even when hardware categories decline.

Expected observables:
- Services should remain a central offset to hardware category declines.
- Gross margin resilience should matter in interpretation of the quarter.
- Future discussion should compare Services growth with product revenue softness.

Supporting evidence:
- `SEC-030` (filing): Segment Operating Performance The following table shows net sales by reportable segment for the three- and six-month periods ended March 30, 2024 and April 1, 2023 (dollars in millions): Three Months Ended Six Months Ended March 30, 2024 April 1, 2023 Change March 30, 2024 April 1, 2023 Change Net sales by reportable segment: Americas $ 37,273 $ 37,784 (1) % $ 87,703 $ 87,062 1 % Europe 24,123 23,945 1 % 54,520 51,626 6 % Greater China 16,372 17,812 (8) % 37,191 41,717 (11) % Japan 6,262 7,176 (13) % 14,029 13,931 1 % Rest of Asia Pacific 6,723 8,119 (17) % 16,885 17,654 (4) % Total net sales $ 90,753 $ 94,836 (4) % $ 210,328 $ 211,990 (1) % Americas Americas net sales were relatively flat during the second quarter of 2024 compared to the second quarter of 2023, with lower net sales of iPhone and iPad offset by higher net sales of Services. Year-over-year Americas net sales were relatively flat during the first six months of 2024, with higher net sales of Services offset by lower net s
- `PUB-MACRUMORS-001` (news): MacRumors reported shortly after Apple's Q2 2024 release that Services set an all-time quarterly record, iPhone revenue fell by more than $5 billion year over year, and Apple authorized an additional $110 billion for share repurchases.
- `PUB-NASDAQ-001` (company_release): Nasdaq / Business Wire published Apple's fiscal Q2 2024 results release at 4:30 PM EDT on May 2, 2024, including lower year-over-year revenue, an all-time Services revenue record, a March-quarter EPS record, a dividend increase, and authorization for up to $110 billion in additional share repurchases.

Contradicting evidence:
- None after replay filtering.

Score components:
- evidence_strength: 0.78
- mechanism_specificity: 0.80
- source_independence: 0.48
- cross_sectional_fit: 0.55
- contradiction_resistance: 0.66
- timestamp_advantage: 0.86
- forward_observable_quality: 0.68
- crowding_risk: 0.50
- unsupported_claim_penalty: 0.08

## #3: Hardware demand pressure

The event exposed hardware demand weakness: iPhone, iPad, and Wearables revenue declined year over year while total net sales fell.

Mechanism: Broad product-category declines can signal weaker hardware demand and pressure the durability of future revenue growth.

Expected observables:
- Hardware-focused analysis should emphasize iPhone, iPad, and Wearables declines.
- If this narrative dominates, later commentary should focus on unit demand or product-cycle weakness.
- Capital return and Services growth would need to be treated as offsets rather than primary drivers.

Supporting evidence:
- `SEC-030` (filing): Segment Operating Performance The following table shows net sales by reportable segment for the three- and six-month periods ended March 30, 2024 and April 1, 2023 (dollars in millions): Three Months Ended Six Months Ended March 30, 2024 April 1, 2023 Change March 30, 2024 April 1, 2023 Change Net sales by reportable segment: Americas $ 37,273 $ 37,784 (1) % $ 87,703 $ 87,062 1 % Europe 24,123 23,945 1 % 54,520 51,626 6 % Greater China 16,372 17,812 (8) % 37,191 41,717 (11) % Japan 6,262 7,176 (13) % 14,029 13,931 1 % Rest of Asia Pacific 6,723 8,119 (17) % 16,885 17,654 (4) % Total net sales $ 90,753 $ 94,836 (4) % $ 210,328 $ 211,990 (1) % Americas Americas net sales were relatively flat during the second quarter of 2024 compared to the second quarter of 2023, with lower net sales of iPhone and iPad offset by higher net sales of Services. Year-over-year Americas net sales were relatively flat during the first six months of 2024, with higher net sales of Services offset by lower net s
- `SEC-033` (filing): Segment Operating Performance The following table shows net sales by reportable segment for the three months ended December 30, 2023 and December 31, 2022 (dollars in millions): Three Months Ended December 30, 2023 December 31, 2022 Change Net sales by reportable segment: Americas $ 50,430 $ 49,278 2 % Europe 30,397 27,681 10 % Greater China 20,819 23,905 (13) % Japan 7,767 6,755 15 % Rest of Asia Pacific 10,162 9,535 7 % Total net sales $ 119,575 $ 117,154 2 % Americas Americas net sales increased 2% or $1.2 billion during the first quarter of 2024 compared to the same quarter in 2023 due primarily to higher net sales of Services and iPhone, partially offset by lower net sales of iPad. The strength in foreign currencies relative to the U.S. dollar had a net favorable year-over-year impact on Americas net sales during the first quarter of 2024. Europe Europe net sales increased 10% or $2.7 billion during the first quarter of 2024 compared to the same quarter in 2023 due primarily to hi
- `MKT-BENCH-001` (market_data): Frozen benchmark market bars showed daily returns of XLK 0.00%, XLC 0.00%, XLY 0.00%; benchmark median return was 0.00%.
- `PUB-MACRUMORS-001` (news): MacRumors reported shortly after Apple's Q2 2024 release that Services set an all-time quarterly record, iPhone revenue fell by more than $5 billion year over year, and Apple authorized an additional $110 billion for share repurchases.

Contradicting evidence:
- None after replay filtering.

Score components:
- evidence_strength: 0.75
- mechanism_specificity: 0.73
- source_independence: 0.40
- cross_sectional_fit: 0.50
- contradiction_resistance: 0.52
- timestamp_advantage: 0.86
- forward_observable_quality: 0.62
- crowding_risk: 0.46
- unsupported_claim_penalty: 0.09

## #4: Greater China pressure

Investors were weighing regional pressure, especially Greater China, where reported net sales declined and iPhone represented a larger proportion of segment sales.

Mechanism: Weakness in Greater China can create a region-specific demand concern that investors may separate from company-wide category mix.

Expected observables:
- Greater China should remain a named risk if the regional narrative is correct.
- Later filings or commentary should show whether China weakness persists or stabilizes.
- The explanation should be weaker if non-China regions and Services carry the investment debate.

Supporting evidence:
- `SEC-030` (filing): Segment Operating Performance The following table shows net sales by reportable segment for the three- and six-month periods ended March 30, 2024 and April 1, 2023 (dollars in millions): Three Months Ended Six Months Ended March 30, 2024 April 1, 2023 Change March 30, 2024 April 1, 2023 Change Net sales by reportable segment: Americas $ 37,273 $ 37,784 (1) % $ 87,703 $ 87,062 1 % Europe 24,123 23,945 1 % 54,520 51,626 6 % Greater China 16,372 17,812 (8) % 37,191 41,717 (11) % Japan 6,262 7,176 (13) % 14,029 13,931 1 % Rest of Asia Pacific 6,723 8,119 (17) % 16,885 17,654 (4) % Total net sales $ 90,753 $ 94,836 (4) % $ 210,328 $ 211,990 (1) % Americas Americas net sales were relatively flat during the second quarter of 2024 compared to the second quarter of 2023, with lower net sales of iPhone and iPad offset by higher net sales of Services. Year-over-year Americas net sales were relatively flat during the first six months of 2024, with higher net sales of Services offset by lower net s
- `SEC-033` (filing): Segment Operating Performance The following table shows net sales by reportable segment for the three months ended December 30, 2023 and December 31, 2022 (dollars in millions): Three Months Ended December 30, 2023 December 31, 2022 Change Net sales by reportable segment: Americas $ 50,430 $ 49,278 2 % Europe 30,397 27,681 10 % Greater China 20,819 23,905 (13) % Japan 7,767 6,755 15 % Rest of Asia Pacific 10,162 9,535 7 % Total net sales $ 119,575 $ 117,154 2 % Americas Americas net sales increased 2% or $1.2 billion during the first quarter of 2024 compared to the same quarter in 2023 due primarily to higher net sales of Services and iPhone, partially offset by lower net sales of iPad. The strength in foreign currencies relative to the U.S. dollar had a net favorable year-over-year impact on Americas net sales during the first quarter of 2024. Europe Europe net sales increased 10% or $2.7 billion during the first quarter of 2024 compared to the same quarter in 2023 due primarily to hi
- `MKT-BENCH-001` (market_data): Frozen benchmark market bars showed daily returns of XLK 0.00%, XLC 0.00%, XLY 0.00%; benchmark median return was 0.00%.

Contradicting evidence:
- None after replay filtering.

Score components:
- evidence_strength: 0.69
- mechanism_specificity: 0.68
- source_independence: 0.42
- cross_sectional_fit: 0.48
- contradiction_resistance: 0.50
- timestamp_advantage: 0.84
- forward_observable_quality: 0.60
- crowding_risk: 0.44
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

## Evaluation Checks

These deterministic checks use the ranked replay output plus separately loaded validation rows.
- Validated narrative IDs: NARR-AAPL-001
- Validated narrative rank: #1
- Narrative Recall@3: pass
- Replay rank #1 validated: pass
- Average unsupported claim penalty: 0.08
- Max unsupported claim penalty: 0.10
- High unsupported-claim penalty narratives: 1
- Blocked future source count: 1

## Model Comparison

| System | Selected Narrative | Rank | Validated | Selection Rule |
| --- | --- | ---: | --- | --- |
| headline_baseline | NARR-AAPL-002 | #2 | miss | Selects the most crowded allowed narrative as a proxy for surface consensus. |
| evidence_only | NARR-AAPL-001 | #1 | pass | Ablation that selects the strongest evidence score without mechanism or contradiction terms. |
| no_contradiction_penalty | NARR-AAPL-001 | #1 | pass | Ablation that reranks without contradiction resistance or unsupported-claim penalty. |
| quality_weighted | NARR-AAPL-001 | #1 | pass | Ablation that selects the strongest evidence score weighted by allowed source quality. |
| narrativedesk_tournament | NARR-AAPL-001 | #1 | pass | Selects the highest deterministic narrative score after replay filtering. |

## Future Validation Fixture

Validation data is shown separately from event-time evidence so it cannot leak into generation.
- Note: Real-curated validation fixture. Held-out future evidence stays separate from event-time replay inputs.
- Future validation source IDs: SEC-027

| Window | Label | Expected Observable | Future Sources | Validation Outcome |
| --- | --- | --- | --- | --- |
| T+20 | pending | Capital return should be prominent in near-term investor discussion. | SEC-027 | Pending future validation; fill only after the validation window closes. |
| T+20 | pending | Per-share support should matter more than reported product revenue weakness if the buyback narrative dominates. | SEC-027 | Pending future validation; fill only after the validation window closes. |
| T+60 | validated | Follow-up filings should preserve evidence of the newly authorized repurchase program. | SEC-027 | Held-out SEC-027, Apple's Q3 2024 Form 10-Q filed after the replay lock, preserved the May 2, 2024 additional $110 billion share repurchase authorization disclosure. |
| T+20 | pending | Services should remain a central offset to hardware category declines. | none | Pending future validation; fill only after the validation window closes. |
| T+20 | pending | Gross margin resilience should matter in interpretation of the quarter. | none | Pending future validation; fill only after the validation window closes. |
| T+20 | pending | Future discussion should compare Services growth with product revenue softness. | none | Pending future validation; fill only after the validation window closes. |
| T+20 | pending | Hardware-focused analysis should emphasize iPhone, iPad, and Wearables declines. | none | Pending future validation; fill only after the validation window closes. |
| T+20 | pending | If this narrative dominates, later commentary should focus on unit demand or product-cycle weakness. | none | Pending future validation; fill only after the validation window closes. |
| T+20 | pending | Capital return and Services growth would need to be treated as offsets rather than primary drivers. | none | Pending future validation; fill only after the validation window closes. |
| T+20 | pending | Greater China should remain a named risk if the regional narrative is correct. | none | Pending future validation; fill only after the validation window closes. |
| T+20 | pending | Later filings or commentary should show whether China weakness persists or stabilizes. | none | Pending future validation; fill only after the validation window closes. |
| T+20 | pending | The explanation should be weaker if non-China regions and Services carry the investment debate. | none | Pending future validation; fill only after the validation window closes. |
