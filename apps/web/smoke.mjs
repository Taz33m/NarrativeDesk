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
  const server = startPreview();
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

    assert.match(bodyText, /NarrativeDesk v0/i);
    assert.match(bodyText, /Timestamp-locked narrative replay/);
    assert.match(bodyText, /ORION/);
    assert.match(bodyText, /Forward demand slowdown/);
    assert.match(bodyText, /Margin compression/);
    assert.match(bodyText, /SRC-009/);
    assert.match(bodyText, /Validation dashboard/);
    assert.match(bodyText, /Research support only/);

    await page.getByRole('button', { name: /Margin compression/i }).click();
    const marginText = await page.locator('[data-testid="evidence-inspector"]').innerText();
    assert.match(marginText, /Gross margin improved year over year/);

    assert.equal(consoleErrors.length, 0, consoleErrors.join('\n'));
    console.log('Browser smoke passed: preview workbench loaded, tournament rendered, evidence interaction worked.');
  } finally {
    if (browser) await browser.close();
    server.kill('SIGTERM');
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
