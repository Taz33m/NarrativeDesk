# AGENTS.md

Guidance for future Codex runs in this repo.

NarrativeDesk public artifact hierarchy is:

1. Working browser product
2. Strong README
3. Tests and evaluation checks
4. Clean repo shape

Do not create public doc sprawl. Public Markdown should usually be limited to `README.md`, this `AGENTS.md`, and generated examples such as `examples/sample_report.md` when linked from README. Put planning notes, agent outputs, and build scratch in `.codex-work/`; that directory must remain gitignored.

Do not make real financial claims without timestamped citations and source provenance. The v0 demo uses synthetic ORION data on purpose. Do not silently replace it with real tickers or real company claims.

Do not position NarrativeDesk as investment advice, a stock picker, a trading bot, or an automated advisor. Use research/education framing and keep uncertainty visible.

Use deterministic code for returns, replay filtering, scoring, validation windows, report export, and ledger export. AI can be added later as an optional layer, but it must be grounded in real state and should produce structured objects, not uncited prose.

The replay timestamp lock is a product feature. Preserve tests that prove future-dated sources are blocked. Do not expose future validation data through event-time replay endpoints.

Browser QA is required before release. If a frontend is changed, run the build and smoke the actual browser surface when feasible.

README must be concise and public-ready. It should explain what works, how to run it, what is synthetic, what is deterministic, what is future work, and what the limitations are. Do not overclaim model performance.

Prefer one polished workbench over many half-built pages. Avoid generic AI SaaS patterns, chat-first UI, fake live data, and meaningless metrics.
