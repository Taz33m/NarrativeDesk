#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FETCH_DIR = ".codex-work/live-fetches/aapl-2024-q2"
DEFAULT_DRAFT_DIR = ".codex-work/real-cases/aapl-2024-q2-rehearsal"
DEFAULT_BUNDLE_DIR = ".codex-work/real-cases/aapl-2024-q2-bundle"
SENSITIVE_ENV_NAMES = {
    "ALPHA_VANTAGE_API_KEY",
    "FINNHUB_API_KEY",
    "NEWS_API_KEY",
    "OPENROUTER_API_KEY",
    "PERPLEXITY_API_KEY",
    "SEC_USER_AGENT",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the scratch AAPL real-case rehearsal without committing real claims."
    )
    parser.add_argument("--ticker", default="AAPL")
    parser.add_argument("--company-name", default="Apple Inc.")
    parser.add_argument("--event-type", default="earnings/guidance")
    parser.add_argument("--event-date", default="2024-05-02")
    parser.add_argument("--replay-lock", default="2024-05-03T10:00:00-04:00")
    parser.add_argument("--from", dest="date_from", default="2024-05-01")
    parser.add_argument("--to", dest="date_to", default="2024-05-20")
    parser.add_argument("--providers", default="finnhub,sec")
    parser.add_argument("--env-file", default=".env.local")
    parser.add_argument("--fetch-dir", default=DEFAULT_FETCH_DIR)
    parser.add_argument("--draft-dir", default=DEFAULT_DRAFT_DIR)
    parser.add_argument("--bundle-dir", default=DEFAULT_BUNDLE_DIR)
    parser.add_argument("--market-bars", help="Optional frozen market_bars.csv to copy into the draft.")
    parser.add_argument("--narratives", help="Curated narratives JSON. Defaults to curated_narratives.json when present.")
    parser.add_argument("--sec-count", type=int, default=5)
    parser.add_argument("--forms", default="8-K,10-Q,10-K")
    parser.add_argument("--no-sec-document-text", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument(
        "--build-bundle",
        action="store_true",
        help="Build a bundle even when the curated narratives file is not named curated_narratives.json.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    response = run_rehearsal(args)
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0 if response["ok"] else 1


def run_rehearsal(args: argparse.Namespace) -> dict[str, Any]:
    stages: dict[str, Any] = {}
    redaction_values = _redaction_values(args.env_file)
    preflight = _run_preflight(args, redaction_values)
    stages["preflight"] = preflight
    preflight_status = str(preflight["json"].get("status", ""))
    if args.preflight_only:
        return _final(
            preflight["returncode"] == 0,
            preflight_status or "preflight_failed",
            stages,
            preflight["json"].get("next_action"),
        )
    if preflight_status == "bundle_verified":
        if args.build_bundle:
            return _run_bundle_and_quality(args, stages, redaction_values)
        if _bundle_stale_after_curation(args):
            return _run_bundle_and_quality(args, stages, redaction_values)
        return _run_quality(args, stages, redaction_values)
    if preflight_status in {"missing_bundle", "bundle_failed", "ready_to_bundle"}:
        return _run_bundle_and_quality(args, stages, redaction_values)
    if preflight_status == "ready_to_normalize":
        return _run_normalize_draft_status_then_bundle(args, stages, redaction_values)
    if preflight_status == "ready_to_draft":
        return _run_draft_status_then_bundle(args, stages, redaction_values)
    if preflight_status == "needs_sources" and args.market_bars:
        return _run_draft_status_then_bundle(args, stages, redaction_values)
    if preflight_status in {"invalid_draft", "needs_sources", "needs_curation"}:
        return _final(False, preflight_status, stages, preflight["json"].get("next_action"))
    if preflight["returncode"] != 0:
        return _final(False, "preflight_failed", stages, preflight["json"].get("next_action"))

    rehearse_args = [
        "real-case-rehearse",
        "--ticker",
        args.ticker,
        "--company-name",
        args.company_name,
        "--event-type",
        args.event_type,
        "--event-date",
        args.event_date,
        "--from",
        args.date_from,
        "--to",
        args.date_to,
        "--replay-lock",
        args.replay_lock,
        "--providers",
        args.providers,
        "--forms",
        args.forms,
        "--sec-count",
        str(args.sec_count),
        *(_env_file_args(args.env_file)),
        "--fetch-dir",
        args.fetch_dir,
        "--draft-dir",
        args.draft_dir,
    ]
    if not args.no_sec_document_text:
        rehearse_args.append("--include-sec-document-text")
    if args.market_bars:
        rehearse_args.extend(["--market-bars", args.market_bars])
    rehearse = _run_cli(rehearse_args, redaction_values=redaction_values)
    stages["rehearse"] = rehearse
    if rehearse["returncode"] != 0:
        if _rehearsal_produced_curator_ready_draft(rehearse["json"]):
            return _run_status_then_bundle(args, stages, redaction_values)
        return _final(False, "rehearsal_failed", stages, "Inspect the rehearsal stage errors; no real claims were committed.")

    return _run_status_then_bundle(args, stages, redaction_values)


def _rehearsal_produced_curator_ready_draft(response: dict[str, Any]) -> bool:
    return (
        str(response.get("stage") or "") == "complete_with_fetch_errors"
        and str(response.get("case_readiness") or "") == "curator_ready"
        and bool(response.get("real_case_config_out"))
    )


def _run_normalize_draft_status_then_bundle(
    args: argparse.Namespace,
    stages: dict[str, Any],
    redaction_values: list[str],
) -> dict[str, Any]:
    normalize = _run_cli(
        [
            "real-data-normalize",
            args.fetch_dir,
            "--replay-lock",
            args.replay_lock,
        ],
        redaction_values=redaction_values,
    )
    stages["normalize"] = normalize
    if normalize["returncode"] != 0:
        return _final(False, "normalize_failed", stages, "Inspect frozen fetch artifacts, then rerun normalization.")
    normalized_dir = normalize["json"].get("out_dir") or str(Path(args.fetch_dir) / "normalized")
    return _run_draft_status_then_bundle(args, stages, redaction_values, normalized_dir=normalized_dir)


def _run_draft_status_then_bundle(
    args: argparse.Namespace,
    stages: dict[str, Any],
    redaction_values: list[str],
    *,
    normalized_dir: str | None = None,
) -> dict[str, Any]:
    if args.market_bars:
        market_bars_check = _run_cli(
            [
                "real-market-bars-check",
                args.market_bars,
                "--ticker",
                args.ticker,
                "--replay-lock",
                args.replay_lock,
            ],
            redaction_values=redaction_values,
        )
        stages["market_bars_check"] = market_bars_check
        if market_bars_check["returncode"] != 0:
            errors = market_bars_check["json"].get("errors") or []
            return _final(
                False,
                "market_bars_failed",
                stages,
                _market_bars_next_action(errors),
            )

    draft_args = [
        "real-case-draft",
        "--ticker",
        args.ticker,
        "--company-name",
        args.company_name,
        "--event-type",
        args.event_type,
        "--event-date",
        args.event_date,
        "--replay-lock",
        args.replay_lock,
        "--normalized-dir",
        normalized_dir or str(Path(args.fetch_dir) / "normalized"),
        "--out-dir",
        args.draft_dir,
    ]
    if args.market_bars:
        draft_args.extend(["--market-bars", args.market_bars])
    draft = _run_cli(draft_args, redaction_values=redaction_values)
    stages["draft"] = draft
    if draft["returncode"] != 0:
        return _final(False, "draft_failed", stages, "Inspect normalized source candidates, then rerun drafting.")

    worksheet = _run_cli(["real-case-worksheet", "--draft-dir", args.draft_dir], redaction_values=redaction_values)
    stages["worksheet"] = worksheet
    if worksheet["returncode"] != 0:
        return _final(False, "worksheet_failed", stages, "Inspect the drafted real-case config, then rerun worksheet generation.")

    template = _run_cli(["real-case-curation-template", "--draft-dir", args.draft_dir], redaction_values=redaction_values)
    stages["curation_template"] = template
    if template["returncode"] != 0:
        return _final(False, "curation_template_failed", stages, "Inspect the drafted real-case config, then rerun curation template generation.")

    return _run_status_then_bundle(args, stages, redaction_values)


def _market_bars_next_action(errors: Any) -> str:
    if isinstance(errors, list) and errors:
        return f"Provide replay-eligible market bars before drafting: {'; '.join(str(error) for error in errors)}"
    return "Provide replay-eligible market bars before drafting."


def _run_preflight(args: argparse.Namespace, redaction_values: list[str]) -> dict[str, Any]:
    preflight_args = [
        "real-case-preflight",
        "--ticker",
        args.ticker,
        "--event-date",
        args.event_date,
        "--providers",
        args.providers,
        *(_env_file_args(args.env_file)),
        "--fetch-dir",
        args.fetch_dir,
        "--draft-dir",
        args.draft_dir,
        "--bundle-dir",
        args.bundle_dir,
    ]
    if args.narratives:
        preflight_args.extend(["--narratives", args.narratives])
    return _run_cli(preflight_args, redaction_values=redaction_values)


def _run_status_then_bundle(
    args: argparse.Namespace,
    stages: dict[str, Any],
    redaction_values: list[str],
) -> dict[str, Any]:
    narratives_path = _select_narratives_path(args)
    status_args = ["real-case-status", "--draft-dir", args.draft_dir]
    if narratives_path is not None:
        status_args.extend(["--narratives", str(narratives_path)])
    status = _run_cli(status_args, redaction_values=redaction_values)
    stages["status"] = status
    status_name = str(status["json"].get("status") or "")
    if status["returncode"] != 0 and status_name not in {"missing_bundle", "bundle_failed", "ready_to_bundle"}:
        return _final(False, status_name or "status_failed", stages, status["json"].get("next_action"))

    if narratives_path is None:
        return _final(
            False,
            "needs_curation",
            stages,
            "Curate 3-5 narratives in curated_narratives.json, then rerun this script.",
        )

    return _run_bundle_and_quality(args, stages, redaction_values, narratives_path=narratives_path)


def _run_bundle_and_quality(
    args: argparse.Namespace,
    stages: dict[str, Any],
    redaction_values: list[str],
    *,
    narratives_path: Path | None = None,
) -> dict[str, Any]:
    narratives_path = narratives_path or _select_narratives_path(args)
    if narratives_path is None:
        return _final(
            False,
            "needs_curation",
            stages,
            "Curate 3-5 narratives in curated_narratives.json, then rerun this script.",
        )

    should_build_bundle = args.build_bundle or narratives_path.name == "curated_narratives.json"
    if not should_build_bundle:
        return _final(
            False,
            "needs_curation",
            stages,
            "Replace the curation template with curated_narratives.json, then rerun this script.",
        )

    bundle = _run_cli(
        [
            "real-case-curated-bundle",
            "--draft-dir",
            args.draft_dir,
            "--narratives",
            str(narratives_path),
            "--out-dir",
            args.bundle_dir,
            "--label",
            f"{args.ticker.upper()} private real-case rehearsal",
        ],
        redaction_values=redaction_values,
    )
    stages["bundle"] = bundle
    if bundle["returncode"] != 0:
        return _final(False, "bundle_failed", stages, "Fix curated narratives and source links, then rebuild the bundle.")

    return _run_quality(args, stages, redaction_values)


def _run_quality(args: argparse.Namespace, stages: dict[str, Any], redaction_values: list[str]) -> dict[str, Any]:
    quality = _run_cli(["real-case-quality", "--bundle-dir", args.bundle_dir], redaction_values=redaction_values)
    stages["quality"] = quality
    if quality["returncode"] != 0:
        return _final(False, "quality_failed", stages, quality["json"].get("next_action"))
    return _final(True, "quality_ready", stages, quality["json"].get("next_action"))


def _select_narratives_path(args: argparse.Namespace) -> Path | None:
    if args.narratives:
        return Path(args.narratives)
    curated = Path(args.draft_dir) / "curated_narratives.json"
    if curated.exists():
        return curated
    template = Path(args.draft_dir) / "curated_narratives.template.json"
    if template.exists():
        return template
    return None


def _bundle_stale_after_curation(args: argparse.Namespace) -> bool:
    bundle_manifest = Path(args.bundle_dir) / "manifest.json"
    if not bundle_manifest.exists():
        return False
    input_paths = [Path(args.draft_dir) / "real_case_config.json"]
    narratives_path = _select_narratives_path(args)
    if narratives_path is not None:
        input_paths.append(narratives_path)
    existing_inputs = [path for path in input_paths if path.exists()]
    if not existing_inputs:
        return False
    newest_input_mtime = max(path.stat().st_mtime for path in existing_inputs)
    bundle_paths = [bundle_manifest, Path(args.bundle_dir) / "bundle_verify.json"]
    existing_bundle_paths = [path for path in bundle_paths if path.exists()]
    oldest_bundle_mtime = min(path.stat().st_mtime for path in existing_bundle_paths)
    return newest_input_mtime > oldest_bundle_mtime


def _env_file_args(path_value: str | None) -> list[str]:
    if not path_value:
        return []
    path = Path(path_value)
    if path.exists():
        return ["--env-file", str(path)]
    return []


def _run_cli(cli_args: list[str], *, redaction_values: list[str] | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = src_path if not env.get("PYTHONPATH") else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "narrativedesk.cli", *cli_args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "returncode": result.returncode,
        "command": _redact_obj(["python3", "-m", "narrativedesk.cli", *cli_args], redaction_values or []),
        "json": _json_or_error(result.stdout, result.stderr, redaction_values or []),
    }


def _json_or_error(stdout: str, stderr: str, redaction_values: list[str] | None = None) -> dict[str, Any]:
    redaction_values = redaction_values or []
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "stdout": _redact_text(stdout, redaction_values),
            "stderr": _redact_text(stderr, redaction_values),
        }
    if not isinstance(parsed, dict):
        return {
            "ok": False,
            "stdout": _redact_text(stdout, redaction_values),
            "stderr": _redact_text(stderr, redaction_values),
        }
    return _redact_obj(parsed, redaction_values)


def _redaction_values(env_file: str | None) -> list[str]:
    values = [os.environ.get(name, "") for name in sorted(SENSITIVE_ENV_NAMES)]
    if env_file and Path(env_file).exists():
        values.extend(_load_sensitive_env_file_values(Path(env_file)).values())
    values.extend(_sensitive_substrings(values))
    deduped = []
    for value in values:
        if value and len(value) >= 4 and value not in deduped:
            deduped.append(value)
    return sorted(deduped, key=len, reverse=True)


def _load_sensitive_env_file_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        if key not in SENSITIVE_ENV_NAMES:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _sensitive_substrings(values: list[str]) -> list[str]:
    substrings: list[str] = []
    for value in values:
        substrings.extend(re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", value))
    return substrings


def _redact_obj(value: Any, redaction_values: list[str]) -> Any:
    if isinstance(value, str):
        return _redact_text(value, redaction_values)
    if isinstance(value, list):
        return [_redact_obj(item, redaction_values) for item in value]
    if isinstance(value, dict):
        return {key: _redact_obj(item, redaction_values) for key, item in value.items()}
    return value


def _redact_text(value: str, redaction_values: list[str]) -> str:
    redacted = value
    for secret in redaction_values:
        redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def _final(ok: bool, status: str, stages: dict[str, Any], next_action: str | None) -> dict[str, Any]:
    return {
        "ok": ok,
        "status": status,
        "stages": stages,
        "next_action": next_action,
    }


if __name__ == "__main__":
    raise SystemExit(main())
