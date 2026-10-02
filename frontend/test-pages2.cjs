const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const allErrors = [];

  const incidentIds = [
    "6d2fad11-3c06-4602-81be-a1af1a6942d4",
    "eb0cc162-135b-4d8a-b12f-50e547a62879"
  ];

  for (const incidentId of incidentIds) {
    console.log('\n=== Testing /incidents/' + incidentId + ' ===');
    const page = await browser.newPage();
    
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
      await page.goto('http://localhost:3000/incidents/' + incidentId, { waitUntil: 'networkidle', timeout: 30000 });
      await page.waitForTimeout(3000);
    } catch (e) {
      pageErrors.push({ type: 'navigation', error: e.message });
    }

    console.log('Errors for /incidents/' + incidentId + ':');
    if (pageErrors.length === 0) {
      console.log('  NONE');
    } else {
      pageErrors.forEach((err, i) => {
        console.log('  ' + (i + 1) + '. [' + err.type + '] ' + (err.text || err.message));
        if (err.stack) console.log('     Stack: ' + err.stack.split('\n').slice(0, 5).join('\n     '));
      });
    }
    allErrors.push(...pageErrors.map(e => ({ page: 'incidents/' + incidentId, ...e })));
    await page.close();
  }

  console.log('\n=== Testing /replay/eb0cc162-135b-4d8a-b12f-50e547a62879 ===');
  const page2 = await browser.newPage();
  const pageErrors2 = [];
  page2.on('console', msg => {
    if (msg.type() === 'error') {
      pageErrors2.push({ type: 'console', text: msg.text(), location: msg.location() });
    }
  });
  page2.on('pageerror', error => {
    pageErrors2.push({ type: 'pageerror', message: error.message, stack: error.stack });
  });

  try {
    await page2.goto('http://localhost:3000/replay/eb0cc162-135b-4d8a-b12f-50e547a62879', { waitUntil: 'networkidle', timeout: 30000 });
    await page2.waitForTimeout(3000);
  } catch (e) {
    pageErrors2.push({ type: 'navigation', error: e.message });
  }

  console.log('Errors for /replay/eb0cc162-135b-4d8a-b12f-50e547a62879:');
  if (pageErrors2.length === 0) {
    console.log('  NONE');
  } else {
    pageErrors2.forEach((err, i) => {
      console.log('  ' + (i + 1) + '. [' + err.type + '] ' + (err.text || err.message));
      if (err.stack) console.log('     Stack: ' + err.stack.split('\n').slice(0, 5).join('\n     '));
    });
    allErrors.push(...pageErrors2.map(e => ({ page: 'replay/eb0cc162-135b-4d8a-b12f-50e547a62879', ...e })));
  }

  await browser.close();
  
  console.log('\n=== SUMMARY ===');
  console.log('Total errors: ' + allErrors.length);
  if (allErrors.length > 0) {
    allErrors.forEach((e, i) => {
      console.log((i + 1) + '. [' + e.page + '] [' + e.type + '] ' + (e.text || e.message));
    });
  }
  
  process.exit(allErrors.length > 0 ? 1 : 0);
})();
