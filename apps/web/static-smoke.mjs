import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const requiredDistFiles = [
  'dist/index.html',
  'dist/demo/ledger.json',
  'dist/demo/validation.json',
  'dist/demo/report.md',
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
assert.equal(ledger.narratives.length, 4);
assert.equal(ledger.narratives[0].title, 'Forward demand slowdown');
assert.deepEqual(ledger.replay_audit.blocked_source_ids, ['SRC-009']);
assert.equal(validation.rows[1].label, 'validated');
assert.match(report, /Research support output. Not investment advice./);
assert.match(report, /Blocked future sources: SRC-009/);

console.log('Static smoke passed: dist shell, ledger, validation, and report artifacts are coherent.');
