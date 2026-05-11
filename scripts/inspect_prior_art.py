from __future__ import annotations

import argparse
import json
from pathlib import Path

from narrativedesk.prior_art import inspect_prior_art_repos


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect prior-art repos for replay-safe manual sources.")
    parser.add_argument(
        "--repo-root",
        action="append",
        default=[],
        metavar="REPO=PATH",
        help="Local prior-art repo root. Repeat for citadail, mktmind-qtm, and applecapital.",
    )
    parser.add_argument(
        "--out-dir",
        default=".codex-work",
        help="Scratch output directory for prior-art-map.json and prior-art-manual-sources.json.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    roots = _parse_roots(args.repo_root)
    inspection = inspect_prior_art_repos(roots, output_dir=args.out_dir)
    print(
        json.dumps(
            {
                "ok": True,
                "out_dir": str(Path(args.out_dir)),
                "manual_source_count": inspection.manual_sources_payload["manual_source_count"],
                "skipped_record_count": inspection.manual_sources_payload["skipped_record_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _parse_roots(values: list[str]) -> dict[str, str]:
    roots: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"--repo-root must be REPO=PATH, got {value!r}")
        repo, path = value.split("=", 1)
        roots[repo.strip()] = path.strip()
    return roots


if __name__ == "__main__":
    raise SystemExit(main())
