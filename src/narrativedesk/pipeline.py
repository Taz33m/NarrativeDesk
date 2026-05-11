from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from narrativedesk.citation_qa import run_citation_qa
from narrativedesk.market import compute_event_market_metrics
from narrativedesk.models import Event, Narrative
from narrativedesk.replay import ReplayAudit, filter_narratives_for_replay
from narrativedesk.scoring import rank_narratives
from narrativedesk.source_clustering import compute_source_clustering
from narrativedesk.source_reliability import compute_source_reliability
from narrativedesk.validation_fixture import load_validation_fixture_payload


def load_event_fixture(path: str | Path) -> tuple[Event, list[Narrative], dict[str, Any]]:
    payload = json.loads(Path(path).read_text())
    event_payload = dict(payload["event"])
    if payload.get("market_snapshot"):
        event_payload.update(
            compute_event_market_metrics(
                payload["market_snapshot"],
                replay_timestamp=event_payload["event_timestamp"],
            )
        )
    event = Event.from_dict(event_payload)
    narratives = [Narrative.from_dict(item) for item in payload.get("narratives", [])]
    validation = payload.get("validation", {})
    return event, narratives, validation


def load_validation_fixture(path: str | Path) -> dict[str, Any]:
    return load_validation_fixture_payload(path)


def run_replay(path: str | Path) -> tuple[Event, list[Narrative], ReplayAudit, dict[str, Any]]:
    event, narratives, validation = load_event_fixture(path)
    replay_narratives, audit = filter_narratives_for_replay(narratives, event.event_timestamp)
    ranked = rank_narratives(replay_narratives)
    return event, ranked, audit, validation


def ledger_export(event: Event, ranked_narratives: list[Narrative], audit: ReplayAudit) -> dict[str, Any]:
    return {
        "event": event.to_dict(),
        "replay_audit": audit.to_dict(),
        "citation_qa": run_citation_qa(ranked_narratives, audit).to_dict(),
        "source_reliability": compute_source_reliability(ranked_narratives, audit).to_dict(),
        "source_clustering": compute_source_clustering(ranked_narratives, audit).to_dict(),
        "narratives": [narrative.to_ledger() for narrative in ranked_narratives],
    }


def load_case_index(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text())
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError("case index cases must be a list")
    return cases
