from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKDIR = ROOT / ".codex-work" / "real-pack-smoke"


def main() -> int:
    WORKDIR.mkdir(parents=True, exist_ok=True)
    config_path = WORKDIR / "real_case_config.json"
    source_pack_path = WORKDIR / "source_pack.json"
    event_fixture_path = WORKDIR / "event_fixture.json"
    validation_fixture_path = WORKDIR / "validation_fixture.json"
    report_path = WORKDIR / "report.md"
    ledger_path = WORKDIR / "ledger.json"
    bundle_dir = WORKDIR / "bundle"

    _write_inputs(config_path)
    _run_cli(
        "real-pack-build",
        str(config_path),
        "--out",
        str(source_pack_path),
        "--retrieved-at",
        "2026-05-10T00:00:00Z",
        "--require-narratives",
    )
    _run_cli(
        "source-pack-ingest",
        str(source_pack_path),
        "--out",
        str(event_fixture_path),
        "--validation-out",
        str(validation_fixture_path),
    )
    _run_cli(
        "replay",
        str(event_fixture_path),
        "--out",
        str(report_path),
        "--ledger-out",
        str(ledger_path),
    )
    _run_cli(
        "real-pack-bundle",
        str(config_path),
        "--out-dir",
        str(bundle_dir),
        "--retrieved-at",
        "2026-05-10T00:00:00Z",
        "--label",
        "EXMPL real-pack smoke",
    )
    _run_cli("bundle-verify", str(bundle_dir))
    _assert_smoke_outputs(source_pack_path, ledger_path, bundle_dir)
    print(
        json.dumps(
            {
                "ok": True,
                "source_pack": str(source_pack_path.relative_to(ROOT)),
                "event_fixture": str(event_fixture_path.relative_to(ROOT)),
                "ledger": str(ledger_path.relative_to(ROOT)),
                "bundle": str(bundle_dir.relative_to(ROOT)),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _write_inputs(config_path: Path) -> None:
    (WORKDIR / "transcript.txt").write_text(
        "Operator: Welcome.\n"
        "Management: We are seeing slower net additions and elevated churn in the forward period.\n"
    )
    (WORKDIR / "prices.csv").write_text(
        "\n".join(
            [
                "date,ticker,open,close,volume",
                "2025-01-02T09:55:00-05:00,EXMPL,100,94,2000",
                "2025-01-02T09:55:00-05:00,PEER,100,98,1200",
                "2025-01-02T09:55:00-05:00,SPY,100,99.5,5000",
            ]
        )
        + "\n"
    )
    (WORKDIR / "estimate_revisions.csv").write_text(
        "\n".join(
            [
                "published_at,metric,period,old_estimate,new_estimate,unit,publisher,title,url",
                "2025-01-02T14:40:00Z,Net additions,FY2025,12.0,10.5,million,Example Consensus,Pre-lock net adds trim,https://estimates.example.com/pre-lock",
                "2025-01-07T13:00:00Z,Revenue,FY2025,100.0,94.0,USD million,Example Consensus,Post-lock revenue cut,https://estimates.example.com/post-lock",
            ]
        )
        + "\n"
    )
    config = {
        "case_metadata": {
            "case_id": "EVT-SMOKE-EXMPL-2025-01-02",
            "ticker": "EXMPL",
            "company_name": "Example Co",
            "event_timestamp": "2025-01-02T10:00:00-05:00",
            "event_type": "earnings/guidance",
            "event_summary": "Local real-pack smoke case built from frozen provider exports.",
        },
        "market_data": {
            "provider": "csv",
            "path": "prices.csv",
            "peers": ["PEER"],
            "sector_symbol": "SPY",
        },
        "transcripts": {
            "items": [
                {
                    "path": "transcript.txt",
                    "publisher": "Example Co investor relations",
                    "title": "Example Co earnings call transcript",
                    "url": "https://ir.example.com/transcript",
                    "published_at": "2025-01-02T09:20:00-05:00",
                    "supported_narrative_ids": ["SMOKE-NARR-001"],
                }
            ]
        },
        "estimate_revisions": {
            "provider": "csv",
            "path": "estimate_revisions.csv",
            "default_supported_narrative_ids": ["SMOKE-NARR-001"],
        },
        "narratives": [
            {
                "narrative_id": "SMOKE-NARR-001",
                "title": "Forward demand slowdown",
                "narrative": "The abnormal move reflects concern that forward demand is slowing.",
                "mechanism": "Lower expected net additions and revenue estimates reduce forward growth expectations.",
                "directional_implication": "bearish",
                "time_horizon": "20 trading days",
                "expected_observables": ["Estimate revisions reduce forward net additions or revenue."],
                "scoring_inputs": {
                    "evidence_strength": 0.75,
                    "mechanism_specificity": 0.8,
                    "source_independence": 0.65,
                    "cross_sectional_fit": 0.7,
                    "contradiction_resistance": 0.6,
                    "timestamp_advantage": 0.8,
                    "forward_observable_quality": 0.78,
                    "crowding_risk": 0.25,
                    "unsupported_claim_penalty": 0.03,
                },
            }
        ],
    }
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")


def _run_cli(*args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "narrativedesk.cli", *args],
        cwd=ROOT,
        env={
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(ROOT / "src"),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"CLI command failed: {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def _assert_smoke_outputs(source_pack_path: Path, ledger_path: Path, bundle_dir: Path) -> None:
    source_pack = json.loads(source_pack_path.read_text())
    ledger = json.loads(ledger_path.read_text())
    validation = json.loads((WORKDIR / "validation_fixture.json").read_text())
    bundle_readiness = json.loads((bundle_dir / "readiness.json").read_text())
    bundle_case_index = json.loads((bundle_dir / "case_index.json").read_text())
    bundle_ledger = json.loads((bundle_dir / "ledger.json").read_text())
    bundle_manifest = json.loads((bundle_dir / "manifest.json").read_text())
    source_counts = {
        status: sum(1 for source in source_pack["sources"] if source["availability_status"] == status)
        for status in ["allowed", "blocked_future"]
    }
    if source_counts != {"allowed": 2, "blocked_future": 1}:
        raise AssertionError(f"unexpected source counts: {source_counts}")
    if validation.get("future_source_ids") != ["EST-002"]:
        raise AssertionError(f"unexpected validation future source ids: {validation.get('future_source_ids')}")
    row_source_ids = validation["rows"][0].get("future_source_ids")
    if row_source_ids != ["EST-002"]:
        raise AssertionError(f"unexpected validation row future source ids: {row_source_ids}")
    blocked_ids = ledger["replay_audit"]["blocked_source_ids"]
    if blocked_ids != ["EST-002"]:
        raise AssertionError(f"unexpected blocked source ids: {blocked_ids}")
    returned_source_ids = {
        item["source_id"]
        for narrative in ledger["narratives"]
        for item in [*narrative["supporting_evidence"], *narrative["contradicting_evidence"]]
    }
    if "EST-002" in returned_source_ids:
        raise AssertionError("future estimate revision leaked into ranked narrative evidence")
    if not bundle_readiness.get("ok"):
        raise AssertionError(f"bundle readiness failed: {bundle_readiness}")
    if bundle_case_index["cases"][0]["event_fixture"] != "event_fixture.json":
        raise AssertionError(f"bundle case index is not portable: {bundle_case_index}")
    if bundle_ledger["replay_audit"]["blocked_source_ids"] != ["EST-002"]:
        raise AssertionError(f"unexpected bundle blocked source ids: {bundle_ledger['replay_audit']['blocked_source_ids']}")
    if bundle_manifest["replay_integrity"]["blocked_future_source_ids"] != ["EST-002"]:
        raise AssertionError(f"unexpected bundle manifest replay integrity: {bundle_manifest}")
    manifest_paths = [artifact["path"] for artifact in bundle_manifest["artifacts"]]
    if "source_pack.json" not in manifest_paths or "case_index.json" not in manifest_paths:
        raise AssertionError(f"bundle manifest missing expected artifacts: {manifest_paths}")


if __name__ == "__main__":
    raise SystemExit(main())
