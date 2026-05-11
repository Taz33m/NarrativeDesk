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
    draft_real_case,
    fetch_real_data,
    normalize_real_data_fetch,
)
from narrativedesk.replay_bundle import verify_replay_bundle
from narrativedesk.source_pack import (
    assess_source_pack_readiness,
    build_fixture_from_source_pack,
    build_validation_fixture_template_from_source_pack,
    load_source_pack,
    preview_source_pack,
    validate_source_pack,
)
from narrativedesk.validation_fixture import preview_validation_fixture, validate_validation_fixture


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

    pack_bundle = sub.add_parser("source-pack-bundle", help="Create a self-contained replay bundle from a ready source pack.")
    pack_bundle.add_argument("path", help="Path to source pack JSON.")
    pack_bundle.add_argument("--out-dir", required=True, help="Directory for the generated replay bundle.")
    pack_bundle.add_argument("--label", help="Human-readable case label for the local case index.")

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
        "--retrieved-at",
        help="Optional ISO timestamp to stamp retrieved_at deterministically.",
    )
    real_bundle.add_argument("--label", help="Human-readable case label for the local case index.")

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

    real_normalize = sub.add_parser(
        "real-data-normalize",
        help="Normalize a frozen live-fetch directory into source candidates.",
    )
    real_normalize.add_argument("fetch_dir", help="Directory containing fetch_manifest.json.")
    real_normalize.add_argument("--replay-lock", required=True, help="Replay lock timestamp with timezone.")
    real_normalize.add_argument("--out-dir", help="Optional normalized output directory.")

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


def run_source_pack_preview(args: argparse.Namespace) -> int:
    payload = load_source_pack(args.path)
    errors = validate_source_pack(payload)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1
    print(json.dumps({"ok": True, "preview": preview_source_pack(payload)}, indent=2))
    return 0


def run_source_pack_readiness(args: argparse.Namespace) -> int:
    payload = load_source_pack(args.path)
    result = assess_source_pack_readiness(payload)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


def run_source_pack_bundle(args: argparse.Namespace) -> int:
    payload = load_source_pack(args.path)
    response, status = _bundle_source_pack_payload(payload, Path(args.out_dir), label=args.label)
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
) -> tuple[dict[str, object], int]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    source_pack_path = out_dir / "source_pack.json"
    if persist_source_pack_on_failure:
        _write_json(source_pack_path, payload)

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

    _write_json(source_pack_path, payload)
    fixture = build_fixture_from_source_pack(payload)
    validation_fixture = build_validation_fixture_template_from_source_pack(payload)
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
        },
        0,
    )


def run_real_pack_build(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    config = load_real_case_config(config_path)
    try:
        payload = build_real_source_pack(
            config,
            finnhub_token=os.environ.get(args.finnhub_token_env),
            sec_user_agent=os.environ.get(args.sec_user_agent_env),
            retrieved_at=args.retrieved_at,
            base_path=config_path.parent,
        )
    except RealDataError as exc:
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
    config = load_real_case_config(config_path)
    try:
        payload = build_real_source_pack(
            config,
            finnhub_token=os.environ.get(args.finnhub_token_env),
            sec_user_agent=os.environ.get(args.sec_user_agent_env),
            retrieved_at=args.retrieved_at,
            base_path=config_path.parent,
        )
    except RealDataError as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 1

    response, status = _bundle_source_pack_payload(
        payload,
        Path(args.out_dir),
        label=args.label,
        persist_source_pack_on_failure=True,
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
    required_env: list[str] = []
    providers = [provider.lower() for provider in _split_csv_arg(args.providers)]
    if "finnhub" in providers:
        required_env.append(args.finnhub_token_env)
    if "sec" in providers:
        required_env.append(args.sec_user_agent_env)
    if "newsapi" in providers:
        required_env.append(args.news_api_key_env)

    deduped_required_env = list(dict.fromkeys(required_env))
    missing_env = [name for name in deduped_required_env if not _env_value(name, env_file_values)]
    present_env = [name for name in deduped_required_env if _env_value(name, env_file_values)]
    response = {
        "ok": not missing_env,
        "env_file": args.env_file,
        "providers": providers,
        "required_env": deduped_required_env,
        "present_env": present_env,
        "missing_env": missing_env,
    }
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0 if response["ok"] else 1


def _env_value(name: str, env_file_values: dict[str, str]) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    return env_file_values.get(name) or None


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
        )
    except (OSError, json.JSONDecodeError, RealProvenanceError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0


def run_source_pack_ingest(args: argparse.Namespace) -> int:
    payload = load_source_pack(args.path)
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
    if args.command == "real-data-normalize":
        return run_real_data_normalize(args)
    if args.command == "real-case-draft":
        return run_real_case_draft(args)
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
