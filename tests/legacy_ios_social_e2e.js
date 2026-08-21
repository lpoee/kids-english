// Legacy iOS (Safari 13.0) compatibility: Social tab must open on a plain tap
// even before the async social-player module has loaded, and the module source
// must be free of post-iOS-13.0 syntax (?. ?? replaceChildren) that would
// make the module fail to parse on older iPads.
const { chromium, devices } = require('playwright');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.mp3': 'audio/mpeg', '.mp4': 'video/mp4', '.jpg': 'image/jpeg', '.png': 'image/png' };

function startServer(root, port, slowModule) {
  return new Promise(resolve => {
    const server = http.createServer((req, res) => {
      const urlPath = req.url.split('?')[0];
      const file = path.join(root, urlPath === '/' ? 'index.html' : urlPath);
      fs.readFile(file, (err, data) => {
        if (err) { res.writeHead(404); res.end('not found'); return; }
        res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-cache' });
        if (slowModule && urlPath === '/assets/social-player.js') {
          setTimeout(() => res.end(data), 1500); // simulate slow network
        } else {
          res.end(data);
        }
      });
    });
    server.listen(port, '127.0.0.1', () => resolve(server));
  });
}

(async () => {
  // ── Static check: module source must be iOS 13.0-safe ──
  const src = fs.readFileSync(path.join(ROOT, 'assets/social-player.js'), 'utf8');
  assert.ok(!src.includes('?.'), 'social-player.js must not use optional chaining ?. (iOS 13.1+)');
  assert.ok(!/\?\?/.test(src), 'social-player.js must not use nullish coalescing ?? (iOS 13.1+)');
  assert.ok(!src.includes('replaceChildren'), 'social-player.js must not use replaceChildren (iOS 14+)');
  console.log('PASS: social-player.js is iOS 13.0 syntax-safe');

  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || '/opt/google/chrome/chrome' });

  // ── Case 1: slow module — tap Social immediately; inline handler must open panel ──
  {
    const port = 18831;
    const server = await startServer(ROOT, port, true);
    const context = await browser.newContext({ ...devices['iPad (gen 7)'] });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(String(e)));
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: 'domcontentloaded' });
    // Tap immediately — module still loading (1.5s delay)
    await page.locator('#mode-social').click();
    await page.waitForTimeout(200);
    assert.equal(await page.locator('#social-panel').evaluate(el => el.hidden), false, 'Social panel must open on immediate tap (before module loads)');
    assert.equal(await page.locator('#phrase-panel').evaluate(el => el.hidden), true, 'Cards panel must hide on immediate tap');
    assert.deepEqual(errors, [], 'no page errors: ' + errors.join('; '));
    console.log('PASS: immediate tap opens Social before the module loads (slow network)');
    await context.close();
    server.close();
  }

  // ── Case 2: normal load — full flow: module takes over, story renders, no double-toggle ──
  {
    const port = 18832;
    const server = await startServer(ROOT, port, false);
    const context = await browser.newContext({ ...devices['iPad (gen 7)'] });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(String(e)));
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: 'load' });
    await page.waitForFunction(() => window.__keSocialReady === true, null, { timeout: 10000 });
    await page.locator('#mode-social').click();
    await page.waitForTimeout(300);
    assert.equal(await page.locator('#social-panel').evaluate(el => el.hidden), false, 'Social panel open after module ready');
    // First story's start turn is a "watch" turn: no speaker, text falls back.
    // This verifies the ?? replacement (text fallback) works.
    assert.equal(await page.locator('#social-speaker').textContent(), '', 'no speaker on setup turn');
    assert.equal(await page.locator('#social-text').textContent(), 'Watch what is happening.', 'text fallback on setup turn');
    // Advance within the story via Continue: speaker must render
    // (character lookup via `character ? character.name : ''`)
    await page.locator('#social-choices button.continue').click();
    await page.waitForTimeout(200);
    const speaker = (await page.locator('#social-speaker').textContent()).trim();
    assert.ok(speaker.length > 0, 'story speaker rendered on spoken turn, got: ' + speaker);
    // Back to Cards via mode-phrases, then Social again — no stuck state
    await page.locator('#mode-phrases').click();
    await page.waitForTimeout(150);
    assert.equal(await page.locator('#phrase-panel').evaluate(el => el.hidden), false, 'Cards panel restores');
    await page.locator('#mode-social').click();
    await page.waitForTimeout(150);
    assert.equal(await page.locator('#social-panel').evaluate(el => el.hidden), false, 'Social reopens');
    assert.deepEqual(errors, [], 'no page errors: ' + errors.join('; '));
    console.log('PASS: module-ready flow renders story; Cards/Social switching stable');
    await context.close();
    server.close();
  }

  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
