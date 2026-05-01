from __future__ import annotations

import argparse
import json
from pathlib import Path

from narrativedesk.pipeline import ledger_export, load_validation_fixture, run_replay
from narrativedesk.report import generate_markdown_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a NarrativeDesk replay fixture.")
    parser.add_argument("fixture", help="Path to an event fixture JSON file.")
    parser.add_argument("--out", help="Write a markdown report to this path.")
    parser.add_argument("--ledger-out", help="Write the ranked ledger JSON to this path.")
    parser.add_argument("--validation", help="Optional future validation fixture for report export.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
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
        ledger_path.write_text(
            json.dumps(ledger_export(event, narratives, audit), indent=2, sort_keys=True) + "\n"
        )

    print(
        f"Ranked {len(narratives)} narratives for {event.ticker}; "
        f"blocked {len(audit.blocked_source_ids)} future sources."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
