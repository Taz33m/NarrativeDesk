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
assert.equal(ledger.event.ticker, 'ORION');
const cases = JSON.parse(await readFile(resolve('dist/demo/cases.json'), 'utf8'));
const evaluations = JSON.parse(await readFile(resolve('dist/demo/evaluations.json'), 'utf8'));
assert.ok(cases.cases.length >= 3);
assert.equal(cases.aggregate, undefined);
assert.equal(cases.cases[1].validation, undefined);
assert.equal(cases.cases[1].evaluation, undefined);
assert.match(cases.cases[1].report, /NarrativeDesk Event Report: AURORA/);
assert.doesNotMatch(cases.cases[1].report, /Future Validation Fixture/);
assert.equal(evaluations.aggregate.case_count, 3);
assert.equal(evaluations.aggregate.narrative_recall_at_3_rate, 1);
assert.equal(evaluations.aggregate.evidence_only_validated_rate, 2 / 3);
assert.equal(evaluations.aggregate.headline_baseline_validated_rate, 1 / 3);
assert.equal(evaluations.aggregate.narrativedesk_tournament_validated_rate, 2 / 3);
assert.equal(evaluations.aggregate.no_contradiction_penalty_validated_rate, 2 / 3);
assert.equal(evaluations.aggregate.quality_weighted_validated_rate, 2 / 3);
assert.equal(evaluations.aggregate.top_ranked_validated_rate, 2 / 3);
assert.equal(evaluations.aggregate.citation_qa_pass_rate, 2 / 3);
assert.equal(evaluations.aggregate.provenance_ready_rate, 2 / 3);
assert.equal(evaluations.aggregate.blocked_future_source_count, 3);
assert.equal(evaluations.aggregate.source_cluster_count, 12);
assert.equal(evaluations.aggregate.source_duplicate_cluster_count, 3);
assert.equal(cases.cases[1].ledger.event.case_id, 'EVT-AURORA-2025-10-22');
assert.equal(cases.cases[1].ledger.event.ticker, 'AURORA');
assert.equal(evaluations.cases[1].evaluation.validated_rank, 1);
assert.equal(cases.cases[1].ledger.event.daily_return, -0.097);
assert.equal(cases.cases[1].ledger.event.abnormal_return, -0.084);
assert.deepEqual(cases.cases[1].ledger.replay_audit.blocked_source_ids, ['AUR-SRC-009']);
assert.match(cases.cases[1].report, /Blocked future sources: AUR-SRC-009/);
assert.match(cases.cases[1].report, /merchant expansion/);
assert.equal(cases.cases[2].ledger.event.case_id, 'EVT-LYRA-2025-11-13');
assert.equal(cases.cases[2].ledger.event.ticker, 'LYRA');
assert.equal(evaluations.cases[2].evaluation.validated_rank, 2);
assert.equal(evaluations.cases[2].evaluation.top_ranked_validated, false);
assert.equal(evaluations.cases[2].evaluation.model_comparisons[0].validated, true);
assert.deepEqual(cases.cases[2].ledger.replay_audit.blocked_source_ids, ['LYR-SRC-009']);
assert.equal(cases.cases[2].ledger.citation_qa.provenance_ready, true);
assert.doesNotMatch(cases.cases[2].report, /Top-ranked narrative validated: miss/);
assert.doesNotMatch(cases.cases[2].report, /headline_baseline \| LYR-NARR-002 \| #2 \| pass/);
assert.equal(ledger.narratives.length, 4);
assert.equal(ledger.event.case_id, 'EVT-ORION-2025-08-07');
assert.equal(ledger.narratives[0].title, 'Forward demand slowdown');
assert.deepEqual(ledger.replay_audit.blocked_source_ids, ['SRC-009']);
assert.equal(ledger.citation_qa.event_time_integrity_pass, true);
assert.equal(ledger.citation_qa.citation_qa_pass, false);
assert.equal(ledger.citation_qa.missing_url_count, 8);
assert.equal(ledger.source_reliability.overall.allowed_source_count, 8);
assert.equal(ledger.source_reliability.overall.blocked_future_count, 1);
assert.deepEqual(ledger.source_reliability.overall.blocked_future_source_ids, ['SRC-009']);
assert.equal(ledger.source_clustering.allowed_source_count, 8);
assert.equal(ledger.source_clustering.cluster_count, 8);
assert.deepEqual(ledger.source_clustering.blocked_future_source_ids, ['SRC-009']);
assert.deepEqual(validation.future_source_ids, ['SRC-009']);
assert.equal(validation.rows[1].label, 'validated');
assert.deepEqual(validation.rows[1].future_source_ids, ['SRC-009']);
assert.match(report, /Research support output. Not investment advice./);
assert.match(report, /Blocked future sources: SRC-009/);
assert.match(report, /## Source Map/);
assert.match(report, /\| SRC-009 \| blocked_future \| analyst_revision \| n\/a \| NARR-001 \| support \|/);
assert.doesNotMatch(report, /Future analyst revisions later reduced expansion estimates/);
assert.match(report, /## Citation QA/);
assert.match(report, /Replay filter: pass/);
assert.match(report, /Event-time integrity: pass/);
assert.match(report, /Citation QA: miss/);
assert.match(report, /## Source Reliability/);
assert.match(report, /Average evidence quality: 0\.80/);
assert.match(report, /## Source Clustering/);
assert.match(report, /Blocked future sources excluded: 1/);
assert.doesNotMatch(report, /## Evaluation Checks/);
assert.doesNotMatch(report, /## Model Comparison/);
assert.doesNotMatch(report, /Future Validation Fixture/);

console.log('Static smoke passed: dist shell, ledger, validation, and report artifacts are coherent.');
