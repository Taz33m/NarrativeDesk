from __future__ import annotations

from narrativedesk.citation_qa import run_citation_qa
from narrativedesk.evaluation import evaluate_replay
from narrativedesk.models import Event, Narrative
from narrativedesk.replay import ReplayAudit
from narrativedesk.scoring import weights_as_dict
from narrativedesk.source_clustering import compute_source_clustering
from narrativedesk.source_reliability import compute_source_reliability


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def _score(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def _bool_label(value: bool | None) -> str:
    if value is None:
        return "n/a"
    return "pass" if value else "miss"


def _source_map_rows(narratives: list[Narrative], audit: ReplayAudit) -> list[dict[str, str]]:
    rows: dict[str, dict[str, set[str] | str]] = {}

    for narrative in narratives:
        for item in narrative.all_evidence():
            row = rows.setdefault(
                item.source_id,
                {
                    "source_id": item.source_id,
                    "status": "allowed",
                    "source_type": item.source_type,
                    "publisher": item.publisher or "n/a",
                    "published_at": item.published_at.isoformat(),
                    "narratives": set(),
                    "relations": set(),
                },
            )
            row["narratives"].add(narrative.narrative_id)  # type: ignore[union-attr]
            row["relations"].add(item.relation)  # type: ignore[union-attr]

    for item in audit.blocked_evidence:
        source_id = str(item["source_id"])
        row = rows.setdefault(
            source_id,
            {
                "source_id": source_id,
                "status": "blocked_future",
                "source_type": str(item.get("source_type", "n/a")),
                "publisher": str(item.get("publisher") or "n/a"),
                "published_at": str(item.get("published_at", "n/a")),
                "narratives": set(),
                "relations": set(),
            },
        )
        row["status"] = "blocked_future"
        row["narratives"].add(str(item["narrative_id"]))  # type: ignore[union-attr]
        row["relations"].add(str(item.get("relation", "support")))  # type: ignore[union-attr]

    formatted: list[dict[str, str]] = []
    for row in rows.values():
        narratives_value = row["narratives"]
        relations_value = row["relations"]
        formatted.append(
            {
                "source_id": str(row["source_id"]),
                "status": str(row["status"]),
                "source_type": str(row["source_type"]),
                "publisher": str(row["publisher"]),
                "published_at": str(row["published_at"]),
                "narratives": ", ".join(sorted(narratives_value)),  # type: ignore[arg-type]
                "relations": ", ".join(sorted(relations_value)),  # type: ignore[arg-type]
            }
        )

    return sorted(formatted, key=lambda row: (row["status"] == "blocked_future", row["source_id"]))


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

    source_rows = _source_map_rows(narratives, audit)
    lines.append("## Source Map")
    lines.append("")
    lines.append("| Source | Status | Type | Publisher | Narratives | Relations |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for row in source_rows:
        lines.append(
            "| {source_id} | {status} | {source_type} | {publisher} | {narratives} | {relations} |".format(
                **row
            )
        )
    lines.append("")

    citation_qa = run_citation_qa(narratives, audit)
    lines.append("## Citation QA")
    lines.append("")
    lines.append(f"- Replay filter: {_bool_label(citation_qa.replay_filter_pass)}")
    lines.append(f"- Support coverage: {_bool_label(citation_qa.support_coverage_pass)}")
    lines.append(f"- Event-time integrity: {_bool_label(citation_qa.event_time_integrity_pass)}")
    lines.append(f"- Citation QA: {_bool_label(citation_qa.citation_qa_pass)}")
    lines.append(f"- Provenance-ready allowed sources: {_bool_label(citation_qa.provenance_ready)}")
    lines.append(f"- Returned blocked sources: {citation_qa.returned_blocked_source_count}")
    lines.append(
        f"- Narratives with support: {citation_qa.narratives_with_support_count}/{citation_qa.narrative_count}"
    )
    lines.append(f"- Missing URLs: {citation_qa.missing_url_count}")
    lines.append(f"- Missing content hashes: {citation_qa.missing_content_hash_count}")
    lines.append(f"- Low-quality evidence sources: {citation_qa.low_quality_evidence_count}")
    lines.append("")

    source_reliability = compute_source_reliability(narratives, audit)
    overall = source_reliability.overall
    lines.append("## Source Reliability")
    lines.append("")
    lines.append("Blocked future sources are counted for auditability but excluded from scoring and ranking.")
    lines.append(f"- Allowed sources: {overall.allowed_source_count}")
    lines.append(f"- Blocked future sources: {overall.blocked_future_count}")
    lines.append(f"- Average evidence quality: {_score(overall.average_evidence_quality)}")
    lines.append(f"- Average independence: {_score(overall.average_independence)}")
    lines.append(f"- Average originality score: {_score(overall.average_originality_score)}")
    lines.append(f"- Low-quality evidence sources: {overall.low_quality_source_count}")
    if overall.blocked_future_source_ids:
        lines.append(f"- Blocked source IDs: {', '.join(overall.blocked_future_source_ids)}")
    lines.append("")
    lines.append("| Publisher | Allowed | Blocked Future | Evidence Quality | Independence | Originality |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for bucket in source_reliability.by_publisher:
        lines.append(
            "| {publisher} | {allowed} | {blocked} | {quality} | {independence} | {originality} |".format(
                publisher=bucket.key,
                allowed=bucket.allowed_source_count,
                blocked=bucket.blocked_future_count,
                quality=_score(bucket.average_evidence_quality),
                independence=_score(bucket.average_independence),
                originality=_score(bucket.average_originality_score),
            )
        )
    lines.append("")

    source_clustering = compute_source_clustering(narratives, audit)
    lines.append("## Source Clustering")
    lines.append("")
    lines.append(
        "Clusters use replay-safe allowed evidence only. Future-dated source text stays quarantined."
    )
    lines.append(f"- Allowed sources clustered: {source_clustering.allowed_source_count}")
    lines.append(f"- Blocked future sources excluded: {source_clustering.blocked_future_source_count}")
    lines.append(f"- Cluster count: {source_clustering.cluster_count}")
    lines.append(f"- Duplicate clusters: {source_clustering.duplicate_cluster_count}")
    lines.append(
        f"- Average derived originality: {_score(source_clustering.average_derived_originality_score)}"
    )
    lines.append("")
    lines.append("| Cluster | Basis | Sources | Publishers | Derived Originality | Representative Claim |")
    lines.append("| --- | --- | --- | --- | ---: | --- |")
    for cluster in source_clustering.clusters:
        lines.append(
            "| {cluster_id} | {basis} | {sources} | {publishers} | {originality} | {claim} |".format(
                cluster_id=cluster.cluster_id,
                basis=cluster.cluster_basis,
                sources=", ".join(cluster.source_ids),
                publishers=", ".join(cluster.publishers),
                originality=_score(cluster.derived_originality_score),
                claim=cluster.representative_claim.replace("|", "\\|"),
            )
        )
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
        evaluation = evaluate_replay(narratives, audit, validation)
        lines.append("## Evaluation Checks")
        lines.append("")
        lines.append(
            "These deterministic checks use the ranked replay output plus separately loaded validation rows."
        )
        lines.append(f"- Validated narrative IDs: {', '.join(evaluation.validated_narrative_ids) or 'none'}")
        if evaluation.missing_validated_narrative_ids:
            lines.append(
                "- Missing validated narrative IDs: "
                f"{', '.join(evaluation.missing_validated_narrative_ids)}"
            )
        lines.append(
            f"- Validated narrative rank: #{evaluation.validated_rank}"
            if evaluation.validated_rank
            else "- Validated narrative rank: n/a"
        )
        lines.append(f"- Narrative Recall@3: {_bool_label(evaluation.narrative_recall_at_3)}")
        lines.append(f"- Top-ranked narrative validated: {_bool_label(evaluation.top_ranked_validated)}")
        lines.append(f"- Average unsupported claim penalty: {evaluation.unsupported_claim_penalty_avg:.2f}")
        lines.append(f"- Max unsupported claim penalty: {evaluation.unsupported_claim_penalty_max:.2f}")
        lines.append(
            f"- High unsupported-claim penalty narratives: {evaluation.high_unsupported_claim_count}"
        )
        lines.append(f"- Blocked future source count: {evaluation.blocked_future_source_count}")
        lines.append("")

        lines.append("## Model Comparison")
        lines.append("")
        lines.append("| System | Selected Narrative | Rank | Validated | Selection Rule |")
        lines.append("| --- | --- | ---: | --- | --- |")
        for row in evaluation.model_comparisons:
            lines.append(
                "| {system} | {selected} | {rank} | {validated} | {reason} |".format(
                    system=row.system_id,
                    selected=row.selected_narrative_id or "n/a",
                    rank=f"#{row.selected_rank}" if row.selected_rank else "n/a",
                    validated=_bool_label(row.validated),
                    reason=row.selection_reason,
                )
            )
        lines.append("")

        lines.append("## Future Validation Fixture")
        lines.append("")
        lines.append(
            "Validation data is shown separately from event-time evidence so it cannot leak into generation."
        )
        if validation.get("note"):
            lines.append(f"- Note: {validation['note']}")
        future_source_ids = validation.get("future_source_ids")
        if isinstance(future_source_ids, list) and future_source_ids:
            lines.append(f"- Future validation source IDs: {', '.join(str(item) for item in future_source_ids)}")
        rows = validation.get("rows")
        if isinstance(rows, list):
            lines.append("")
            lines.append("| Window | Label | Expected Observable | Future Sources | Synthetic Outcome |")
            lines.append("| --- | --- | --- | --- | --- |")
            for row in rows:
                row_future_sources = row.get("future_source_ids")
                if isinstance(row_future_sources, list):
                    future_sources = ", ".join(str(item) for item in row_future_sources) or "none"
                else:
                    future_sources = "none"
                lines.append(
                    "| {window} | {label} | {expected} | {sources} | {happened} |".format(
                        window=row.get("window", "n/a"),
                        label=row.get("label", "n/a"),
                        expected=row.get("expected_observable", "n/a"),
                        sources=future_sources,
                        happened=row.get("what_happened", "n/a"),
                    )
                )
        else:
            for key, value in validation.items():
                lines.append(f"- {key}: {value}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"
