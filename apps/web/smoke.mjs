import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { chromium } from 'playwright';

const baseUrl = process.env.WEB_BASE_URL || 'http://127.0.0.1:4173';

function startPreview() {
  const binName = process.platform === 'win32' ? 'vite.cmd' : 'vite';
  const localBin = resolve('node_modules', '.bin', binName);
  const workspaceBin = resolve('..', '..', 'node_modules', '.bin', binName);
  const viteBin = existsSync(localBin) ? localBin : workspaceBin;
  const child = spawn(viteBin, ['preview', '--host', '127.0.0.1', '--port', '4173', '--strictPort'], {
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  child.stdout.on('data', (chunk) => process.stdout.write(chunk));
  child.stderr.on('data', (chunk) => process.stderr.write(chunk));
  return child;
}

function decodeDataHref(href) {
  const marker = ',';
  const body = href.slice(href.indexOf(marker) + marker.length);
  return decodeURIComponent(body);
}

async function waitForServer(url, attempts = 40) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // Preview server is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Preview server did not become ready at ${url}`);
}

async function main() {
  const server = process.env.WEB_BASE_URL ? null : startPreview();
  const consoleErrors = [];
  let browser;

  try {
    await waitForServer(baseUrl);
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push(message.text());
    });
    page.on('pageerror', (error) => consoleErrors.push(error.message));

    await page.goto(baseUrl, { waitUntil: 'networkidle' });
    const bodyText = await page.locator('body').innerText();

    assert.match(bodyText, /NarrativeDesk Replay/i);
    assert.match(bodyText, /Replay-safe narrative ranking for abnormal market moves/i);
    assert.match(bodyText, /Competing market narratives\. Time-locked evidence\. Later validation\./i);
    assert.match(bodyText, /ORION/);
    assert.match(bodyText, /Case library/i);
    assert.match(bodyText, /Winning Narrative/i);
    assert.match(bodyText, /Why it won/i);
    assert.match(bodyText, /Replay timeline/i);
    assert.match(bodyText, /Replay Lock/i);
    assert.match(bodyText, /History check/i);
    assert.match(bodyText, /Forward demand slowdown/);
    assert.match(bodyText, /Margin compression/);
    assert.match(bodyText, /Only evidence left of the lock entered ranking/i);
    const orionThesis = await page.locator('[data-testid="event-header"]').innerText();
    assert.match(orionThesis, /surface baseline[\s\S]*Margin compression/i);
    assert.match(orionThesis, /Ranked #4/i);
    assert.match(orionThesis, /Ranked #1[\s\S]*T\+20 validated the winner/i);
    assert.match(orionThesis, /winning narrative[\s\S]*Forward demand slowdown/i);
    assert.doesNotMatch(bodyText, /SRC-009/);
    assert.match(bodyText, /T\+20 validated the winner/i);
    assert.match(bodyText, /Demo provenance: synthetic benchmark case/i);

    await page.getByRole('button', { name: /^Tournament$/i }).click();
    const bracketText = await page.locator('[data-testid="tournament-bracket"]').innerText();
    assert.match(bracketText, /NarrativeDesk Tournament/i);
    assert.match(bracketText, /Head-to-head explanation bracket/i);
    await page.locator('[data-testid="narrative-tournament"]').getByRole('button', { name: /Margin compression/i }).click();
    const marginText = await page.locator('[data-testid="evidence-inspector"]').innerText();
    assert.match(marginText, /Gross margin improved year over year/);

    await page.getByRole('button', { name: /^Evidence$/i }).click();
    const evidenceText = await page.locator('body').innerText();
    assert.match(evidenceText, /SRC-009/);
    assert.match(evidenceText, /Evidence Chain/i);
    assert.match(evidenceText, /Leakage audit/i);
    assert.match(evidenceText, /Replay source inventory/i);
    assert.match(evidenceText, /Citation QA/i);
    assert.match(evidenceText, /Evidence integrity checks/i);

    await page.getByRole('button', { name: /^Benchmark$/i }).click();
    const benchmarkText = await page.locator('body').innerText();
    assert.match(benchmarkText, /Benchmark corpus/i);
    assert.match(benchmarkText, /Synthetic case-index summary/i);
    assert.match(benchmarkText, /Source reliability/i);
    assert.match(benchmarkText, /Provenance quality ledger/i);
    assert.match(benchmarkText, /Source clustering/i);
    assert.match(benchmarkText, /Originality clusters/i);
    assert.match(benchmarkText, /Evaluation checks/i);
    assert.match(benchmarkText, /Recall@3/i);
    assert.match(benchmarkText, /headline baseline/i);
    assert.match(benchmarkText, /evidence only/i);
    assert.match(benchmarkText, /no contradiction penalty/i);
    assert.match(benchmarkText, /quality weighted/i);
    assert.match(benchmarkText, /narrativedesk tournament/i);

    await page.getByRole('button', { name: /^Report$/i }).click();
    assert.match(await page.locator('[data-testid="report-preview"]').innerText(), /NarrativeDesk Event Report: ORION/);

    await page.locator('[data-testid="case-selector"]').selectOption('EVT-AURORA-2025-10-22');
    await page.getByRole('button', { name: /^Overview$/i }).click();
    await assert.doesNotReject(async () => (
      page.getByRole('heading', { name: 'Aurora Commerce Cloud' }).waitFor()
    ));
    await page.getByRole('button', { name: /^Evidence$/i }).click();
    const auroraText = await page.locator('body').innerText();
    assert.match(auroraText, /AUR-SRC-009/);
    assert.match(auroraText, /merchant expansion/);
    assert.match(auroraText, /Blocked from ranking/i);
    await page.getByRole('button', { name: /^Report$/i }).click();
    assert.equal(
      await page.locator('[data-testid="ledger-export"]').getAttribute('download'),
      'evt-aurora-2025-10-22-ledger.json',
    );
    assert.match(await page.locator('[data-testid="ledger-export"]').getAttribute('href'), /^data:application\/json/);
    assert.equal(
      await page.locator('[data-testid="report-export"]').getAttribute('download'),
      'evt-aurora-2025-10-22-report.md',
    );

    await page.locator('[data-testid="case-selector"]').selectOption('EVT-LYRA-2025-11-13');
    await page.getByRole('button', { name: /^Overview$/i }).click();
    await assert.doesNotReject(async () => (
      page.getByRole('heading', { name: 'Lyra Security Systems' }).waitFor()
    ));
    await page.getByRole('button', { name: /^Evidence$/i }).click();
    const lyraEvidenceText = await page.locator('body').innerText();
    assert.match(lyraEvidenceText, /LYR-SRC-009/);
    await page.getByRole('button', { name: /^Validation$/i }).click();
    const lyraText = await page.locator('body').innerText();
    assert.match(lyraText, /Renewal discounting pressure/);
    assert.match(lyraText, /Future sources: LYR-SRC-009/);
    assert.match(lyraText, /Top validated\s+miss/i);
    const lyraEvaluation = await page.locator('[data-testid="evaluation-checks"]').innerText();
    assert.match(lyraEvaluation, /headline baseline[\s\S]*pass/i);
    assert.match(lyraEvaluation, /evidence only[\s\S]*miss/i);
    assert.match(lyraEvaluation, /quality weighted[\s\S]*miss/i);
    await page.getByRole('button', { name: /^Overview$/i }).click();
    const lyraThesis = await page.locator('[data-testid="event-header"]').innerText();
    assert.match(lyraThesis, /surface baseline[\s\S]*Renewal discounting pressure/i);
    assert.match(lyraThesis, /Ranked #2/i);
    assert.match(lyraThesis, /Ranked #1[\s\S]*T\+20 validated rank #2/i);
    assert.match(lyraThesis, /winning narrative[\s\S]*AI module adoption slowdown/i);
    await page.getByRole('button', { name: /^Report$/i }).click();
    assert.equal(
      await page.locator('[data-testid="ledger-export"]').getAttribute('download'),
      'evt-lyra-2025-11-13-ledger.json',
    );
    const lyraReportHref = await page.locator('[data-testid="report-export"]').getAttribute('href');
    assert.match(decodeDataHref(lyraReportHref), /NarrativeDesk Event Report: LYRA/);
    assert.doesNotMatch(decodeDataHref(lyraReportHref), /NarrativeDesk Event Report: ORION/);
    assert.doesNotMatch(decodeDataHref(lyraReportHref), /Future Validation Fixture/);
    assert.doesNotMatch(decodeDataHref(lyraReportHref), /Top-ranked narrative validated/);

    await page.setViewportSize({ width: 390, height: 1100 });
    await page.goto(baseUrl, { waitUntil: 'networkidle' });
    await page.locator('[data-testid="case-selector"]').selectOption('EVT-LYRA-2025-11-13');
    await page.getByRole('button', { name: /^Tournament$/i }).click();
    await page.locator('[data-testid="narrative-tournament"]').waitFor();
    await page.getByRole('button', { name: /^Report$/i }).click();
    const hasHorizontalOverflow = await page.evaluate(() => (
      document.documentElement.scrollWidth > window.innerWidth + 1
    ));
    assert.equal(hasHorizontalOverflow, false, 'mobile viewport should not horizontally overflow');
    await assert.doesNotReject(async () => (
      page.locator('[data-testid="export-area"]').scrollIntoViewIfNeeded()
    ));

    assert.equal(consoleErrors.length, 0, consoleErrors.join('\n'));
    console.log('Browser smoke passed: preview workbench loaded, tournament rendered, evidence interaction worked.');
  } finally {
    if (browser) await browser.close();
    if (server) server.kill('SIGTERM');
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
