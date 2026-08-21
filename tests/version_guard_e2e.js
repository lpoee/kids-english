const { chromium, devices } = require('playwright');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.mp3': 'audio/mpeg', '.mp4': 'video/mp4', '.jpg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp' };

function startServer(root, port) {
  return new Promise(resolve => {
    const server = http.createServer((req, res) => {
      const urlPath = req.url.split('?')[0];
      const file = path.join(root, urlPath === '/' ? 'index.html' : urlPath);
      fs.readFile(file, (err, data) => {
        if (err) { res.writeHead(404); res.end('not found'); return; }
        res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-cache' });
        res.end(data);
      });
    });
    server.listen(port, '127.0.0.1', () => resolve(server));
  });
}

(async () => {
  const port = Number(process.env.PORT || 18821);
  const server = await startServer(ROOT, port);
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROMIUM_PATH || '/opt/google/chrome/chrome',
  });
  try {
    const context = await browser.newContext({ ...devices['iPad (gen 7)'] });

    // Case 1: server version NEWER than the cached page -> guard must reload with ?v=
    {
      const page = await context.newPage();
      const newer = String(Date.now());
      await page.route('**/data/site_version.json*', route =>
        route.fulfill({ contentType: 'application/json', body: JSON.stringify({ version: newer }) }));
      await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: 'domcontentloaded' });
      await page.waitForURL(`**/?v=${newer}`, { timeout: 5000 });
      await page.waitForLoadState('domcontentloaded');
      assert.ok(page.url().includes(`?v=${newer}`), 'page must reload with cache-busting ?v= param');
      console.log('PASS: stale page self-heals via version guard');
      await page.close();
    }

    // Case 2: server version MATCHES page -> no reload loop
    {
      const page = await context.newPage();
      const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
      const current = (html.match(/SITE_VERSION\s*=\s*'([^']+)'/) || [])[1];
      assert.ok(current, 'index.html must declare SITE_VERSION');
      await page.route('**/data/site_version.json*', route =>
        route.fulfill({ contentType: 'application/json', body: JSON.stringify({ version: current }) }));
      await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(800);
      assert.ok(!page.url().includes('?v='), 'matching version must not trigger a reload');
      // Social still works end-to-end after the guard settles
      await page.locator('#mode-social').click();
      await page.waitForTimeout(150);
      assert.equal(await page.locator('#social-panel').evaluate(el => el.hidden), false);
      assert.equal(await page.locator('#phrase-panel').evaluate(el => el.hidden), true);
      console.log('PASS: matching version does not loop; Social opens');
      await page.close();
    }

    await context.close();
  } finally {
    await browser.close();
    server.close();
  }
})().catch(error => {
  console.error(error);
  process.exit(1);
});
