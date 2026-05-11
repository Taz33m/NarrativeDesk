from __future__ import annotations

import argparse
import json
from pathlib import Path

from narrativedesk.prior_art import extract_mktmind_market_bars


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract frozen market_bars.csv from local prior-art datasets.")
    parser.add_argument(
        "--mktmind-csv",
        default=".codex-work/prior-art-repos/mktmind-qtm/data/marketmind_qml_dataset.csv",
        help="Path to marketmind_qml_dataset.csv.",
    )
    parser.add_argument(
        "--out-dir",
        default=".codex-work/prior-art-market-bars",
        help="Scratch output directory for market_bars.csv and manifest.",
    )
    parser.add_argument("--tickers", help="Optional comma-separated ticker filter.")
    parser.add_argument("--from", dest="date_from", help="Optional inclusive start date, YYYY-MM-DD.")
    parser.add_argument("--to", dest="date_to", help="Optional inclusive end date, YYYY-MM-DD.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = extract_mktmind_market_bars(
        args.mktmind_csv,
        output_dir=args.out_dir,
        tickers=_split_csv(args.tickers),
        date_from=args.date_from,
        date_to=args.date_to,
    )
    print(
        json.dumps(
            {
                "ok": True,
                "market_bars": str(result.market_bars_path),
                "manifest": str(result.manifest_path),
                "row_count": result.manifest["row_count"],
                "tickers": result.manifest["tickers"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _split_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip().upper() for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
