from __future__ import annotations

from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import PlainTextResponse
except ImportError as exc:  # pragma: no cover - optional service layer dependency
    raise RuntimeError("Install API dependencies with `pip install -e .[api]`.") from exc

from apps.api import service


app = FastAPI(
    title="NarrativeDesk API",
    description="Event ID based API for the NarrativeDesk research kernel.",
    version="0.1.0",
)


def _handle_api_error(exc: service.ApiError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@app.get("/health")
def health() -> dict[str, str]:
    return service.health()


@app.get("/api/health")
def api_health() -> dict[str, str]:
    return service.health()


@app.get("/api/events")
def list_events() -> dict[str, list[dict[str, Any]]]:
    return service.list_events()


@app.get("/api/evaluations")
def get_evaluations() -> dict[str, Any]:
    return service.get_evaluations()


@app.get("/api/events/{event_id}")
def get_event(event_id: str) -> dict[str, Any]:
    try:
        return service.get_event(event_id)
    except service.ApiError as exc:
        raise _handle_api_error(exc) from exc


@app.post("/api/events/{event_id}/run")
def run_event(event_id: str) -> dict[str, Any]:
    try:
        return service.run_event(event_id)
    except service.ApiError as exc:
        raise _handle_api_error(exc) from exc


@app.get("/api/events/{event_id}/ledger")
def get_ledger(event_id: str) -> dict[str, Any]:
    try:
        return service.get_ledger(event_id)
    except service.ApiError as exc:
        raise _handle_api_error(exc) from exc


@app.get("/api/events/{event_id}/validation")
def get_validation(event_id: str) -> dict[str, Any]:
    try:
        return service.get_validation(event_id)
    except service.ApiError as exc:
        raise _handle_api_error(exc) from exc


@app.get("/api/events/{event_id}/report", response_class=PlainTextResponse)
def get_report(event_id: str, include_validation: bool = False) -> str:
    try:
        return service.get_report(event_id, include_validation=include_validation)
    except service.ApiError as exc:
        raise _handle_api_error(exc) from exc
