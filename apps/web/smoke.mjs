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
    assert.match(bodyText, /Replay-safe market narrative verification/i);
    assert.match(bodyText, /Incomplete signals\. Time-locked evidence\. Historical validation\./i);
    assert.match(bodyText, /AAPL/);
    assert.match(bodyText, /Apple Inc\./);
    assert.match(bodyText, /Real-curated replay/i);
    assert.match(bodyText, /Case library/i);
    assert.match(bodyText, /Historical analogs/i);
    assert.match(bodyText, /How similar narratives validated/i);
    assert.match(bodyText, /No historical analogs are available/i);
    assert.match(bodyText, /Narrative under audit/i);
    assert.match(bodyText, /Verification score/i);
    assert.match(bodyText, /Replay timeline/i);
    assert.match(bodyText, /Replay Lock/i);
    assert.match(bodyText, /Future validation/i);
    assert.match(bodyText, /Capital return reset/);
    assert.match(bodyText, /Services mix resilience/);
    assert.match(bodyText, /Only evidence left of the lock entered ranking/i);
    const aaplThesis = await page.locator('[data-testid="event-header"]').innerText();
    assert.match(aaplThesis, /surface baseline[\s\S]*Services mix resilience/i);
    assert.match(aaplThesis, /Ranked #2/i);
    assert.match(aaplThesis, /Ranked #1 at the lock[\s\S]*T\+60 later supported replay rank #1/i);
    assert.match(aaplThesis, /Narrative under audit[\s\S]*Capital return reset/i);
    assert.match(aaplThesis, /Held out from replay scoring/i);
    assert.match(bodyText, /Provenance: real-curated replay/i);

    await page.getByRole('button', { name: /^Tournament$/i }).click();
    const bracketText = await page.locator('[data-testid="tournament-bracket"]').innerText();
    assert.match(bracketText, /NarrativeDesk Verification Bracket/i);
    assert.match(bracketText, /Head-to-head explanation audit/i);
    assert.match(bracketText, /Hardware demand pressure/i);
    await page.locator('[data-testid="narrative-tournament"]').getByRole('button', { name: /Hardware demand pressure/i }).click();
    const hardwareText = await page.locator('[data-testid="evidence-inspector"]').innerText();
    assert.match(hardwareText, /iPhone/i);

    await page.getByRole('button', { name: /^Evidence$/i }).click();
    const evidenceText = await page.locator('body').innerText();
    assert.match(evidenceText, /SEC-027/);
    assert.match(evidenceText, /Evidence Chain/i);
    assert.match(evidenceText, /Leakage audit/i);
    assert.match(evidenceText, /Replay source inventory/i);
    assert.match(evidenceText, /Citation QA/i);
    assert.match(evidenceText, /Evidence integrity checks/i);

    await page.getByRole('button', { name: /^Benchmark$/i }).click();
    const benchmarkText = await page.locator('body').innerText();
    assert.match(benchmarkText, /Benchmark corpus/i);
    assert.match(benchmarkText, /Historical analogs/i);
    assert.match(benchmarkText, /Case-index summary/i);
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
    assert.match(await page.locator('[data-testid="report-preview"]').innerText(), /NarrativeDesk Event Report: AAPL/);
    const bundleIntegrityText = await page.locator('[data-testid="bundle-integrity"]').innerText();
    assert.match(bundleIntegrityText, /Bundle Integrity/i);
    assert.match(bundleIntegrityText, /Replay integrity[\s\S]*pass/i);
    assert.match(bundleIntegrityText, /Artifact hashes[\s\S]*pass/i);
    assert.match(bundleIntegrityText, /Readiness[\s\S]*Ready To Ingest/i);
    assert.match(bundleIntegrityText, /Validation future[\s\S]*1/i);
    assert.equal(
      await page.locator('[data-testid="ledger-export"]').getAttribute('download'),
      'evt-real-aapl-2024-05-02-ledger.json',
    );
    assert.match(await page.locator('[data-testid="ledger-export"]').getAttribute('href'), /^data:application\/json/);
    assert.equal(
      await page.locator('[data-testid="report-export"]').getAttribute('download'),
      'evt-real-aapl-2024-05-02-report.md',
    );
    const reportHref = await page.locator('[data-testid="report-export"]').getAttribute('href');
    assert.match(decodeDataHref(reportHref), /NarrativeDesk Event Report: AAPL/);
    assert.doesNotMatch(decodeDataHref(reportHref), /Future Validation Fixture/);

    await page.setViewportSize({ width: 390, height: 1100 });
    await page.goto(baseUrl, { waitUntil: 'networkidle' });
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
    console.log('Browser smoke passed: preview workbench loaded, verification bracket rendered, evidence interaction worked.');
  } finally {
    if (browser) await browser.close();
    if (server) server.kill('SIGTERM');
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
