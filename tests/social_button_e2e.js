const { chromium, devices } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROMIUM_PATH || '/snap/bin/chromium',
  });
  try {
    const context = await browser.newContext({ ...devices['iPad (gen 7)'] });
    const page = await context.newPage();
    await page.route('**/data/social_dialogues.json*', async route => {
      await new Promise(resolve => setTimeout(resolve, 1200));
      await route.continue();
    });
    await page.goto(process.env.APP_URL || 'http://127.0.0.1:18765/', {
      waitUntil: 'domcontentloaded',
    });
    await page.locator('#mode-social').click();
    await page.waitForTimeout(100);
    assert.equal(
      await page.locator('#social-panel').evaluate(element => element.hidden),
      false,
      'Social panel must open immediately, even while story data is loading',
    );
    assert.equal(
      await page.locator('#phrase-panel').evaluate(element => element.hidden),
      true,
      'Cards panel must close immediately after tapping Social',
    );
    await context.close();
    console.log('PASS: Social opens immediately on iPad while data loads');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exit(1);
});
