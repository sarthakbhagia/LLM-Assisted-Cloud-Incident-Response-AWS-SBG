const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push({ type: 'console', text: msg.text(), location: msg.location() });
    }
  });
  page.on('pageerror', error => {
    errors.push({ type: 'pageerror', message: error.message, stack: error.stack });
  });
  page.on('requestfailed', request => {
    errors.push({ type: 'requestfailed', url: request.url(), failure: request.failure() });
  });

  const urls = [
    { name: 'Service Map', url: 'http://localhost:3000/service-map' },
    { name: 'Replay Mode', url: 'http://localhost:3000/replay' }
  ];

  for (const { name, url } of urls) {
    console.log(`\n=== Testing ${name} (${url}) ===`);
    const pageErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        pageErrors.push({ type: 'console', text: msg.text(), location: msg.location() });
      }
    });
    page.on('pageerror', error => {
      pageErrors.push({ type: 'pageerror', message: error.message, stack: error.stack });
    });

    try {
      await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
      await page.waitForTimeout(3000); // Wait for any async errors
    } catch (e) {
      pageErrors.push({ type: 'navigation', error: e.message });
    }

    console.log(`Errors for ${name}:`);
    if (pageErrors.length === 0) {
      console.log('  NONE');
    } else {
      pageErrors.forEach((err, i) => {
        console.log(`  ${i + 1}. [${err.type}] ${err.text || err.message}`);
        if (err.stack) console.log(`     Stack: ${err.stack.split('\n').slice(0, 5).join('\n     ')}`);
        if (err.location) console.log(`     Location: ${JSON.stringify(err.location)}`);
      });
    }
    errors.push(...pageErrors.map(e => ({ page: name, ...e })));
  }

  await browser.close();
  
  console.log('\n=== SUMMARY ===');
  console.log(`Total errors: ${errors.length}`);
  if (errors.length > 0) {
    errors.forEach((e, i) => {
      console.log(`${i + 1}. [${e.page}] [${e.type}] ${e.text || e.message}`);
    });
  }
  
  process.exit(errors.length > 0 ? 1 : 0);
})();
