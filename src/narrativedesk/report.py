from __future__ import annotations

from narrativedesk.models import Event, Narrative
from narrativedesk.replay import ReplayAudit
from narrativedesk.scoring import weights_as_dict


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def _score(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def generate_markdown_report(
    event: Event,
    narratives: list[Narrative],
    audit: ReplayAudit,
    validation: dict[str, object] | None = None,
) -> str:
    lines: list[str] = []
    lines.append(f"# NarrativeDesk Event Report: {event.ticker}")
    lines.append("")
    lines.append("> Research support output. Not investment advice.")
    lines.append("")
    lines.append("## Data Note")
    lines.append("")
    lines.append(
        "This sample report is generated from a synthetic fixture. Real event reports must include "
        "source URLs, publication timestamps, and raw document hashes."
    )
    lines.append("")
    lines.append("## Event")
    lines.append("")
    lines.append(f"- Event ID: `{event.event_id}`")
    lines.append(f"- Company: {event.company_name} (`{event.ticker}`)")
    lines.append(f"- Timestamp lock: `{event.event_timestamp.isoformat()}`")
    lines.append(f"- Event type: {event.event_type}")
    lines.append(f"- Daily return: {_pct(event.daily_return)}")
    lines.append(f"- Abnormal return: {_pct(event.abnormal_return)}")
    lines.append(f"- Volume ratio: {_score(event.volume_ratio)}x")
    lines.append(f"- Sector ETF return: {_pct(event.sector_etf_return)}")
    lines.append(f"- Peer median return: {_pct(event.peer_median_return)}")
    lines.append("")
    if event.event_summary:
        lines.append(event.event_summary)
        lines.append("")

    lines.append("## Replay Audit")
    lines.append("")
    lines.append(f"- Allowed sources: {', '.join(audit.allowed_source_ids) or 'none'}")
    lines.append(f"- Blocked future sources: {', '.join(audit.blocked_source_ids) or 'none'}")
    if audit.removed_evidence_by_narrative:
        for narrative_id, source_ids in audit.removed_evidence_by_narrative.items():
            lines.append(f"- Removed from `{narrative_id}`: {', '.join(source_ids)}")
    lines.append("")

    lines.append("## Narrative Tournament")
    lines.append("")
    lines.append("| Rank | Narrative | Direction | Score | Horizon |")
    lines.append("| ---: | --- | --- | ---: | --- |")
    for narrative in narratives:
        lines.append(
            f"| {narrative.rank} | {narrative.title} | {narrative.directional_implication} | "
            f"{narrative.overall_narrative_score:.2f} | {narrative.time_horizon} |"
        )
    lines.append("")

    for narrative in narratives:
        lines.append(f"## #{narrative.rank}: {narrative.title}")
        lines.append("")
        lines.append(narrative.narrative)
        lines.append("")
        lines.append(f"Mechanism: {narrative.mechanism}")
        lines.append("")
        lines.append("Expected observables:")
        for observable in narrative.expected_observables:
            lines.append(f"- {observable}")
        lines.append("")
        lines.append("Supporting evidence:")
        if narrative.supporting_evidence:
            for item in narrative.supporting_evidence:
                lines.append(f"- `{item.source_id}` ({item.source_type}): {item.claim}")
        else:
            lines.append("- None after replay filtering.")
        lines.append("")
        lines.append("Contradicting evidence:")
        if narrative.contradicting_evidence:
            for item in narrative.contradicting_evidence:
                lines.append(f"- `{item.source_id}` ({item.source_type}): {item.claim}")
        else:
            lines.append("- None after replay filtering.")
        lines.append("")
        lines.append("Score components:")
        for key, value in narrative.scoring_inputs.to_dict().items():
            lines.append(f"- {key}: {value:.2f}")
        lines.append("")

    lines.append("## Scoring Weights")
    lines.append("")
    for key, value in weights_as_dict().items():
        lines.append(f"- {key}: {value:.2f}")
    lines.append("")

    if validation:
        lines.append("## Future Validation Fixture")
        lines.append("")
        lines.append(
            "Validation data is shown separately from event-time evidence so it cannot leak into generation."
        )
        if validation.get("note"):
            lines.append(f"- Note: {validation['note']}")
        rows = validation.get("rows")
        if isinstance(rows, list):
            lines.append("")
            lines.append("| Window | Label | Expected Observable | Synthetic Outcome |")
            lines.append("| --- | --- | --- | --- |")
            for row in rows:
                lines.append(
                    "| {window} | {label} | {expected} | {happened} |".format(
                        window=row.get("window", "n/a"),
                        label=row.get("label", "n/a"),
                        expected=row.get("expected_observable", "n/a"),
                        happened=row.get("what_happened", "n/a"),
                    )
                )
        else:
            for key, value in validation.items():
                lines.append(f"- {key}: {value}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"
