from __future__ import annotations

import argparse
import json
import os
from hashlib import sha256
from pathlib import Path
from typing import Any

from narrativedesk.case_index import register_case_index_entry, validate_case_index
from narrativedesk.evaluation import evaluate_replay, summarize_case_evaluations
from narrativedesk.pipeline import (
    ledger_export,
    load_case_index,
    load_validation_fixture,
    run_replay,
)
from narrativedesk.report import generate_markdown_report
from narrativedesk.real_data import (
    RealDataError,
    build_real_source_pack,
    load_real_case_config,
    preview_real_case_config,
    validate_real_case_config,
)
from narrativedesk.real_provenance import (
    RealProvenanceError,
    apply_curated_narratives,
    draft_real_case,
    fetch_real_data,
    inspect_market_bars,
    normalize_real_data_fetch,
    rehearse_real_case,
    validate_curated_narratives,
    write_curated_narratives_template,
    write_real_case_worksheet,
)
from narrativedesk.replay_bundle import verify_replay_bundle
from narrativedesk.source_pack import (
    assess_real_case_quality,
    assess_source_pack_readiness,
    build_fixture_from_source_pack,
    build_validation_fixture_template_from_source_pack,
    load_source_pack,
    preview_source_pack,
    sanitize_source_pack_payload,
    validate_source_pack,
)
from narrativedesk.source_discovery import (
    SourceDiscoveryError,
    discover_sources_with_sonar,
    freeze_discovery_candidates,
)
from narrativedesk.validation_fixture import (
    load_validation_fixture_payload,
    preview_validation_fixture,
    validate_validation_fixture,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run NarrativeDesk utilities.")
    sub = parser.add_subparsers(dest="command")

    replay = sub.add_parser("replay", help="Run a replay fixture.")
    replay.add_argument("fixture", help="Path to an event fixture JSON file.")
    replay.add_argument("--out", help="Write a markdown report to this path.")
    replay.add_argument("--ledger-out", help="Write the ranked ledger JSON to this path.")
    replay.add_argument("--validation", help="Optional future validation fixture for report export.")

    pack = sub.add_parser("source-pack-preview", help="Validate and preview a source pack.")
    pack.add_argument("path", help="Path to source pack JSON.")

    pack_readiness = sub.add_parser("source-pack-readiness", help="Assess whether a source pack is ready to ingest.")
    pack_readiness.add_argument("path", help="Path to source pack JSON.")

    real_quality = sub.add_parser(
        "real-case-quality",
        help="Assess whether a real-curated source pack or bundle clears the replay-case quality gate.",
    )
    real_quality_input = real_quality.add_mutually_exclusive_group(required=True)
    real_quality_input.add_argument("--source-pack", help="Path to source pack JSON.")
    real_quality_input.add_argument("--bundle-dir", help="Path to a generated replay bundle directory.")
    real_quality.add_argument("--min-narratives", type=int, default=3, help="Minimum competing narratives.")
    real_quality.add_argument("--max-narratives", type=int, default=5, help="Maximum focused competing narratives.")
    real_quality.add_argument("--min-allowed-sources", type=int, default=5, help="Minimum replay-time sources.")
    real_quality.add_argument(
        "--min-blocked-future-sources",
        type=int,
        default=1,
        help="Minimum future sources quarantined for validation.",
    )
    real_quality.add_argument(
        "--min-contradictions",
        type=int,
        default=1,
        help="Minimum replay-time contradiction links.",
    )
    real_quality.add_argument(
        "--require-demo-ready",
        action="store_true",
        help=(
            "Apply the stricter private-demo gate: peer-market context, linked evidence depth, "
            "source diversity, and at least one held-out validation outcome."
        ),
    )
    real_quality.add_argument(
        "--require-public-ready",
        action="store_true",
        help=(
            "Apply the public-promotion gate in addition to --require-demo-ready: "
            "requires non-SEC, non-market replay evidence and linked validation outcomes."
        ),
    )

    pack_bundle = sub.add_parser("source-pack-bundle", help="Create a self-contained replay bundle from a ready source pack.")
    pack_bundle.add_argument("path", help="Path to source pack JSON.")
    pack_bundle.add_argument("--out-dir", required=True, help="Directory for the generated replay bundle.")
    pack_bundle.add_argument("--label", help="Human-readable case label for the local case index.")
    pack_bundle.add_argument(
        "--validation-fixture",
        help="Optional curator-filled future validation fixture to include instead of a generated pending scaffold.",
    )

    bundle_verify = sub.add_parser("bundle-verify", help="Verify replay bundle hashes and replay integrity.")
    bundle_verify.add_argument("bundle_dir", help="Path to a generated replay bundle directory.")

    real_pack = sub.add_parser(
        "real-pack-build",
        help="Build a real-curated source pack from provider data and a curated case config.",
    )
    real_pack.add_argument("config", help="Path to real-data case config JSON.")
    real_pack.add_argument("--out", required=True, help="Write the generated source pack JSON to this path.")
    real_pack.add_argument(
        "--finnhub-token-env",
        default="FINNHUB_API_KEY",
        help="Environment variable containing the Finnhub API token.",
    )
    real_pack.add_argument(
        "--sec-user-agent-env",
        default="SEC_USER_AGENT",
        help="Environment variable containing the SEC EDGAR User-Agent header.",
    )
    real_pack.add_argument(
        "--env-file",
        help="Optional dotenv-style file with provider credentials. Environment variables override file values.",
    )
    real_pack.add_argument(
        "--retrieved-at",
        help="Optional ISO timestamp to stamp retrieved_at deterministically.",
    )
    real_pack.add_argument(
        "--require-narratives",
        action="store_true",
        help="Validate the generated source pack as ingestion-ready, not just preview-ready.",
    )

    real_bundle = sub.add_parser(
        "real-pack-bundle",
        help="Build a real-curated source pack from config and create a replay bundle.",
    )
    real_bundle.add_argument("config", help="Path to real-data case config JSON.")
    real_bundle.add_argument("--out-dir", required=True, help="Directory for the generated replay bundle.")
    real_bundle.add_argument(
        "--finnhub-token-env",
        default="FINNHUB_API_KEY",
        help="Environment variable containing the Finnhub API token.",
    )
    real_bundle.add_argument(
        "--sec-user-agent-env",
        default="SEC_USER_AGENT",
        help="Environment variable containing the SEC EDGAR User-Agent header.",
    )
    real_bundle.add_argument(
        "--env-file",
        help="Optional dotenv-style file with provider credentials. Environment variables override file values.",
    )
    real_bundle.add_argument(
        "--retrieved-at",
        help="Optional ISO timestamp to stamp retrieved_at deterministically.",
    )
    real_bundle.add_argument("--label", help="Human-readable case label for the local case index.")
    real_bundle.add_argument(
        "--validation-fixture",
        help="Optional curator-filled future validation fixture to include instead of a generated pending scaffold.",
    )

    real_check = sub.add_parser("real-pack-check", help="Validate a real-data case config without provider fetches.")
    real_check.add_argument("config", help="Path to real-data case config JSON.")
    real_check.add_argument(
        "--check-files",
        action="store_true",
        help="Also require local CSV/transcript paths referenced by the config to exist.",
    )

    real_fetch = sub.add_parser(
        "real-data-fetch",
        help="Fetch live provider data into frozen .codex-work raw artifacts.",
    )
    real_fetch.add_argument("--ticker", required=True, help="Ticker symbol to fetch.")
    real_fetch.add_argument("--company-name", default="", help="Company name for provider queries.")
    real_fetch.add_argument("--from", dest="date_from", required=True, help="Oldest provider date, YYYY-MM-DD.")
    real_fetch.add_argument("--to", dest="date_to", required=True, help="Newest provider date, YYYY-MM-DD.")
    real_fetch.add_argument(
        "--providers",
        default="finnhub,sec",
        help="Comma-separated provider list: finnhub,sec,newsapi.",
    )
    real_fetch.add_argument("--out-dir", help="Output directory. Defaults to .codex-work/live-fetches/<ticker>-<from>-<to>.")
    real_fetch.add_argument(
        "--finnhub-token-env",
        default="FINNHUB_API_KEY",
        help="Environment variable containing the Finnhub API token.",
    )
    real_fetch.add_argument(
        "--sec-user-agent-env",
        default="SEC_USER_AGENT",
        help="Environment variable containing the SEC EDGAR User-Agent header.",
    )
    real_fetch.add_argument(
        "--news-api-key-env",
        default="NEWS_API_KEY",
        help="Environment variable containing the NewsAPI token.",
    )
    real_fetch.add_argument(
        "--env-file",
        help="Optional dotenv-style file with provider credentials. Environment variables override file values.",
    )
    real_fetch.add_argument("--forms", default="8-K,10-Q,10-K", help="Comma-separated SEC forms to fetch.")
    real_fetch.add_argument("--sec-count", type=int, default=5, help="Maximum SEC filings to inspect.")
    real_fetch.add_argument("--cik", help="Optional SEC CIK override.")
    real_fetch.add_argument(
        "--market-symbols",
        help="Optional comma-separated extra symbols to freeze daily Finnhub candles for peer/sector context.",
    )
    real_fetch.add_argument(
        "--include-sec-document-text",
        action="store_true",
        help="Also fetch primary SEC filing document text for selected filings.",
    )
    real_fetch.add_argument("--news-query", help="Optional NewsAPI query override.")
    real_fetch.add_argument("--news-domains", help="Optional comma-separated NewsAPI domain filter.")

    real_env = sub.add_parser(
        "real-data-env-check",
        help="Check whether live-provider rehearsal environment variables are present without printing values.",
    )
    real_env.add_argument(
        "--providers",
        default="finnhub,sec",
        help="Comma-separated provider list: finnhub,sec,newsapi.",
    )
    real_env.add_argument(
        "--finnhub-token-env",
        default="FINNHUB_API_KEY",
        help="Environment variable containing the Finnhub API token.",
    )
    real_env.add_argument(
        "--sec-user-agent-env",
        default="SEC_USER_AGENT",
        help="Environment variable containing the SEC EDGAR User-Agent header.",
    )
    real_env.add_argument(
        "--news-api-key-env",
        default="NEWS_API_KEY",
        help="Environment variable containing the NewsAPI token.",
    )
    real_env.add_argument(
        "--env-file",
        help="Optional dotenv-style file with provider credentials. Environment variables override file values.",
    )

    real_preflight = sub.add_parser(
        "real-case-preflight",
        help="Check live-provider env names and scratch real-case paths without fetching data.",
    )
    real_preflight.add_argument("--ticker", required=True, help="Ticker symbol for the rehearsal.")
    real_preflight.add_argument("--event-date", required=True, help="Event date, YYYY-MM-DD.")
    real_preflight.add_argument(
        "--providers",
        default="finnhub,sec",
        help="Comma-separated provider list: finnhub,sec,newsapi.",
    )
    real_preflight.add_argument("--out-root", default=".codex-work", help="Scratch root for default output paths.")
    real_preflight.add_argument("--fetch-dir", help="Expected frozen fetch directory.")
    real_preflight.add_argument("--draft-dir", help="Expected real-case draft directory.")
    real_preflight.add_argument("--bundle-dir", help="Expected replay bundle directory.")
    real_preflight.add_argument("--narratives", help="Optional curated narratives JSON for status validation.")
    real_preflight.add_argument(
        "--finnhub-token-env",
        default="FINNHUB_API_KEY",
        help="Environment variable containing the Finnhub API token.",
    )
    real_preflight.add_argument(
        "--sec-user-agent-env",
        default="SEC_USER_AGENT",
        help="Environment variable containing the SEC EDGAR User-Agent header.",
    )
    real_preflight.add_argument(
        "--news-api-key-env",
        default="NEWS_API_KEY",
        help="Environment variable containing the NewsAPI token.",
    )
    real_preflight.add_argument(
        "--env-file",
        help="Optional dotenv-style file with provider credentials. Environment variables override file values.",
    )

    real_normalize = sub.add_parser(
        "real-data-normalize",
        help="Normalize a frozen live-fetch directory into source candidates.",
    )
    real_normalize.add_argument("fetch_dir", help="Directory containing fetch_manifest.json.")
    real_normalize.add_argument("--replay-lock", required=True, help="Replay lock timestamp with timezone.")
    real_normalize.add_argument("--out-dir", help="Optional normalized output directory.")

    real_source_discover = sub.add_parser(
        "real-source-discover",
        help="Use Perplexity Sonar as scratch-only source discovery; discovered text is not evidence.",
    )
    real_source_discover.add_argument("--ticker", required=True, help="Ticker symbol.")
    real_source_discover.add_argument("--company-name", required=True, help="Company name.")
    real_source_discover.add_argument("--event-date", required=True, help="Event date, YYYY-MM-DD.")
    real_source_discover.add_argument("--replay-lock", required=True, help="Replay lock timestamp with timezone.")
    real_source_discover.add_argument("--query", required=True, help="Public source-discovery query.")
    real_source_discover.add_argument(
        "--out-dir",
        help="Output directory. Defaults to .codex-work/source-discovery/<ticker>-<event-date>.",
    )
    real_source_discover.add_argument(
        "--perplexity-key-env",
        default="PERPLEXITY_API_KEY",
        help="Environment variable containing the Perplexity API token.",
    )
    real_source_discover.add_argument(
        "--perplexity-model-env",
        default="PERPLEXITY_MODEL",
        help="Optional environment variable containing the Sonar model name.",
    )
    real_source_discover.add_argument("--model", help="Optional Sonar model override. Defaults to PERPLEXITY_MODEL or sonar.")
    real_source_discover.add_argument(
        "--env-file",
        help="Optional dotenv-style file with provider credentials. Environment variables override file values.",
    )
    real_source_discover.add_argument("--search-domains", help="Optional comma-separated Sonar domain filter.")
    real_source_discover.add_argument("--search-before-date", help="Optional Sonar date filter, MM/DD/YYYY.")
    real_source_discover.add_argument("--search-after-date", help="Optional Sonar date filter, MM/DD/YYYY.")

    real_source_freeze = sub.add_parser(
        "real-source-freeze",
        help="Refetch discovered URLs and freeze verified pages into SourceCandidate artifacts.",
    )
    real_source_freeze.add_argument("--discovery-dir", required=True, help="Directory containing discovery_candidates.json.")
    real_source_freeze.add_argument("--replay-lock", required=True, help="Replay lock timestamp with timezone.")
    real_source_freeze.add_argument("--out-dir", help="Optional frozen output directory.")
    real_source_freeze.add_argument(
        "--normalized-dir",
        help="Optional existing real-data normalized directory to append frozen source candidates into.",
    )
    real_source_freeze.add_argument("--source-type", default="news", help="Source type for frozen pages, default news.")

    real_draft = sub.add_parser(
        "real-case-draft",
        help="Draft a curator-ready real_case_config from normalized candidates.",
    )
    real_draft.add_argument("--ticker", required=True, help="Ticker symbol.")
    real_draft.add_argument("--company-name", required=True, help="Company name.")
    real_draft.add_argument("--event-type", required=True, help="Event type label.")
    real_draft.add_argument("--event-date", required=True, help="Event date, YYYY-MM-DD.")
    real_draft.add_argument("--replay-lock", required=True, help="Replay lock timestamp with timezone.")
    real_draft.add_argument("--normalized-dir", required=True, help="Directory containing normalized outputs.")
    real_draft.add_argument("--out-dir", required=True, help="Output directory for the real-case draft.")
    real_draft.add_argument("--case-id", help="Optional case ID override.")
    real_draft.add_argument(
        "--market-bars",
        help="Optional frozen market_bars.csv override to copy into the draft before readiness checks.",
    )
    real_draft.add_argument("--market-peers", help="Optional comma-separated peer symbols required in market_bars.csv.")
    real_draft.add_argument("--sector-symbol", help="Optional sector or ETF symbol required in market_bars.csv.")

    market_bars_check = sub.add_parser(
        "real-market-bars-check",
        help="Check whether a frozen market_bars.csv has replay-eligible ticker rows.",
    )
    market_bars_check.add_argument("path", help="Path to market_bars.csv.")
    market_bars_check.add_argument("--ticker", required=True, help="Ticker symbol to require.")
    market_bars_check.add_argument("--replay-lock", required=True, help="Replay lock timestamp with timezone.")
    market_bars_check.add_argument("--peers", help="Optional comma-separated peer symbols to require.")
    market_bars_check.add_argument("--sector-symbol", help="Optional sector or ETF symbol to require.")

    real_worksheet = sub.add_parser(
        "real-case-worksheet",
        help="Write a scratch curation worksheet from a real-case draft directory.",
    )
    real_worksheet.add_argument("--draft-dir", required=True, help="Directory containing real_case_config.json and draft_summary.json.")
    real_worksheet.add_argument("--out", help="Optional worksheet output path. Defaults to <draft-dir>/curation_worksheet.md.")
    real_worksheet.add_argument("--allowed-limit", type=int, default=12, help="Maximum replay-eligible sources to render.")
    real_worksheet.add_argument("--blocked-limit", type=int, default=10, help="Maximum blocked future sources to render.")

    real_rehearsal = sub.add_parser(
        "real-case-rehearse",
        help="Run live fetch, normalization, draft config, and scratch worksheet in one deterministic pass.",
    )
    real_rehearsal.add_argument("--ticker", required=True, help="Ticker symbol to rehearse.")
    real_rehearsal.add_argument("--company-name", required=True, help="Company name for provider queries.")
    real_rehearsal.add_argument("--event-type", required=True, help="Event type label.")
    real_rehearsal.add_argument("--event-date", required=True, help="Event date, YYYY-MM-DD.")
    real_rehearsal.add_argument("--replay-lock", required=True, help="Replay lock timestamp with timezone.")
    real_rehearsal.add_argument("--from", dest="date_from", required=True, help="Oldest provider date, YYYY-MM-DD.")
    real_rehearsal.add_argument("--to", dest="date_to", required=True, help="Newest provider date, YYYY-MM-DD.")
    real_rehearsal.add_argument(
        "--providers",
        default="finnhub,sec",
        help="Comma-separated provider list: finnhub,sec,newsapi.",
    )
    real_rehearsal.add_argument("--out-root", default=".codex-work", help="Scratch root for default output paths.")
    real_rehearsal.add_argument("--fetch-dir", help="Output directory for frozen provider artifacts.")
    real_rehearsal.add_argument("--draft-dir", help="Output directory for the curator-ready draft.")
    real_rehearsal.add_argument(
        "--market-bars",
        help="Optional frozen market_bars.csv override to copy into the draft before readiness checks.",
    )
    real_rehearsal.add_argument(
        "--finnhub-token-env",
        default="FINNHUB_API_KEY",
        help="Environment variable containing the Finnhub API token.",
    )
    real_rehearsal.add_argument(
        "--sec-user-agent-env",
        default="SEC_USER_AGENT",
        help="Environment variable containing the SEC EDGAR User-Agent header.",
    )
    real_rehearsal.add_argument(
        "--news-api-key-env",
        default="NEWS_API_KEY",
        help="Environment variable containing the NewsAPI token.",
    )
    real_rehearsal.add_argument(
        "--env-file",
        help="Optional dotenv-style file with provider credentials. Environment variables override file values.",
    )
    real_rehearsal.add_argument("--forms", default="8-K,10-Q,10-K", help="Comma-separated SEC forms to fetch.")
    real_rehearsal.add_argument("--sec-count", type=int, default=5, help="Maximum SEC filings to inspect.")
    real_rehearsal.add_argument("--cik", help="Optional SEC CIK override.")
    real_rehearsal.add_argument("--market-peers", help="Optional comma-separated peer symbols to freeze and require.")
    real_rehearsal.add_argument("--sector-symbol", help="Optional sector or ETF symbol to freeze and require.")
    real_rehearsal.add_argument(
        "--include-sec-document-text",
        action="store_true",
        help="Also fetch primary SEC filing document text for selected filings.",
    )
    real_rehearsal.add_argument("--news-query", help="Optional NewsAPI query override.")
    real_rehearsal.add_argument("--news-domains", help="Optional comma-separated NewsAPI domain filter.")
    real_rehearsal.add_argument(
        "--no-worksheet",
        action="store_true",
        help="Skip writing the scratch curation worksheet.",
    )
    real_rehearsal.add_argument(
        "--no-curation-template",
        action="store_true",
        help="Skip writing the scratch curated_narratives.template.json file.",
    )
    real_rehearsal.add_argument("--allowed-limit", type=int, default=12, help="Maximum replay-eligible sources to render.")
    real_rehearsal.add_argument("--blocked-limit", type=int, default=10, help="Maximum blocked future sources to render.")
    real_rehearsal.add_argument("--template-narrative-count", type=int, default=5, help="Number of narrative template slots to write.")

    real_apply_narratives = sub.add_parser(
        "real-case-apply-narratives",
        help="Apply human-curated narratives and source links to a real-case draft config.",
    )
    real_apply_narratives.add_argument("--draft-dir", required=True, help="Directory containing real_case_config.json.")
    real_apply_narratives.add_argument(
        "--narratives",
        required=True,
        help="JSON file containing a list or {narratives: [...]} with curated narrative records.",
    )
    real_apply_narratives.add_argument(
        "--out",
        help="Output config path. Defaults to <draft-dir>/real_case_config.curated.json.",
    )

    real_narrative_template = sub.add_parser(
        "real-case-curation-template",
        help="Write a scratch curated_narratives.template.json file from a real-case draft.",
    )
    real_narrative_template.add_argument("--draft-dir", required=True, help="Directory containing real_case_config.json.")
    real_narrative_template.add_argument(
        "--out",
        help="Optional template output path. Defaults to <draft-dir>/curated_narratives.template.json.",
    )
    real_narrative_template.add_argument("--narrative-count", type=int, default=5, help="Number of narrative slots to write.")
    real_narrative_template.add_argument("--allowed-limit", type=int, default=20, help="Maximum allowed sources to include.")
    real_narrative_template.add_argument("--blocked-limit", type=int, default=20, help="Maximum blocked future sources to include.")

    real_curated_bundle = sub.add_parser(
        "real-case-curated-bundle",
        help="Apply curated narratives to a draft and build a verified scratch replay bundle.",
    )
    real_curated_bundle.add_argument("--draft-dir", required=True, help="Directory containing real_case_config.json.")
    real_curated_bundle.add_argument(
        "--narratives",
        required=True,
        help="JSON file containing human-curated narratives and source link helper fields.",
    )
    real_curated_bundle.add_argument("--out-dir", required=True, help="Output directory for the generated replay bundle.")
    real_curated_bundle.add_argument(
        "--retrieved-at",
        help="Optional ISO timestamp to stamp generated provider-derived source-pack records.",
    )
    real_curated_bundle.add_argument("--label", help="Human-readable case label for the local case index.")
    real_curated_bundle.add_argument(
        "--validation-fixture",
        help="Optional curator-filled future validation fixture to include instead of a generated pending scaffold.",
    )

    real_status = sub.add_parser(
        "real-case-status",
        help="Inspect a scratch real-case draft, curation file, and optional bundle verification state.",
    )
    real_status.add_argument("--draft-dir", required=True, help="Directory containing real_case_config.json.")
    real_status.add_argument(
        "--narratives",
        help="Optional curated narratives JSON. Defaults to curated_narratives.json or curated_narratives.template.json when present.",
    )
    real_status.add_argument("--bundle-dir", help="Optional replay bundle directory to verify.")

    ingest = sub.add_parser("source-pack-ingest", help="Convert a source pack into a replay fixture.")
    ingest.add_argument("path", help="Path to source pack JSON.")
    ingest.add_argument("--out", required=True, help="Write the generated event fixture JSON to this path.")
    ingest.add_argument("--validation-out", help="Optionally write a separate pending validation fixture scaffold.")

    validation = sub.add_parser("validation-validate", help="Validate and preview a validation fixture.")
    validation.add_argument("path", help="Path to validation fixture JSON.")

    evaluate = sub.add_parser("evaluate-cases", help="Run deterministic evaluation checks.")
    evaluate.add_argument(
        "case_index",
        nargs="?",
        default="data/fixtures/case_index.json",
        help="Path to a case index JSON file.",
    )

    register = sub.add_parser("case-index-register", help="Register a replay fixture in a case index.")
    register.add_argument("case_index", help="Path to the case index JSON file to read or create.")
    register.add_argument("--event-fixture", required=True, help="Path to the event fixture JSON file.")
    register.add_argument("--validation-fixture", required=True, help="Path to the validation fixture JSON file.")
    register.add_argument("--label", help="Human-readable case label. Defaults to '<ticker> curated case'.")
    register.add_argument("--out", help="Optional output path. Defaults to updating case_index in place.")

    validate_index = sub.add_parser("case-index-validate", help="Validate case-index fixtures and replay integrity.")
    validate_index.add_argument(
        "case_index",
        nargs="?",
        default="data/fixtures/case_index.json",
        help="Path to a case index JSON file.",
    )

    return parser


def run_replay_command(args: argparse.Namespace) -> int:
    event, narratives, audit, validation = run_replay(args.fixture)
    if args.validation:
        validation = load_validation_fixture(args.validation)
    report = generate_markdown_report(event, narratives, audit, validation)

    if args.out:
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)
    else:
        print(report)

    if args.ledger_out:
        ledger_path = Path(args.ledger_out)
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(json.dumps(ledger_export(event, narratives, audit), indent=2, sort_keys=True) + "\n")

    print(f"Ranked {len(narratives)} narratives for {event.ticker}; blocked {len(audit.blocked_source_ids)} future sources.")
    return 0


def _load_source_pack_or_error(path: str | Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    try:
        payload = load_source_pack(path)
    except (OSError, json.JSONDecodeError) as exc:
        return {}, {"ok": False, "status": "invalid_input", "errors": [str(exc)]}
    return payload, None


def run_source_pack_preview(args: argparse.Namespace) -> int:
    payload, error_response = _load_source_pack_or_error(args.path)
    if error_response:
        print(json.dumps(error_response, indent=2, sort_keys=True))
        return 1
    errors = validate_source_pack(payload)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1
    print(json.dumps({"ok": True, "preview": preview_source_pack(payload)}, indent=2))
    return 0


def run_source_pack_readiness(args: argparse.Namespace) -> int:
    payload, error_response = _load_source_pack_or_error(args.path)
    if error_response:
        print(json.dumps(error_response, indent=2, sort_keys=True))
        return 1
    result = assess_source_pack_readiness(payload)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


def run_real_case_quality(args: argparse.Namespace) -> int:
    try:
        bundle_verification = None
        validation_fixture = None
        if args.bundle_dir:
            bundle_dir = Path(args.bundle_dir)
            payload = load_source_pack(bundle_dir / "source_pack.json")
            bundle_verification = verify_replay_bundle(bundle_dir)
            validation_path = bundle_dir / "validation_fixture.json"
            if validation_path.exists():
                validation_fixture = json.loads(validation_path.read_text())
        else:
            payload = load_source_pack(args.source_pack)

        result = assess_real_case_quality(
            payload,
            min_narratives=args.min_narratives,
            max_narratives=args.max_narratives,
            min_allowed_sources=args.min_allowed_sources,
            min_blocked_future_sources=args.min_blocked_future_sources,
            min_contradictions=args.min_contradictions,
            require_demo_ready=args.require_demo_ready,
            require_public_ready=args.require_public_ready,
            bundle_verification=bundle_verification,
            validation_fixture=validation_fixture,
        )
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "status": "invalid_input", "errors": [str(exc)]}, indent=2, sort_keys=True))
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


def run_source_pack_bundle(args: argparse.Namespace) -> int:
    payload, error_response = _load_source_pack_or_error(args.path)
    if error_response:
        print(json.dumps(error_response, indent=2, sort_keys=True))
        return 1
    response, status = _bundle_source_pack_payload(
        payload,
        Path(args.out_dir),
        label=args.label,
        validation_fixture_path=Path(args.validation_fixture) if args.validation_fixture else None,
    )
    print(json.dumps(response, indent=2, sort_keys=True))
    return status


def run_bundle_verify(args: argparse.Namespace) -> int:
    result = verify_replay_bundle(args.bundle_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


def _bundle_source_pack_payload(
    payload: dict[str, object],
    out_dir: Path,
    *,
    label: str | None,
    persist_source_pack_on_failure: bool = False,
    validation_fixture_path: Path | None = None,
) -> tuple[dict[str, object], int]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    source_pack_path = out_dir / "source_pack.json"
    sanitized_payload = sanitize_source_pack_payload(payload)
    if persist_source_pack_on_failure:
        _write_json(source_pack_path, sanitized_payload)

    readiness = assess_source_pack_readiness(payload)
    readiness_path = out_dir / "readiness.json"
    _write_json(readiness_path, readiness)
    if not readiness["ok"]:
        response = {
            "ok": False,
            "status": readiness["status"],
            "readiness_out": str(readiness_path),
            "errors": _readiness_errors(readiness),
        }
        if persist_source_pack_on_failure:
            response["source_pack_out"] = str(source_pack_path)
        return response, 1

    event_path = out_dir / "event_fixture.json"
    validation_path = out_dir / "validation_fixture.json"
    ledger_path = out_dir / "ledger.json"
    report_path = out_dir / "report.md"
    case_index_path = out_dir / "case_index.json"
    manifest_path = out_dir / "manifest.json"

    _write_json(source_pack_path, sanitized_payload)
    fixture = build_fixture_from_source_pack(sanitized_payload)
    try:
        validation_fixture, validation_fixture_source = _bundle_validation_fixture(
            sanitized_payload,
            fixture,
            validation_fixture_path,
        )
    except ValueError as exc:
        return (
            {
                "ok": False,
                "status": "validation_fixture_invalid",
                "source_pack_out": str(source_pack_path),
                "readiness_out": str(readiness_path),
                "errors": [str(exc)],
            },
            1,
        )
    _write_json(event_path, fixture)
    _write_json(validation_path, validation_fixture)

    event, narratives, audit, _validation = run_replay(event_path)
    _write_json(ledger_path, ledger_export(event, narratives, audit))
    report_path.write_text(generate_markdown_report(event, narratives, audit, validation_fixture))
    _write_json(
        case_index_path,
        {
            "default_case_id": event.case_id,
            "cases": [
                {
                    "case_id": event.case_id,
                    "label": label or f"{event.ticker} curated case",
                    "event_fixture": event_path.name,
                    "validation_fixture": validation_path.name,
                }
            ],
        },
    )
    case_index_check = validate_case_index(case_index_path)
    if not case_index_check["ok"]:
        return (
            {
                "ok": False,
                "status": "bundle_written_but_invalid",
                "case_index_out": str(case_index_path),
                "errors": case_index_check["errors"],
            },
            1,
        )

    manifest = _bundle_manifest(
        out_dir,
        event=event,
        readiness=readiness,
        validation_fixture=validation_fixture,
        audit=audit,
        artifact_paths=[
            source_pack_path,
            readiness_path,
            event_path,
            validation_path,
            ledger_path,
            report_path,
            case_index_path,
        ],
    )
    _write_json(manifest_path, manifest)

    return (
        {
            "ok": True,
            "case_id": event.case_id,
            "out_dir": str(out_dir),
            "source_pack_out": str(source_pack_path),
            "readiness_out": str(readiness_path),
            "event_fixture_out": str(event_path),
            "validation_fixture_out": str(validation_path),
            "ledger_out": str(ledger_path),
            "report_out": str(report_path),
            "case_index_out": str(case_index_path),
            "manifest_out": str(manifest_path),
            "blocked_future_source_count": len(audit.blocked_source_ids),
            "validation_fixture_source": validation_fixture_source,
        },
        0,
    )


def _bundle_validation_fixture(
    source_pack: dict[str, object],
    event_fixture: dict[str, object],
    validation_fixture_path: Path | None,
) -> tuple[dict[str, object], str]:
    if validation_fixture_path is None:
        return build_validation_fixture_template_from_source_pack(source_pack), "generated_template"

    try:
        validation_fixture = load_validation_fixture_payload(validation_fixture_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"validation fixture override is invalid: {exc}") from exc

    event = event_fixture.get("event", {})
    expected_event_id = event.get("case_id") if isinstance(event, dict) else None
    if validation_fixture.get("event_id") != expected_event_id:
        raise ValueError(
            "validation fixture override event_id must match bundled event "
            f"{expected_event_id!r}"
        )

    source_by_id = {
        str(source["source_id"]): source
        for source in source_pack.get("sources", [])
        if isinstance(source, dict) and source.get("source_id")
    }
    blocked_future_ids = {
        source_id
        for source_id, source in source_by_id.items()
        if source.get("availability_status") == "blocked_future"
    }
    validation_future_ids = {
        str(source_id)
        for source_id in validation_fixture.get("future_source_ids", [])
        if isinstance(source_id, str)
    }
    unknown_source_ids = sorted(validation_future_ids - set(source_by_id))
    if unknown_source_ids:
        raise ValueError(
            "validation fixture override future_source_ids are not in source pack: "
            + ", ".join(unknown_source_ids)
        )
    replay_time_source_ids = sorted(validation_future_ids - blocked_future_ids)
    if replay_time_source_ids:
        raise ValueError(
            "validation fixture override future_source_ids must reference blocked_future sources: "
            + ", ".join(replay_time_source_ids)
        )

    narrative_ids = {
        str(narrative["narrative_id"])
        for narrative in source_pack.get("narratives", [])
        if isinstance(narrative, dict) and narrative.get("narrative_id")
    }
    unknown_narrative_ids = sorted(
        {
            str(row.get("narrative_id"))
            for row in validation_fixture.get("rows", [])
            if isinstance(row, dict) and row.get("narrative_id")
        }
        - narrative_ids
    )
    if unknown_narrative_ids:
        raise ValueError(
            "validation fixture override rows reference unknown narrative IDs: "
            + ", ".join(unknown_narrative_ids)
        )

    return validation_fixture, str(validation_fixture_path)


def run_real_pack_build(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    try:
        config = load_real_case_config(config_path)
        env_file_values = _load_env_file(args.env_file) if args.env_file else {}
        payload = build_real_source_pack(
            config,
            finnhub_token=_env_value(args.finnhub_token_env, env_file_values),
            sec_user_agent=_env_value(args.sec_user_agent_env, env_file_values),
            retrieved_at=args.retrieved_at,
            base_path=config_path.parent,
        )
    except (OSError, RealDataError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 1

    errors = validate_source_pack(payload, require_narratives=args.require_narratives)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1

    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "ok": True,
                "out": str(output_path),
                "preview": preview_source_pack(payload),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_real_pack_bundle(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    try:
        config = load_real_case_config(config_path)
        env_file_values = _load_env_file(args.env_file) if args.env_file else {}
        payload = build_real_source_pack(
            config,
            finnhub_token=_env_value(args.finnhub_token_env, env_file_values),
            sec_user_agent=_env_value(args.sec_user_agent_env, env_file_values),
            retrieved_at=args.retrieved_at,
            base_path=config_path.parent,
        )
    except (OSError, RealDataError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 1

    response, status = _bundle_source_pack_payload(
        payload,
        Path(args.out_dir),
        label=args.label,
        persist_source_pack_on_failure=True,
        validation_fixture_path=Path(args.validation_fixture) if args.validation_fixture else None,
    )
    print(json.dumps(response, indent=2, sort_keys=True))
    return status


def run_real_pack_check(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    try:
        config = load_real_case_config(config_path)
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 1
    errors = validate_real_case_config(
        config,
        base_path=config_path.parent,
        check_files=args.check_files,
    )
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1
    print(json.dumps({"ok": True, "preview": preview_real_case_config(config)}, indent=2, sort_keys=True))
    return 0


def run_real_data_fetch(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir) if args.out_dir else Path(".codex-work") / "live-fetches" / (
        f"{args.ticker.upper()}-{args.date_from}-{args.date_to}"
    )
    try:
        env_file_values = _load_env_file(args.env_file) if args.env_file else {}
        manifest = fetch_real_data(
            ticker=args.ticker,
            company_name=args.company_name,
            date_from=args.date_from,
            date_to=args.date_to,
            providers=args.providers,
            out_dir=out_dir,
            finnhub_token=_env_value(args.finnhub_token_env, env_file_values),
            sec_user_agent=_env_value(args.sec_user_agent_env, env_file_values),
            news_api_key=_env_value(args.news_api_key_env, env_file_values),
            forms=_split_csv_arg(args.forms),
            sec_count=args.sec_count,
            cik=args.cik,
            market_symbols=_split_csv_arg(args.market_symbols),
            include_sec_document_text=args.include_sec_document_text,
            news_query=args.news_query,
            news_domains=args.news_domains,
        )
    except (OSError, RealProvenanceError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        return 1
    response = {
        "ok": manifest["ok"],
        "out_dir": str(out_dir),
        "manifest_out": str(out_dir / "fetch_manifest.json"),
        "artifact_count": len(manifest.get("artifacts", [])),
        "errors": manifest.get("errors", []),
    }
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0 if manifest["ok"] else 1


def run_real_data_env_check(args: argparse.Namespace) -> int:
    try:
        env_file_values = _load_env_file(args.env_file) if args.env_file else {}
    except OSError as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        return 1
    providers = _provider_list(args.providers)
    deduped_required_env = _provider_env_names(
        providers,
        finnhub_token_env=args.finnhub_token_env,
        sec_user_agent_env=args.sec_user_agent_env,
        news_api_key_env=args.news_api_key_env,
    )
    env_state = _env_presence(deduped_required_env, env_file_values)
    response = {
        "ok": not env_state["missing_env"] and not env_state["empty_env"],
        "env_file": args.env_file,
        "providers": providers,
        "required_env": deduped_required_env,
        **env_state,
    }
    if not response["ok"]:
        response["next_action"] = _provider_env_next_action(env_state)
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0 if response["ok"] else 1


def run_real_case_preflight(args: argparse.Namespace) -> int:
    try:
        env_file_values = _load_env_file(args.env_file) if args.env_file else {}
    except OSError as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        return 1
    response = _real_case_preflight(
        ticker=args.ticker,
        event_date=args.event_date,
        providers=args.providers,
        out_root=Path(args.out_root),
        fetch_dir=Path(args.fetch_dir) if args.fetch_dir else None,
        draft_dir=Path(args.draft_dir) if args.draft_dir else None,
        bundle_dir=Path(args.bundle_dir) if args.bundle_dir else None,
        narratives_path=Path(args.narratives) if args.narratives else None,
        env_file=args.env_file,
        env_file_values=env_file_values,
        finnhub_token_env=args.finnhub_token_env,
        sec_user_agent_env=args.sec_user_agent_env,
        news_api_key_env=args.news_api_key_env,
    )
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0 if response["ok"] else 1


def _provider_list(providers: str | None) -> list[str]:
    return [provider.lower() for provider in _split_csv_arg(providers)]


def _provider_env_names(
    providers: list[str],
    *,
    finnhub_token_env: str,
    sec_user_agent_env: str,
    news_api_key_env: str,
) -> list[str]:
    required_env: list[str] = []
    if "finnhub" in providers:
        required_env.append(finnhub_token_env)
    if "sec" in providers:
        required_env.append(sec_user_agent_env)
    if "newsapi" in providers:
        required_env.append(news_api_key_env)
    return list(dict.fromkeys(required_env))


def _default_real_case_paths(
    *,
    ticker: str,
    event_date: str,
    out_root: Path,
) -> tuple[Path, Path, Path]:
    slug = _safe_path_slug(f"{ticker.lower()}-{event_date}")
    return (
        out_root / "live-fetches" / slug,
        out_root / "real-cases" / f"{slug}-rehearsal",
        out_root / "real-cases" / f"{slug}-bundle",
    )


def _safe_path_slug(value: str) -> str:
    import re

    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "artifact"


def _real_case_preflight(
    *,
    ticker: str,
    event_date: str,
    providers: str,
    out_root: Path,
    fetch_dir: Path | None,
    draft_dir: Path | None,
    bundle_dir: Path | None,
    narratives_path: Path | None,
    env_file: str | None,
    env_file_values: dict[str, str],
    finnhub_token_env: str,
    sec_user_agent_env: str,
    news_api_key_env: str,
) -> dict[str, Any]:
    provider_names = _provider_list(providers)
    required_env = _provider_env_names(
        provider_names,
        finnhub_token_env=finnhub_token_env,
        sec_user_agent_env=sec_user_agent_env,
        news_api_key_env=news_api_key_env,
    )
    env_state = _env_presence(required_env, env_file_values)
    unavailable_env = [*env_state["missing_env"], *env_state["empty_env"]]
    default_fetch, default_draft, default_bundle = _default_real_case_paths(
        ticker=ticker,
        event_date=event_date,
        out_root=out_root,
    )
    fetch_path = fetch_dir or default_fetch
    draft_path = draft_dir or default_draft
    bundle_path = bundle_dir or default_bundle
    paths = {
        "fetch_dir": str(fetch_path),
        "fetch_manifest": str(fetch_path / "fetch_manifest.json"),
        "normalized_candidates": str(fetch_path / "normalized" / "source_candidates.json"),
        "draft_dir": str(draft_path),
        "real_case_config": str(draft_path / "real_case_config.json"),
        "curation_template": str(draft_path / "curated_narratives.template.json"),
        "bundle_dir": str(bundle_path),
        "bundle_manifest": str(bundle_path / "manifest.json"),
        "bundle_verify": str(bundle_path / "bundle_verify.json"),
    }
    artifacts = {name: Path(path).exists() for name, path in paths.items()}
    response: dict[str, Any] = {
        "ok": False,
        "ticker": ticker.upper(),
        "event_date": event_date,
        "providers": provider_names,
        "env": {
            "env_file": env_file,
            "required_env": required_env,
            **env_state,
        },
        "paths": paths,
        "artifacts": artifacts,
    }

    if artifacts["real_case_config"]:
        status = _real_case_status(
            draft_path,
            narratives_path=narratives_path,
            bundle_dir=bundle_path if bundle_dir is not None or artifacts["bundle_dir"] else None,
        )
        response.update(
            {
                "ok": bool(status.get("ok")),
                "status": status.get("status"),
                "case_status": status,
                "next_action": status.get("next_action"),
            }
        )
        return response
    if artifacts["normalized_candidates"]:
        response.update(
            {
                "ok": True,
                "status": "ready_to_draft",
                "next_action": "Run real-case-draft against the normalized source candidates.",
            }
        )
        return response
    if artifacts["fetch_manifest"]:
        response.update(
            {
                "ok": True,
                "status": "ready_to_normalize",
                "next_action": "Run real-data-normalize, then real-case-draft.",
            }
        )
        return response
    if unavailable_env:
        response.update(
            {
                "status": "missing_env",
                "next_action": _provider_env_next_action(env_state),
            }
        )
        return response
    response.update(
        {
            "ok": True,
            "status": "ready_to_fetch",
            "next_action": "Run real-case-rehearse to fetch, normalize, draft, and write curation artifacts.",
        }
    )
    return response


def _env_value(name: str, env_file_values: dict[str, str]) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    return env_file_values.get(name) or None


def _env_presence(names: list[str], env_file_values: dict[str, str]) -> dict[str, list[str]]:
    present_env: list[str] = []
    empty_env: list[str] = []
    missing_env: list[str] = []
    for name in names:
        if _env_value(name, env_file_values):
            present_env.append(name)
        elif name in os.environ or name in env_file_values:
            empty_env.append(name)
        else:
            missing_env.append(name)
    return {
        "present_env": present_env,
        "empty_env": empty_env,
        "missing_env": missing_env,
    }


def _provider_env_next_action(env_state: dict[str, list[str]]) -> str:
    actions: list[str] = []
    missing_env = env_state.get("missing_env") or []
    empty_env = env_state.get("empty_env") or []
    if missing_env:
        actions.append(f"create local entries for {', '.join(missing_env)}")
    if empty_env:
        actions.append(f"fill non-empty local values for {', '.join(empty_env)}")
    if not actions:
        return "Provider environment is ready; rerun the real-case rehearsal."
    return f"Before live fetch, {' and '.join(actions)}. Keep provider secrets local and rerun real-case-rehearse."


def _load_env_file(path: str | Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in Path(path).read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def run_real_data_normalize(args: argparse.Namespace) -> int:
    try:
        summary = normalize_real_data_fetch(
            args.fetch_dir,
            replay_lock=args.replay_lock,
            out_dir=args.out_dir,
        )
    except (OSError, json.JSONDecodeError, RealProvenanceError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def run_real_source_discover(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir) if args.out_dir else Path(".codex-work") / "source-discovery" / (
        _safe_path_slug(f"{args.ticker.lower()}-{args.event_date}")
    )
    try:
        env_file_values = _load_env_file(args.env_file) if args.env_file else {}
        model = args.model or _env_value(args.perplexity_model_env, env_file_values)
        summary = discover_sources_with_sonar(
            ticker=args.ticker,
            company_name=args.company_name,
            event_date=args.event_date,
            replay_lock=args.replay_lock,
            query=args.query,
            out_dir=out_dir,
            api_key=_env_value(args.perplexity_key_env, env_file_values),
            model=model,
            search_domains=_split_csv_arg(args.search_domains),
            search_before_date=args.search_before_date,
            search_after_date=args.search_after_date,
        )
    except (OSError, json.JSONDecodeError, SourceDiscoveryError, RealProvenanceError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def run_real_source_freeze(args: argparse.Namespace) -> int:
    try:
        summary = freeze_discovery_candidates(
            discovery_dir=args.discovery_dir,
            replay_lock=args.replay_lock,
            out_dir=args.out_dir,
            normalized_dir=args.normalized_dir,
            source_type=args.source_type,
        )
    except (OSError, json.JSONDecodeError, SourceDiscoveryError, RealProvenanceError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def run_real_case_draft(args: argparse.Namespace) -> int:
    try:
        response = draft_real_case(
            ticker=args.ticker,
            company_name=args.company_name,
            event_type=args.event_type,
            event_date=args.event_date,
            replay_lock=args.replay_lock,
            normalized_dir=args.normalized_dir,
            out_dir=args.out_dir,
            case_id=args.case_id,
            market_bars_path=args.market_bars,
            market_peers=_split_csv_arg(args.market_peers),
            sector_symbol=args.sector_symbol,
        )
    except (OSError, json.JSONDecodeError, RealProvenanceError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0


def run_real_market_bars_check(args: argparse.Namespace) -> int:
    response = inspect_market_bars(
        args.path,
        ticker=args.ticker,
        replay_lock=args.replay_lock,
        peers=_split_csv_arg(args.peers),
        sector_symbol=args.sector_symbol,
    )
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0 if response["ok"] else 1


def run_real_case_worksheet(args: argparse.Namespace) -> int:
    try:
        response = write_real_case_worksheet(
            args.draft_dir,
            out=args.out,
            allowed_limit=args.allowed_limit,
            blocked_limit=args.blocked_limit,
        )
    except (OSError, json.JSONDecodeError, RealProvenanceError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0


def run_real_case_rehearse(args: argparse.Namespace) -> int:
    try:
        env_file_values = _load_env_file(args.env_file) if args.env_file else {}
        response = rehearse_real_case(
            ticker=args.ticker,
            company_name=args.company_name,
            event_type=args.event_type,
            event_date=args.event_date,
            replay_lock=args.replay_lock,
            date_from=args.date_from,
            date_to=args.date_to,
            out_root=args.out_root,
            fetch_dir=args.fetch_dir,
            draft_dir=args.draft_dir,
            providers=args.providers,
            finnhub_token=_env_value(args.finnhub_token_env, env_file_values),
            sec_user_agent=_env_value(args.sec_user_agent_env, env_file_values),
            news_api_key=_env_value(args.news_api_key_env, env_file_values),
            forms=_split_csv_arg(args.forms),
            sec_count=args.sec_count,
            cik=args.cik,
            market_peers=_split_csv_arg(args.market_peers),
            sector_symbol=args.sector_symbol,
            include_sec_document_text=args.include_sec_document_text,
            news_query=args.news_query,
            news_domains=args.news_domains,
            market_bars_path=args.market_bars,
            worksheet=not args.no_worksheet,
            curation_template=not args.no_curation_template,
            allowed_limit=args.allowed_limit,
            blocked_limit=args.blocked_limit,
            template_narrative_count=args.template_narrative_count,
        )
    except (OSError, json.JSONDecodeError, RealProvenanceError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0 if response["ok"] else 1


def run_real_case_apply_narratives(args: argparse.Namespace) -> int:
    try:
        response = apply_curated_narratives(
            args.draft_dir,
            args.narratives,
            out=args.out,
        )
    except (OSError, json.JSONDecodeError, RealProvenanceError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0


def run_real_case_curation_template(args: argparse.Namespace) -> int:
    try:
        response = write_curated_narratives_template(
            args.draft_dir,
            out=args.out,
            narrative_count=args.narrative_count,
            allowed_limit=args.allowed_limit,
            blocked_limit=args.blocked_limit,
        )
    except (OSError, json.JSONDecodeError, RealProvenanceError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0


def run_real_case_curated_bundle(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    try:
        applied = apply_curated_narratives(args.draft_dir, args.narratives)
        config_path = Path(applied["out"])
        config = load_real_case_config(config_path)
        payload = build_real_source_pack(
            config,
            retrieved_at=args.retrieved_at,
            base_path=config_path.parent,
        )
    except (OSError, json.JSONDecodeError, RealProvenanceError, RealDataError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        return 1

    response, status = _bundle_source_pack_payload(
        payload,
        out_dir,
        label=args.label,
        persist_source_pack_on_failure=True,
        validation_fixture_path=Path(args.validation_fixture) if args.validation_fixture else None,
    )
    if status == 0:
        verify = verify_replay_bundle(out_dir)
        verify_path = out_dir / "bundle_verify.json"
        _write_json(verify_path, verify)
        response = {
            **response,
            "ok": bool(response.get("ok")) and bool(verify.get("ok")),
            "curated_config_out": applied["out"],
            "bundle_verify_out": str(verify_path),
            "bundle_verify": {
                "ok": verify.get("ok"),
                "artifact_count": verify.get("artifact_count"),
                "errors": verify.get("errors", []),
            },
        }
        status = 0 if response["ok"] else 1
    else:
        response = {
            **response,
            "curated_config_out": applied["out"],
        }
    print(json.dumps(response, indent=2, sort_keys=True))
    return status


def run_real_case_status(args: argparse.Namespace) -> int:
    response = _real_case_status(
        Path(args.draft_dir),
        narratives_path=Path(args.narratives) if args.narratives else None,
        bundle_dir=Path(args.bundle_dir) if args.bundle_dir else None,
    )
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0 if response["ok"] else 1


def _real_case_status(
    draft_dir: Path,
    *,
    narratives_path: Path | None,
    bundle_dir: Path | None,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "ok": False,
        "status": "missing_draft",
        "draft_dir": str(draft_dir),
        "next_action": "Run real-case-rehearse to create a scratch draft.",
    }
    if not draft_dir.exists() or not draft_dir.is_dir():
        return response

    config_path = draft_dir / "real_case_config.json"
    summary_path = draft_dir / "draft_summary.json"
    if not config_path.exists():
        response.update(
            {
                "status": "invalid_draft",
                "errors": [f"real_case_config.json not found: {config_path}"],
                "next_action": "Regenerate the draft with real-case-draft or real-case-rehearse.",
            }
        )
        return response

    try:
        config = json.loads(config_path.read_text())
        summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    except (OSError, json.JSONDecodeError) as exc:
        response.update(
            {
                "status": "invalid_draft",
                "errors": [str(exc)],
                "next_action": "Regenerate the draft; one of its JSON artifacts is invalid.",
            }
        )
        return response

    sources = config.get("manual_sources", [])
    if not isinstance(sources, list):
        sources = []
    allowed = [source for source in sources if isinstance(source, dict) and source.get("availability_status") == "allowed"]
    blocked = [
        source
        for source in sources
        if isinstance(source, dict) and source.get("availability_status") == "blocked_future"
    ]
    allowed_source_types = {
        str(source.get("source_type", "")).strip()
        for source in allowed
        if isinstance(source, dict) and str(source.get("source_type", "")).strip()
    }
    current_market_bars_check = _real_case_status_current_market_bars_check(
        draft_dir,
        config,
        summary,
    )
    current_market_bars_available = bool(current_market_bars_check.get("ok")) or "market_data" in allowed_source_types
    current_filings_available = bool({"filing", "sec_filing"} & allowed_source_types)
    current_news_available = bool({"news", "news_article"} & allowed_source_types)
    current_summary = {
        **summary,
        "market_bars_available": current_market_bars_available,
        "market_bars_check": current_market_bars_check,
    }
    response.update(
        {
            "status": "needs_sources",
            "draft": {
                "config": str(config_path),
                "summary": str(summary_path) if summary_path.exists() else None,
                "case_id": (config.get("case_metadata") or {}).get("case_id") if isinstance(config, dict) else None,
                "ticker": (config.get("case_metadata") or {}).get("ticker") if isinstance(config, dict) else None,
                "case_readiness": summary.get("case_readiness"),
                "accepted_sources": len(allowed),
                "blocked_future_sources": len(blocked),
                "rejected_sources": summary.get("rejected_sources"),
                "market_bars_available": current_market_bars_available,
                "market_bars_check": current_market_bars_check,
                "market_context": _real_case_status_market_context(
                    current_market_bars_check
                ),
                "filings_available": current_filings_available,
                "news_available": current_news_available,
                "missing_requirements": summary.get("missing_requirements", []),
            },
            "next_action": _real_case_status_next_action(current_summary),
        }
    )
    if summary.get("case_readiness") != "curator_ready":
        return response

    detected_narratives = narratives_path or _default_narratives_path(draft_dir)
    if detected_narratives is None:
        response.update(
            {
                "status": "needs_curation",
                "next_action": "Run real-case-curation-template, then replace TBD values and source links.",
            }
        )
        return response

    response["curation"] = {"narratives": str(detected_narratives), "exists": detected_narratives.exists()}
    if not detected_narratives.exists():
        response.update(
            {
                "status": "needs_curation",
                "next_action": f"Create or fix the curated narratives file: {detected_narratives}",
            }
        )
        return response

    try:
        curation = validate_curated_narratives(draft_dir, detected_narratives)
    except (OSError, json.JSONDecodeError, RealProvenanceError) as exc:
        response.update(
            {
                "status": "needs_curation",
                "curation": {
                    "narratives": str(detected_narratives),
                    "exists": True,
                    "ok": False,
                    "errors": [str(exc)],
                },
                "next_action": "Edit the curated narratives file until all placeholders and source-link errors are fixed.",
            }
        )
        return response

    response.update(
        {
            "ok": True,
            "status": "ready_to_bundle",
            "curation": curation,
            "next_action": "Run real-case-curated-bundle to write and verify the replay bundle.",
        }
    )

    if bundle_dir is not None:
        if not bundle_dir.exists():
            response.update(
                {
                    "ok": False,
                    "status": "missing_bundle",
                    "bundle": {"bundle_dir": str(bundle_dir), "exists": False},
                    "next_action": "Run real-case-curated-bundle with this bundle directory.",
                }
            )
            return response
        verification = verify_replay_bundle(bundle_dir)
        quality = _real_case_status_bundle_quality(bundle_dir, verification)
        response["bundle"] = {
            "bundle_dir": str(bundle_dir),
            "exists": True,
            "ok": verification.get("ok"),
            "artifact_count": verification.get("artifact_count"),
            "errors": verification.get("errors", []),
        }
        response["quality"] = quality
        if verification.get("ok"):
            response.update(
                {
                    "ok": True,
                    "status": "bundle_verified",
                    "next_action": _real_case_status_bundle_next_action(quality),
                }
            )
        else:
            response.update(
                {
                    "ok": False,
                    "status": "bundle_failed",
                    "next_action": "Inspect bundle errors, then rebuild with real-case-curated-bundle.",
                }
            )
    return response


def _real_case_status_bundle_quality(
    bundle_dir: Path,
    verification: dict[str, Any],
) -> dict[str, Any]:
    try:
        payload = load_source_pack(bundle_dir / "source_pack.json")
        validation_fixture = None
        validation_path = bundle_dir / "validation_fixture.json"
        if validation_path.exists():
            validation_fixture = json.loads(validation_path.read_text())
        gates = {
            "quality": assess_real_case_quality(
                payload,
                bundle_verification=verification,
                validation_fixture=validation_fixture,
            ),
            "demo": assess_real_case_quality(
                payload,
                require_demo_ready=True,
                bundle_verification=verification,
                validation_fixture=validation_fixture,
            ),
            "public_demo": assess_real_case_quality(
                payload,
                require_public_ready=True,
                bundle_verification=verification,
                validation_fixture=validation_fixture,
            ),
        }
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "errors": [str(exc)],
            "next_action": "Repair or rebuild the bundle before assessing quality gates.",
        }

    return {
        "ok": bool(gates["quality"]["ok"]),
        "source_pack": str(bundle_dir / "source_pack.json"),
        "validation_fixture": str(bundle_dir / "validation_fixture.json")
        if (bundle_dir / "validation_fixture.json").exists()
        else None,
        "gates": {
            name: _real_case_status_compact_quality_gate(result)
            for name, result in gates.items()
        },
    }


def _real_case_status_compact_quality_gate(result: dict[str, Any]) -> dict[str, Any]:
    checks = result.get("checks", {})
    failed_checks = []
    if isinstance(checks, dict):
        failed_checks = sorted(
            name
            for name, check in checks.items()
            if not isinstance(check, dict) or not bool(check.get("ok"))
        )
    response = {
        "ok": bool(result.get("ok")),
        "status": result.get("status"),
        "failed_checks": failed_checks,
        "metrics": result.get("metrics", {}),
        "next_action": result.get("next_action"),
    }
    if isinstance(checks, dict) and isinstance(checks.get("demo_market_context"), dict):
        response["market_context"] = _compact_demo_market_context(checks["demo_market_context"])
    return response


def _real_case_status_current_market_bars_check(
    draft_dir: Path,
    config: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    fallback = summary.get("market_bars_check")
    market_data = config.get("market_data") if isinstance(config, dict) else None
    if not isinstance(market_data, dict):
        return fallback if isinstance(fallback, dict) else {}

    meta = config.get("case_metadata") if isinstance(config.get("case_metadata"), dict) else {}
    ticker = meta.get("ticker") or summary.get("ticker")
    replay_lock = meta.get("event_timestamp") or summary.get("replay_lock")
    market_path_value = market_data.get("path")
    if not ticker or not replay_lock or not market_path_value:
        return fallback if isinstance(fallback, dict) else {}

    market_path = Path(str(market_path_value))
    if not market_path.is_absolute():
        market_path = draft_dir / market_path
    try:
        return inspect_market_bars(
            market_path,
            ticker=str(ticker),
            replay_lock=str(replay_lock),
            peers=market_data.get("peers"),
            sector_symbol=market_data.get("sector_symbol"),
        )
    except (OSError, TypeError, ValueError, RealProvenanceError) as exc:
        return {
            "ok": False,
            "path": str(market_path),
            "ticker": str(ticker),
            "errors": [str(exc)],
        }


def _real_case_status_market_context(market_bars_check: Any) -> dict[str, Any]:
    if not isinstance(market_bars_check, dict):
        return {
            "ok": False,
            "target_bar_present": False,
            "peer_bars_present": False,
            "peer_bar_count": 0,
            "peer_median_measurable": False,
            "abnormal_return_measurable": False,
            "daily_return": None,
            "peer_median_return": None,
            "abnormal_return": None,
            "errors": ["market_bars_check is unavailable"],
        }
    metrics = market_bars_check.get("market_metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    errors = market_bars_check.get("errors", [])
    if not isinstance(errors, list):
        errors = []
    return {
        "ok": bool(market_bars_check.get("ok"))
        and bool(market_bars_check.get("target_bar_present"))
        and bool(market_bars_check.get("peer_bars_present"))
        and bool(market_bars_check.get("peer_median_measurable"))
        and bool(market_bars_check.get("abnormal_return_measurable")),
        "target_bar_present": bool(market_bars_check.get("target_bar_present")),
        "peer_bars_present": bool(market_bars_check.get("peer_bars_present")),
        "peer_bar_count": int(market_bars_check.get("peer_bar_count") or 0),
        "peer_median_measurable": bool(market_bars_check.get("peer_median_measurable")),
        "abnormal_return_measurable": bool(market_bars_check.get("abnormal_return_measurable")),
        "daily_return": metrics.get("daily_return"),
        "peer_median_return": metrics.get("peer_median_return"),
        "abnormal_return": metrics.get("abnormal_return"),
        "event_bar_as_of": (market_bars_check.get("selected_row") or {}).get("as_of")
        if isinstance(market_bars_check.get("selected_row"), dict)
        else None,
        "errors": [str(error) for error in errors],
    }


def _compact_demo_market_context(check: dict[str, Any]) -> dict[str, Any]:
    metrics = check.get("metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    errors = check.get("errors", [])
    if not isinstance(errors, list):
        errors = []
    return {
        "ok": bool(check.get("ok")),
        "target_bar_present": bool(check.get("event_bar_present")),
        "peer_bars_present": int(check.get("peer_bar_count") or 0) > 0,
        "peer_bar_count": int(check.get("peer_bar_count") or 0),
        "peer_median_measurable": metrics.get("peer_median_return") is not None,
        "abnormal_return_measurable": metrics.get("abnormal_return") is not None,
        "daily_return": metrics.get("daily_return"),
        "peer_median_return": metrics.get("peer_median_return"),
        "abnormal_return": metrics.get("abnormal_return"),
        "event_bar_as_of": check.get("event_bar_as_of"),
        "latest_linked_evidence_at": check.get("latest_linked_evidence_at"),
        "post_evidence_bar_present": check.get("post_evidence_bar_present"),
        "errors": [str(error) for error in errors],
    }


def _real_case_status_bundle_next_action(quality: dict[str, Any]) -> str:
    gates = quality.get("gates", {})
    if not isinstance(gates, dict):
        return "Review the bundle report and decide whether this private case is demo-worthy."
    public_gate = gates.get("public_demo", {})
    demo_gate = gates.get("demo", {})
    quality_gate = gates.get("quality", {})
    if public_gate.get("ok"):
        return "Review the report, citations, and product copy before any public demo promotion."
    if demo_gate.get("ok"):
        return str(public_gate.get("next_action") or "Resolve public promotion blockers before public demo use.")
    if quality_gate.get("ok"):
        return str(demo_gate.get("next_action") or "Resolve private demo blockers before demo use.")
    return str(quality_gate.get("next_action") or "Resolve quality blockers before demo review.")


def _real_case_status_next_action(summary: dict[str, Any]) -> str:
    generic_next_action = "Fetch or curate additional timestamped sources before narrative curation."
    recommended = summary.get("recommended_next_action")
    if summary.get("case_readiness") == "curator_ready":
        return str(recommended or "Run real-case-curation-template, then replace TBD values and source links.")

    if summary.get("market_bars_available") is False and (
        recommended is None or str(recommended) == generic_next_action
    ):
        market_bars_action = "Provide replay-eligible market bars before narrative curation"
        market_bars_check = summary.get("market_bars_check")
        errors = market_bars_check.get("errors", []) if isinstance(market_bars_check, dict) else []
        error_text = "; ".join(str(error) for error in errors[:2] if error)
        if error_text:
            return f"{market_bars_action}: {error_text}"
        return f"{market_bars_action}."

    return str(recommended or generic_next_action)


def _default_narratives_path(draft_dir: Path) -> Path | None:
    curated_path = draft_dir / "curated_narratives.json"
    if curated_path.exists():
        return curated_path
    template_path = draft_dir / "curated_narratives.template.json"
    if template_path.exists():
        return template_path
    return None


def run_source_pack_ingest(args: argparse.Namespace) -> int:
    payload, error_response = _load_source_pack_or_error(args.path)
    if error_response:
        print(json.dumps(error_response, indent=2, sort_keys=True))
        return 1
    errors = validate_source_pack(payload, require_narratives=True)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1

    fixture = build_fixture_from_source_pack(payload)
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
    response = {
        "ok": True,
        "out": str(output_path),
        "case_id": fixture["event"]["case_id"],
        "narrative_count": len(fixture["narratives"]),
        "source_count": len(payload.get("sources", [])),
    }
    if args.validation_out:
        validation_fixture = build_validation_fixture_template_from_source_pack(payload)
        validation_path = Path(args.validation_out)
        validation_path.parent.mkdir(parents=True, exist_ok=True)
        validation_path.write_text(json.dumps(validation_fixture, indent=2, sort_keys=True) + "\n")
        response["validation_out"] = str(validation_path)
        response["validation_row_count"] = len(validation_fixture["rows"])
        response["validation_future_source_count"] = int(validation_fixture.get("future_source_count", 0))

    print(
        json.dumps(
            response,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_validation_validate(args: argparse.Namespace) -> int:
    try:
        payload = json.loads(Path(args.path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 1
    errors = validate_validation_fixture(payload)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1
    print(json.dumps({"ok": True, "preview": preview_validation_fixture(payload)}, indent=2, sort_keys=True))
    return 0


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _bundle_manifest(
    out_dir: Path,
    *,
    event: Any,
    readiness: dict[str, object],
    validation_fixture: dict[str, object],
    audit: Any,
    artifact_paths: list[Path],
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "bundle_type": "narrativedesk_replay_bundle",
        "case_id": event.case_id,
        "event_id": event.event_id,
        "ticker": event.ticker,
        "data_provenance_mode": event.data_provenance_mode,
        "replay_timestamp": event.event_timestamp.isoformat(),
        "readiness_status": readiness.get("status"),
        "replay_integrity": {
            "blocked_future_source_count": len(audit.blocked_source_ids),
            "blocked_future_source_ids": audit.blocked_source_ids,
            "validation_future_source_count": int(validation_fixture.get("future_source_count", 0)),
            "validation_future_source_ids": validation_fixture.get("future_source_ids", []),
            "future_validation_separate": True,
        },
        "artifacts": [
            {
                "path": path.relative_to(out_dir).as_posix(),
                "sha256": _file_sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in artifact_paths
        ],
    }


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _readiness_errors(readiness: dict[str, object]) -> list[str]:
    errors: list[str] = []
    checks = readiness.get("checks", {})
    if not isinstance(checks, dict):
        return errors
    for check_name, check in checks.items():
        if not isinstance(check, dict):
            continue
        for error in check.get("errors", []):
            errors.append(f"{check_name}: {error}")
    return errors


def _resolve_case_path(case_index_path: Path, fixture_path: str) -> Path:
    path = Path(fixture_path)
    if path.is_absolute():
        return path
    if path.exists():
        return path
    return case_index_path.parent / path


def run_evaluate_cases(args: argparse.Namespace) -> int:
    case_index_path = Path(args.case_index)
    case_evaluations = []
    for case in load_case_index(case_index_path):
        event_path = _resolve_case_path(case_index_path, case["event_fixture"])
        validation_path = _resolve_case_path(case_index_path, case["validation_fixture"])
        event, narratives, audit, _validation = run_replay(event_path)
        validation = load_validation_fixture(validation_path)
        ledger = ledger_export(event, narratives, audit)
        case_evaluations.append(
            {
                "case_id": case["case_id"],
                "label": case.get("label", case["case_id"]),
                "ticker": event.ticker,
                "evaluation": evaluate_replay(narratives, audit, validation).to_dict(),
                "citation_qa": ledger["citation_qa"],
                "source_reliability": ledger["source_reliability"],
                "source_clustering": ledger["source_clustering"],
            }
        )

    print(
        json.dumps(
            {
                "cases": case_evaluations,
                "aggregate": summarize_case_evaluations(case_evaluations),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_case_index_register(args: argparse.Namespace) -> int:
    try:
        result = register_case_index_entry(
            args.case_index,
            args.event_fixture,
            args.validation_fixture,
            label=args.label,
            output_path=args.out,
        )
    except ValueError as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 1
    print(json.dumps({"ok": True, **result}, indent=2, sort_keys=True))
    return 0


def run_case_index_validate(args: argparse.Namespace) -> int:
    result = validate_case_index(args.case_index)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


def _split_csv_arg(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command in {None, "replay"}:
        if args.command is None:
            parser.error("Please provide a subcommand. Run with --help to list available commands.")
        return run_replay_command(args)
    if args.command == "source-pack-preview":
        return run_source_pack_preview(args)
    if args.command == "source-pack-readiness":
        return run_source_pack_readiness(args)
    if args.command == "real-case-quality":
        return run_real_case_quality(args)
    if args.command == "source-pack-bundle":
        return run_source_pack_bundle(args)
    if args.command == "bundle-verify":
        return run_bundle_verify(args)
    if args.command == "real-pack-build":
        return run_real_pack_build(args)
    if args.command == "real-pack-bundle":
        return run_real_pack_bundle(args)
    if args.command == "real-pack-check":
        return run_real_pack_check(args)
    if args.command == "real-data-fetch":
        return run_real_data_fetch(args)
    if args.command == "real-data-env-check":
        return run_real_data_env_check(args)
    if args.command == "real-case-preflight":
        return run_real_case_preflight(args)
    if args.command == "real-data-normalize":
        return run_real_data_normalize(args)
    if args.command == "real-source-discover":
        return run_real_source_discover(args)
    if args.command == "real-source-freeze":
        return run_real_source_freeze(args)
    if args.command == "real-case-draft":
        return run_real_case_draft(args)
    if args.command == "real-market-bars-check":
        return run_real_market_bars_check(args)
    if args.command == "real-case-worksheet":
        return run_real_case_worksheet(args)
    if args.command == "real-case-rehearse":
        return run_real_case_rehearse(args)
    if args.command == "real-case-apply-narratives":
        return run_real_case_apply_narratives(args)
    if args.command == "real-case-curation-template":
        return run_real_case_curation_template(args)
    if args.command == "real-case-curated-bundle":
        return run_real_case_curated_bundle(args)
    if args.command == "real-case-status":
        return run_real_case_status(args)
    if args.command == "source-pack-ingest":
        return run_source_pack_ingest(args)
    if args.command == "validation-validate":
        return run_validation_validate(args)
    if args.command == "evaluate-cases":
        return run_evaluate_cases(args)
    if args.command == "case-index-register":
        return run_case_index_register(args)
    if args.command == "case-index-validate":
        return run_case_index_validate(args)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
