from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from narrativedesk.models import Event, Narrative
from narrativedesk.replay import ReplayAudit, filter_narratives_for_replay
from narrativedesk.scoring import rank_narratives


def load_event_fixture(path: str | Path) -> tuple[Event, list[Narrative], dict[str, Any]]:
    payload = json.loads(Path(path).read_text())
    event = Event.from_dict(payload["event"])
    narratives = [Narrative.from_dict(item) for item in payload.get("narratives", [])]
    validation = payload.get("validation", {})
    return event, narratives, validation


def load_validation_fixture(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def run_replay(path: str | Path) -> tuple[Event, list[Narrative], ReplayAudit, dict[str, Any]]:
    event, narratives, validation = load_event_fixture(path)
    replay_narratives, audit = filter_narratives_for_replay(narratives, event.event_timestamp)
    ranked = rank_narratives(replay_narratives)
    return event, ranked, audit, validation


def ledger_export(event: Event, ranked_narratives: list[Narrative], audit: ReplayAudit) -> dict[str, Any]:
    return {
        "event": event.to_dict(),
        "replay_audit": audit.to_dict(),
        "narratives": [narrative.to_ledger() for narrative in ranked_narratives],
    }
