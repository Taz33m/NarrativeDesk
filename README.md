# NarrativeDesk

NarrativeDesk is a research platform for verifying generated market narratives behind abnormal equity moves.

It is not the AI that tells people what to think about a stock. It is the audit layer that asks, given incomplete, noisy, time-bounded information, whether a generated explanation was sourced correctly, timestamp-valid, non-leaky, contradiction-aware, historically comparable, and eventually validated or falsified.

## What the app does

The v0.2 demo is a synthetic multi-case historical replay and verification infrastructure. ORION remains the default synthetic case, AURORA adds a provenance-ready guidance-miss replay, and LYRA adds a hard case where the later-validated narrative ranks #2 instead of #1. A fictional streaming company, ORION, sells off after earnings. The surface-level explanation is margin disappointment, but NarrativeDesk audits forward demand slowdown as the replay rank #1 after scoring mechanism specificity, evidence strength, source independence, contradictions, crowding risk, and forward observables.

The browser workbench shows:

- Event header with abnormal move, peer move, sector move, volume spike, and leakage lock timestamp.
- Synthetic case-index summary with aggregate Recall@3 and baseline comparison rates.
- Historical analogs showing how similar narrative structures validated or missed in other replay cases.
- Narrative verification bracket with ranked competing explanations.
- Evidence and contradiction inspector with source timestamps.
- Replay audit showing allowed sources and blocked future sources.
- Citation QA panel for replay filtering, support coverage, and provenance gaps.
- Source reliability panel with quality, independence, originality, and blocked-source breakdowns.
- Source clustering panel with deterministic originality clusters from replay-safe evidence.
- Deterministic research trail for the current fixture.
- Future validation panel kept separate from event-time replay evidence.
- Export links for ledger JSON and report Markdown.

The demo data is synthetic by design. Real-curated cases require timestamped source packs with source provenance metadata and replay-lock validation. Do not treat ORION, AURORA, or LYRA as real companies or real investment cases.

## Demo loop

1. Open the ORION replay workbench.
2. Read the event strip: the stock is down 11.4 percent, with a -10.2 percent abnormal move.
3. Check the replay lock: the event-time system is locked at `2025-08-07T10:00:00-04:00`.
4. Inspect the audit: future source `SRC-009` is quarantined and removed from `NARR-001`.
5. Compare the verification bracket: forward demand slowdown ranks above margin compression.
6. Open the evidence inspector: margin compression has headline support but a direct contradiction.
7. Read expected observables: each narrative makes falsifiable future claims.
8. Compare historical analogs: similar demand-slowdown narratives validated in other synthetic replay cases.
9. Reveal validation: T+20 later supports replay rank #1 in the synthetic replay.
10. Export the Markdown report or ledger JSON.

## Why anti-leakage matters

Historical market research can accidentally use information that was not available at the replay timestamp. That makes a system look smarter than it was.

NarrativeDesk treats the replay lock as a first-class constraint. Event-time replay filters out future-dated sources before scoring and ranking. Future validation is loaded separately and clearly labeled as after-the-fact.

## Architecture summary

The repo keeps the deterministic research kernel separate from the product surface.

- `src/narrativedesk/`: typed ledger models, replay filtering, scoring, validation helpers, pipeline, CLI, and report export.
- `apps/api/`: FastAPI service exposing event ID based endpoints around the kernel.
- `apps/web/`: Vite React workbench that renders kernel-generated demo artifacts.
- `data/fixtures/`: synthetic event and validation fixtures.
- `schemas/`: Narrative Ledger, Source Pack, Real Case Config, Validation Fixture, and Replay Bundle Manifest JSON schemas.
- `tests/`: unit and API tests.

The browser demo reads generated JSON from `apps/web/public/demo/`. Generate those artifacts from the Python kernel with `make web-data`. Replay bundles stay separate from future validation and evaluation bundles.

The generated example report lives at [`examples/sample_report.md`](examples/sample_report.md).

## Deterministic vs future AI/data work

Implemented deterministically:

- Typed Narrative Ledger object.
- Event return, abnormal return, peer median return, sector return, and volume ratio from raw fixture bars.
- Replay-lock checks requiring market snapshot `timestamp` or `as_of` fields.
- Replay timestamp filtering.
- Narrative scoring, ranking, and audit checks.
- Historical analog selection from replay-safe narrative text, mechanism, event type, direction, and held-out validation labels.
- Evaluation checks for Narrative Recall@3, replay rank #1 validation, unsupported-claim penalty, and blocked future sources.
- Deterministic headline-baseline versus NarrativeDesk verification comparison.
- Deterministic ablation comparisons for evidence-only, no-contradiction-penalty, and quality-weighted selection.
- Citation QA checks for replay leakage, support coverage, provenance gaps, and low-quality evidence.
- Source reliability summaries by publisher and source type.
- Deterministic source clustering and derived originality scoring from replay-safe evidence.
- Source-pack registration with fixture integrity and real-curated content-hash checks.
- Real-data source-pack builder for Finnhub candles/news, frozen price CSVs, SEC EDGAR submissions/facts, local transcripts, and frozen estimate revisions.
- Ledger JSON export.
- Markdown report export.
- Synthetic validation display.
- API endpoints for event, replay, ledger, report, and validation.

Future work:

- Provider adapters for transcript services, timestamped estimates, and analyst revisions.
- Optional AI agents for source-grounded hypothesis generation and contradiction generation; model output is never evidence by itself.
- Citation QA over larger real timestamped document sets.
- Multi-model arena and benchmark dataset.

## Run

Install JavaScript dependencies from the repo root:

```bash
npm ci
```

Generate demo artifacts:

```bash
npm run web:data
```

Preview and validate the synthetic source-pack example:

```bash
PYTHONPATH=src python3 -m narrativedesk.cli source-pack-preview examples/source_pack_template.json
```

Assess whether a source pack is ready to ingest:

```bash
PYTHONPATH=src python3 -m narrativedesk.cli source-pack-readiness .codex-work/real_source_pack.json
```

Create a self-contained replay bundle from a ready source pack:

```bash
PYTHONPATH=src python3 -m narrativedesk.cli source-pack-bundle .codex-work/real_source_pack.json --out-dir .codex-work/real_case_bundle
```

Bundles include `manifest.json` with artifact hashes and replay-integrity metadata.

Verify a replay bundle before sharing or registering it:

```bash
PYTHONPATH=src python3 -m narrativedesk.cli bundle-verify .codex-work/real_case_bundle
```

Build a real-curated source pack from provider data:

```bash
PYTHONPATH=src python3 -m narrativedesk.cli real-pack-build \
  .codex-work/real_case_config.json \
  --out .codex-work/real_source_pack.json \
  --env-file .env.local
```

Or build and bundle in one step:

```bash
PYTHONPATH=src python3 -m narrativedesk.cli real-pack-bundle \
  .codex-work/real_case_config.json \
  --out-dir .codex-work/real_case_bundle \
  --env-file .env.local
```

Start from `examples/real_case_config_template.json`, fill in a real ticker, event timestamp, peers, and curated narratives, then keep the working config in `.codex-work/`.

To rehearse live-provider ingestion without committing real claims, fetch raw provider data into scratch space, normalize it into strict source candidates, then draft a curator-ready config:

```bash
npm run real-case:aapl:preflight
npm run real-case:aapl:rehearse
```

Those scripts wrap the explicit CLI sequence below:

```bash
PYTHONPATH=src python3 -m narrativedesk.cli real-data-env-check --providers finnhub,sec --env-file .env.local
PYTHONPATH=src python3 -m narrativedesk.cli real-case-preflight \
  --ticker AAPL --event-date 2024-05-02 \
  --providers finnhub,sec --env-file .env.local \
  --fetch-dir .codex-work/live-fetches/aapl-2024-q2 \
  --draft-dir .codex-work/real-cases/aapl-2024-q2-rehearsal
PYTHONPATH=src python3 -m narrativedesk.cli real-case-rehearse \
  --ticker AAPL --company-name "Apple Inc." \
  --event-type earnings --event-date 2024-05-02 \
  --from 2024-05-01 --to 2024-05-20 \
  --replay-lock 2024-05-03T10:00:00-04:00 \
  --providers finnhub,sec --include-sec-document-text \
  --env-file .env.local \
  --fetch-dir .codex-work/live-fetches/aapl-2024-q2 \
  --draft-dir .codex-work/real-cases/aapl-2024-q2-rehearsal
```

Live-provider rehearsal requires `FINNHUB_API_KEY` and `SEC_USER_AGENT`; `NEWS_API_KEY` is optional when using `--providers newsapi`. Outputs remain scratch until a human adds competing narratives, `real-pack-build --require-narratives` passes, and the final bundle verifies.

If you have a frozen, timestamped market CSV from another trusted local source, pass it during draft repair with `real-case-draft --market-bars path/to/market_bars.csv`; the file is copied into the scratch draft and still goes through the normal readiness and bundle checks.

Before using a frozen price file, inspect it against the case replay lock:

```bash
PYTHONPATH=src python3 -m narrativedesk.cli real-market-bars-check path/to/market_bars.csv \
  --ticker AAPL --replay-lock 2024-05-03T10:00:00-04:00
```

The rehearsal command also writes `curated_narratives.template.json`. After curation, apply a separate narrative JSON file without hand-editing source link arrays:

```bash
PYTHONPATH=src python3 -m narrativedesk.cli real-case-apply-narratives \
  --draft-dir .codex-work/real-cases/aapl-2024-q2-rehearsal \
  --narratives .codex-work/real-cases/aapl-2024-q2-rehearsal/curated_narratives.template.json
```

Each curated narrative can include `supporting_source_ids`, `contradicting_source_ids`, `future_supporting_source_ids`, and `future_contradicting_source_ids`; these helper fields are used to link sources and are omitted from the written config. Replace all `TBD` values and add source links before applying the template.

To apply curation, build a source pack, write a replay bundle, and verify it in one scratch step:

```bash
PYTHONPATH=src python3 -m narrativedesk.cli real-case-curated-bundle \
  --draft-dir .codex-work/real-cases/aapl-2024-q2-rehearsal \
  --narratives .codex-work/real-cases/aapl-2024-q2-rehearsal/curated_narratives.template.json \
  --out-dir .codex-work/real-cases/aapl-2024-q2-bundle
```

Check draft, curation, and bundle state at any point:

```bash
PYTHONPATH=src python3 -m narrativedesk.cli real-case-status \
  --draft-dir .codex-work/real-cases/aapl-2024-q2-rehearsal \
  --narratives .codex-work/real-cases/aapl-2024-q2-rehearsal/curated_narratives.template.json \
  --bundle-dir .codex-work/real-cases/aapl-2024-q2-bundle
```

Before promoting a private real bundle, run the quality gate. It checks for a real-curated pack, 3-5 competing narratives, enough replay-time sources, blocked future evidence, contradiction links, and bundle integrity:

```bash
PYTHONPATH=src python3 -m narrativedesk.cli real-case-quality \
  --bundle-dir .codex-work/real-cases/aapl-2024-q2-bundle
```

Inspect local prior-art repos for timestamped manual-source candidates:

```bash
PYTHONPATH=src python3 scripts/inspect_prior_art.py --repo-root citadail=/path/to/citadail --repo-root mktmind-qtm=/path/to/mktmind-qtm --repo-root applecapital=/path/to/applecapital
```

Extract scratch sector market bars from the local MarketMind prior-art dataset:

```bash
PYTHONPATH=src python3 scripts/extract_prior_art_market_bars.py --tickers XLK --from 2024-05-01 --to 2024-05-07
```

Check a real-curated config before fetching provider data:

```bash
PYTHONPATH=src python3 -m narrativedesk.cli real-pack-check .codex-work/real_case_config.json --check-files
```

The real-data builder currently supports:

- Finnhub `stock/candle` for replay-safe event, peer, and sector bars.
- Local frozen CSV price files for replay-safe event, peer, and sector bars.
- Finnhub `company-news` for timestamped company news sources.
- SEC EDGAR `company_tickers`, submissions JSON, and optional filing document text.
- SEC EDGAR XBRL `companyfacts` for reported fundamental facts.
- Local transcript text files for source-backed earnings-call evidence.
- Frozen CSV estimate revisions for replay-time and future validation evidence.

Real-data configs are intentionally curator-led. Provide `case_metadata`, optional `market_data`, optional `news`, optional `sec_filings`, optional `sec_facts`, optional `transcripts`, optional `estimate_revisions`, optional `manual_sources`, and optional `narratives`. Run `real-pack-build` first, inspect the generated source pack, then add or curate narrative links before `source-pack-ingest`, which requires ingestion-ready narratives. For intraday replay locks, use intraday candles; daily bars and date-only CSV rows are rejected for pre-close locks unless explicitly marked as post-close safe.

Convert a complete source pack into a replay fixture:

```bash
PYTHONPATH=src python3 -m narrativedesk.cli source-pack-ingest examples/source_pack_template.json --out .codex-work/event_fixture.json --validation-out .codex-work/validation_fixture.json
```

Validate the generated validation scaffold before registering it:

```bash
PYTHONPATH=src python3 -m narrativedesk.cli validation-validate .codex-work/validation_fixture.json
```

Register those generated fixtures in a case index:

```bash
PYTHONPATH=src python3 -m narrativedesk.cli case-index-register .codex-work/case_index_seed.json --event-fixture .codex-work/event_fixture.json --validation-fixture .codex-work/validation_fixture.json --label "EXMPL synthetic source-pack example" --out .codex-work/case_index.json
```

Validate a case index before evaluating it:

```bash
PYTHONPATH=src python3 -m narrativedesk.cli case-index-validate .codex-work/case_index.json
```

Run the no-network real-data workflow smoke:

```bash
npm run real-pack:smoke
```

Run the Python smoke export:

```bash
make smoke
```

Run deterministic evaluation checks across the synthetic case index:

```bash
make evaluate
```

Run the API locally after installing API dependencies:

```bash
python3 -m pip install -e '.[api]'
PYTHONPATH=src uvicorn apps.api.main:app --reload --port 8000
```

Run the browser workbench:

```bash
npm run web:dev
```

Build the browser workbench:

```bash
npm run web:build
```

## Test

Run kernel and API tests:

```bash
make test
```

Run a CLI smoke check:

```bash
make smoke
```

If frontend dependencies are installed, build the browser product:

```bash
npm run web:build
```

Run the browser smoke test:

```bash
npm run web:smoke
```

Run the release verification path, including real browser QA:

```bash
npm run verify:release
```

If the environment cannot launch a browser, run the static artifact smoke:

```bash
npm run web:smoke:static
```

## API endpoints

- `GET /health`
- `GET /api/events`
- `GET /api/evaluations`
- `GET /api/events/{event_id}`
- `POST /api/events/{event_id}/run`
- `GET /api/events/{event_id}/ledger`
- `GET /api/events/{event_id}/report`
- `GET /api/events/{event_id}/report?include_validation=true`
- `GET /api/events/{event_id}/validation`

Replay, ledger, and default report endpoints do not include future validation data.

## Limitations

- v0.2 defaults to synthetic fixtures; real-curated cases require timestamped source packs and explicit provenance metadata.
- Real-data builder output is not automatically an investment thesis; a human still curates source-to-narrative links and uncertainty.
- Scores are transparent heuristics, not learned truth labels.
- Validation rows are synthetic and separate from event-time replay.
- The browser demo is a single workbench, not a live terminal.
- No investment recommendations, brokerage integration, or real-money trading exist.

## Roadmap

1. Add real historical event fixtures with timestamped citations.
2. Add transcript, estimate-revision, and analyst-consensus adapters.
3. Add optional agent generation grounded in structured source packs, with every generated claim tied back to source IDs.
4. Expand case evaluation to T+5, T+20, and T+60 validation windows.
5. Build a 100-event benchmark for Validated Narrative Rank@3.

## Research positioning

NarrativeDesk is meant to test the layer before P&L: whether a generated market thesis is source-backed, replay-safe, contradicted, ranked against alternatives, and later validated or falsified.

## Disclaimer

NarrativeDesk is for research and education only. It is not investment advice, a trading system, a broker, or an automated investment adviser.
