# NarrativeDesk

NarrativeDesk is a research platform for evaluating competing market narratives behind abnormal equity moves.

It does not ask only whether a stock should be bought or sold. It asks which explanations are circulating, which are evidence-backed, which are crowded or contradicted, and which later prove validated or wrong.

## What the app does

The v0 demo is a synthetic historical replay. A fictional streaming company, ORION, sells off after earnings. The surface-level explanation is margin disappointment, but NarrativeDesk ranks forward demand slowdown higher after scoring mechanism specificity, evidence strength, source independence, contradictions, crowding risk, and forward observables.

The browser workbench shows:

- Event header with abnormal move, peer move, sector move, volume spike, and leakage lock timestamp.
- Narrative Tournament with ranked competing explanations.
- Evidence and contradiction inspector with source timestamps.
- Replay audit showing allowed sources and blocked future sources.
- Deterministic research trail for the current fixture.
- Future validation panel kept separate from event-time replay evidence.
- Export links for ledger JSON and report Markdown.

The demo data is synthetic by design. Do not treat ORION as a real company or a real investment case.

## Demo loop

1. Open the ORION replay workbench.
2. Read the event strip: the stock is down 11.4 percent, with a -10.2 percent abnormal move.
3. Check the replay lock: the event-time system is locked at `2025-08-07T10:00:00-04:00`.
4. Inspect the audit: future source `SRC-009` is quarantined and removed from `NARR-001`.
5. Compare the tournament: forward demand slowdown ranks above margin compression.
6. Open the evidence inspector: margin compression has headline support but a direct contradiction.
7. Read expected observables: each narrative makes falsifiable future claims.
8. Reveal validation: T+20 later validates the top-ranked narrative in the synthetic replay.
9. Export the Markdown report or ledger JSON.

## Why anti-leakage matters

Historical market research can accidentally use information that was not available at the replay timestamp. That makes a system look smarter than it was.

NarrativeDesk treats the replay lock as a first-class constraint. Event-time replay filters out future-dated sources before scoring and ranking. Future validation is loaded separately and clearly labeled as after-the-fact.

## Architecture summary

The repo keeps the deterministic research kernel separate from the product surface.

- `src/narrativedesk/`: typed ledger models, replay filtering, scoring, validation helpers, pipeline, CLI, and report export.
- `apps/api/`: FastAPI service exposing event ID based endpoints around the kernel.
- `apps/web/`: Vite React workbench that renders kernel-generated demo artifacts.
- `data/fixtures/`: synthetic event and validation fixtures.
- `schemas/`: Narrative Ledger JSON schema.
- `tests/`: unit and API tests.

The browser demo reads generated JSON from `apps/web/public/demo/`. Generate those artifacts from the Python kernel with `make web-data`.

## Deterministic vs future AI/data work

Implemented deterministically:

- Typed Narrative Ledger object.
- Replay timestamp filtering.
- Narrative scoring and ranking.
- Ledger JSON export.
- Markdown report export.
- Synthetic validation display.
- API endpoints for event, replay, ledger, report, and validation.

Future work:

- Real SEC and transcript ingestion.
- Real price, peer, and volume calculations.
- Source clustering and originality scoring.
- Optional AI agents for hypothesis generation and contradiction generation.
- Citation QA over real timestamped documents.
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

Run the Python smoke export:

```bash
make smoke
```

Run the API locally after installing API dependencies:

```bash
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

If the environment cannot launch a browser, run the static artifact smoke:

```bash
npm run web:smoke:static
```

## API endpoints

- `GET /health`
- `GET /api/events`
- `GET /api/events/{event_id}`
- `POST /api/events/{event_id}/run`
- `GET /api/events/{event_id}/ledger`
- `GET /api/events/{event_id}/report`
- `GET /api/events/{event_id}/validation`

Replay and ledger endpoints do not include future validation data.

## Limitations

- v0 uses one synthetic fixture, not real market data.
- Scores are transparent heuristics, not learned truth labels.
- Validation rows are synthetic and separate from event-time replay.
- The browser demo is a single workbench, not a live terminal.
- No investment recommendations, brokerage integration, or real-money trading exist.

## Roadmap

1. Add real historical event fixtures with timestamped citations.
2. Add deterministic market data calculations for abnormal returns and peer context.
3. Add source ingestion and document hashing.
4. Add optional agent generation with citation QA and ablations.
5. Build a 100-event benchmark for Validated Narrative Rank@3.

## Research positioning

NarrativeDesk is meant to test the layer before P&L: whether a system identifies the right market thesis, supports it with evidence, ranks it against alternatives, and tracks whether the market later validates it.

## Disclaimer

NarrativeDesk is for research and education only. It is not investment advice, a trading system, a broker, or an automated investment adviser.
