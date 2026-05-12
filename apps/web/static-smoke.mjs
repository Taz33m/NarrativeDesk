import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const requiredDistFiles = [
  'dist/index.html',
  'dist/demo/ledger.json',
  'dist/demo/validation.json',
  'dist/demo/report.md',
  'dist/demo/cases.json',
  'dist/demo/evaluations.json',
];

for (const file of requiredDistFiles) {
  await readFile(resolve(file), 'utf8');
}

const index = await readFile(resolve('dist/index.html'), 'utf8');
const ledger = JSON.parse(await readFile(resolve('dist/demo/ledger.json'), 'utf8'));
const validation = JSON.parse(await readFile(resolve('dist/demo/validation.json'), 'utf8'));
const report = await readFile(resolve('dist/demo/report.md'), 'utf8');

assert.match(index, /NarrativeDesk Workbench/);
assert.match(index, /rel="icon"[^>]+href="\.?\/logo\.png"/);
assert.match(index, /rel="apple-touch-icon"[^>]+href="\.?\/logo\.png"/);
assert.equal(ledger.event.ticker, 'AAPL');
assert.equal(ledger.event.data_provenance_mode, 'real-curated');
const cases = JSON.parse(await readFile(resolve('dist/demo/cases.json'), 'utf8'));
const evaluations = JSON.parse(await readFile(resolve('dist/demo/evaluations.json'), 'utf8'));
assert.equal(cases.default_case_id, 'EVT-REAL-AAPL-2024-05-02');
assert.equal(cases.cases.length, 1);
assert.equal(cases.aggregate, undefined);
assert.equal(cases.cases[0].validation, undefined);
assert.equal(cases.cases[0].evaluation, undefined);
assert.equal(cases.cases[0].bundle_integrity.verified_by_bundle_verify, true);
assert.equal(cases.cases[0].bundle_integrity.readiness_status, 'ready_to_ingest');
assert.equal(cases.cases[0].bundle_integrity.artifact_hashes_ok, true);
assert.equal(cases.cases[0].bundle_integrity.replay_integrity_ok, true);
assert.equal(cases.cases[0].bundle_integrity.blocked_future_source_count, 1);
assert.equal(cases.cases[0].bundle_integrity.validation_future_source_count, 1);
assert.match(cases.cases[0].report, /NarrativeDesk Event Report: AAPL/);
assert.doesNotMatch(cases.cases[0].report, /Future Validation Fixture/);
assert.equal(evaluations.aggregate.case_count, 1);
assert.equal(evaluations.aggregate.narrative_recall_at_3_rate, 1);
assert.equal(evaluations.aggregate.evidence_only_validated_rate, 1);
assert.equal(evaluations.aggregate.headline_baseline_validated_rate, 0);
assert.equal(evaluations.aggregate.narrativedesk_tournament_validated_rate, 1);
assert.equal(evaluations.aggregate.no_contradiction_penalty_validated_rate, 1);
assert.equal(evaluations.aggregate.quality_weighted_validated_rate, 1);
assert.equal(evaluations.aggregate.top_ranked_validated_rate, 1);
assert.equal(evaluations.aggregate.citation_qa_pass_rate, 1);
assert.equal(evaluations.aggregate.provenance_ready_rate, 1);
assert.equal(evaluations.aggregate.blocked_future_source_count, 1);
assert.equal(evaluations.aggregate.source_cluster_count, 4);
assert.equal(evaluations.aggregate.source_duplicate_cluster_count, 2);
assert.equal(ledger.narratives.length, 4);
assert.equal(ledger.event.case_id, 'EVT-REAL-AAPL-2024-05-02');
assert.equal(ledger.narratives[0].title, 'Capital return reset');
assert.deepEqual(ledger.replay_audit.blocked_source_ids, ['SEC-027']);
assert.equal(ledger.citation_qa.event_time_integrity_pass, true);
assert.equal(ledger.citation_qa.citation_qa_pass, true);
assert.equal(ledger.citation_qa.missing_url_count, 0);
assert.equal(ledger.source_reliability.overall.allowed_source_count, 7);
assert.equal(ledger.source_reliability.overall.blocked_future_count, 1);
assert.deepEqual(ledger.source_reliability.overall.blocked_future_source_ids, ['SEC-027']);
assert.equal(ledger.source_clustering.allowed_source_count, 7);
assert.equal(ledger.source_clustering.cluster_count, 4);
assert.deepEqual(ledger.source_clustering.blocked_future_source_ids, ['SEC-027']);
assert.deepEqual(validation.future_source_ids, ['SEC-027']);
assert.equal(validation.rows[2].label, 'validated');
assert.deepEqual(validation.rows[2].future_source_ids, ['SEC-027']);
assert.match(report, /Research support output. Not investment advice./);
assert.match(report, /real-curated replay bundle/i);
assert.match(report, /Blocked future sources: SEC-027/);
assert.match(report, /## Source Map/);
assert.match(report, /\| SEC-027 \| blocked_future \| filing \| n\/a \| NARR-AAPL-001 \| support \|/);
assert.match(report, /## Citation QA/);
assert.match(report, /Replay filter: pass/);
assert.match(report, /Event-time integrity: pass/);
assert.match(report, /Citation QA: pass/);
assert.match(report, /## Source Reliability/);
assert.match(report, /Average evidence quality: 0\.73/);
assert.match(report, /## Source Clustering/);
assert.match(report, /Blocked future sources excluded: 1/);
assert.doesNotMatch(report, /## Evaluation Checks/);
assert.doesNotMatch(report, /## Model Comparison/);
assert.doesNotMatch(report, /Future Validation Fixture/);

console.log('Static smoke passed: dist shell, ledger, validation, and report artifacts are coherent.');
