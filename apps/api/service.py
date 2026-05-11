from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from narrativedesk.evaluation import evaluate_replay, summarize_case_evaluations
from narrativedesk.pipeline import (
    ledger_export,
    load_case_index,
    load_event_fixture,
    load_validation_fixture,
    run_replay,
)
from narrativedesk.report import generate_markdown_report


ROOT_DIR = Path(__file__).resolve().parents[2]
CASE_INDEX_FIXTURE = ROOT_DIR / "data" / "fixtures" / "case_index.json"
CASE_INDEX = load_case_index(CASE_INDEX_FIXTURE)
EVENT_FIXTURES = {
    case["case_id"]: ROOT_DIR / case["event_fixture"]
    for case in CASE_INDEX
}
VALIDATION_FIXTURES = {
    case["case_id"]: ROOT_DIR / case["validation_fixture"]
    for case in CASE_INDEX
}
CASE_LABELS = {
    case["case_id"]: case.get("label", case["case_id"])
    for case in CASE_INDEX
}


@dataclass(frozen=True)
class ApiError(Exception):
    status_code: int
    detail: str


def fixture_for_event(event_id: str) -> Path:
    fixture = EVENT_FIXTURES.get(event_id)
    if fixture is None or not fixture.exists():
        raise ApiError(status_code=404, detail=f"Event not found: {event_id}")
    return fixture


def validation_for_event(event_id: str) -> dict[str, Any]:
    fixture = VALIDATION_FIXTURES.get(event_id)
    if fixture is None or not fixture.exists():
        raise ApiError(status_code=404, detail=f"Validation not found: {event_id}")
    return load_validation_fixture(fixture)


def event_links(event_id: str) -> dict[str, str]:
    return {
        "run": f"/api/events/{event_id}/run",
        "ledger": f"/api/events/{event_id}/ledger",
        "report": f"/api/events/{event_id}/report",
        "validation": f"/api/events/{event_id}/validation",
    }


def health() -> dict[str, str]:
    return {"status": "ok"}


def list_events() -> dict[str, list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    for event_id, fixture in EVENT_FIXTURES.items():
        event, _narratives, _validation = load_event_fixture(fixture)
        events.append(
            {
                "event_id": event_id,
                "ticker": event.ticker,
                "company_name": event.company_name,
                "event_date": event.event_date,
                "event_type": event.event_type,
                "label": CASE_LABELS.get(event_id, event_id),
                "daily_return": event.daily_return,
                "abnormal_return": event.abnormal_return,
                "replay_timestamp": event.event_timestamp.isoformat(),
                "links": event_links(event_id),
            }
        )
    return {"events": events}


def run_event(event_id: str) -> dict[str, Any]:
    event, narratives, audit, _validation = run_replay(fixture_for_event(event_id))
    payload = ledger_export(event, narratives, audit)
    payload["links"] = event_links(event_id)
    return payload


def evaluation_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in CASE_INDEX:
        event_id = case["case_id"]
        event, narratives, audit, _validation = run_replay(fixture_for_event(event_id))
        validation = validation_for_event(event_id)
        ledger = ledger_export(event, narratives, audit)
        rows.append(
            {
                "case_id": event_id,
                "label": CASE_LABELS.get(event_id, event_id),
                "ticker": event.ticker,
                "event_date": event.event_date,
                "evaluation": evaluate_replay(narratives, audit, validation).to_dict(),
                "citation_qa": ledger["citation_qa"],
                "source_reliability": ledger["source_reliability"],
                "source_clustering": ledger["source_clustering"],
                "links": event_links(event_id),
            }
        )
    return rows


def get_evaluations() -> dict[str, Any]:
    rows = evaluation_rows()
    return {
        "cases": rows,
        "aggregate": summarize_case_evaluations(rows),
    }


def get_event(event_id: str) -> dict[str, Any]:
    event, _narratives, _validation = load_event_fixture(fixture_for_event(event_id))
    return {"event": event.to_dict()}


def get_ledger(event_id: str) -> dict[str, Any]:
    return run_event(event_id)


def get_validation(event_id: str) -> dict[str, Any]:
    return validation_for_event(event_id)


def get_report(event_id: str, *, include_validation: bool = False) -> str:
    event, narratives, audit, _validation = run_replay(fixture_for_event(event_id))
    validation = validation_for_event(event_id) if include_validation else None
    return generate_markdown_report(event, narratives, audit, validation)
