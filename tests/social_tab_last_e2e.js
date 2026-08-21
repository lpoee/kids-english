const { chromium, devices } = require('playwright');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css' };

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
  const port = Number(process.env.PORT || 18831);
  const server = await startServer(ROOT, port);
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROMIUM_PATH || '/opt/google/chrome/chrome',
  });
  try {
    const context = await browser.newContext({ ...devices['iPad (gen 7)'] });
    // Keep the version guard quiet (matching version) so we test the layout, not the reload.
    const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
    const current = (html.match(/SITE_VERSION\s*=\s*'([^']+)'/) || [])[1];
    assert.ok(current, 'index.html must declare SITE_VERSION');
    await context.route('**/data/site_version.json*', route =>
      route.fulfill({ contentType: 'application/json', body: JSON.stringify({ version: current }) }));

    const page = await context.newPage();
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#tabs .tab', { timeout: 10000 });
    await page.waitForTimeout(400);

    // Read the rendered tab order by id/label.
    const order = await page.$$eval('#tabs > button', btns =>
      btns.map(b => (b.id === 'mode-social' ? 'Social' : (b.dataset.cat || b.textContent.trim()))));

    assert.ok(order.length > 1, 'expected multiple tabs, got: ' + order.join(','));
    assert.ok(order.includes('Social'), 'Social tab missing from rendered tabs: ' + order.join(','));
    const socialIdx = order.indexOf('Social');
    assert.equal(socialIdx, order.length - 1,
      'Social must be the LAST tab. Got order: ' + order.join(' | '));
    console.log('PASS: Social is the last tab. Order:', order.join(' | '));

    await context.close();
  } finally {
    await browser.close();
    server.close();
  }
})().catch(error => {
  console.error(error);
  process.exit(1);
});
