// Run against the disposable QA site used by unified_browser.cjs.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('assert/strict');
const fs = require('fs');
const base = process.env.NJ_BASE_URL || 'http://nightjar.localhost:8000';
if (process.env.NJ_RUN_INTEGRATION !== '1' || !new URL(base).hostname.endsWith('.localhost'))
  throw new Error('Use NJ_RUN_INTEGRATION=1 and a disposable .localhost site');
const results = [];
const pass = test => {results.push({test,result:'PASS'}); console.log('PASS',test)};
(async () => {
  const browser = await chromium.launch({headless:true,
    ...(process.env.CHROMIUM_PATH ? {executablePath:process.env.CHROMIUM_PATH}:{}),
    args:['--no-sandbox','--disable-gpu','--no-zygote','--host-resolver-rules=MAP nightjar.localhost 127.0.0.1']});
  try {
    const page = await browser.newPage();
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    for (let attempt=0; ; attempt++) {
      try { await page.goto(base+'/learn'); break; }
      catch (error) { if(attempt >= 39) throw error; await page.waitForTimeout(250); }
    }
    await page.locator('.course-card').first().waitFor();
    const endpoint = '**/api/method/nightjar_learning.api.catalog*';
    for (const level of ['Beginner','Intermediate','Advanced','']) {
      const response = page.waitForResponse(r => r.url().includes('api.catalog?') && new URL(r.url()).searchParams.get('level')===level);
      await page.getByLabel('Difficulty').selectOption(level);
      const r = await response; assert.equal(r.status(),200);
      const data = (await r.json()).message;
      assert(data.courses.every(c => !level || c.nj_difficulty === level));
      await page.locator('.count').filter({hasText:data.total+' courses'}).waitFor();
    }
    pass('All difficulty filters return valid results and reset successfully');
    await page.route(endpoint,r => r.fulfill({status:500,contentType:'application/json',body:JSON.stringify({exc_type:'ResponseError'})}));
    await page.getByLabel('Difficulty').selectOption('Beginner');
    await page.getByRole('heading',{name:"We couldn't load the courses."}).waitFor();
    assert.equal(await page.getByText('Your learning library starts here.',{exact:true}).count(),0);
    assert.equal(await page.locator('.count').count(),0);
    pass('Failed filter request shows service failure instead of zero courses');
    await page.unroute(endpoint);
    await page.getByRole('button',{name:'Retry loading courses'}).click();
    await page.locator('.course-card').first().waitFor();
    assert.equal(await page.getByRole('heading',{name:"We couldn't load the courses."}).count(),0);
    pass('Catalog retry restores cards and clears the error');
    await page.route(endpoint,r => r.fulfill({status:500,contentType:'application/json',body:'{}'}));
    await page.reload();
    await page.getByRole('heading',{name:"We couldn't load the courses."}).waitFor();
    assert.equal(await page.getByText('Your learning library starts here.',{exact:true}).count(),0);
    pass('Initial catalog failure does not claim the library is empty');
    await page.unroute(endpoint);
    await page.getByRole('button',{name:'Retry loading courses'}).click();
    await page.locator('.course-card').first().waitFor();
    // Force an older request to fail only after a newer filter succeeds.
    let releaseOld;
    const held = new Promise(resolve => releaseOld=resolve);
    let seenOld; const received = new Promise(resolve => seenOld=resolve);
    await page.route(endpoint,async r => {
      if(new URL(r.request().url()).searchParams.get('level')==='Beginner') {
        seenOld(); await held; await r.fulfill({status:500,contentType:'application/json',body:'{}'});
      } else await r.continue();
    });
    await page.getByLabel('Difficulty').selectOption('Beginner'); await received;
    const advanced = page.waitForResponse(r => r.url().includes('api.catalog?') && new URL(r.url()).searchParams.get('level')==='Advanced');
    await page.getByLabel('Difficulty').selectOption('Advanced'); await advanced;
    releaseOld(); await page.waitForTimeout(300);
    assert.equal(await page.getByRole('heading',{name:"We couldn't load the courses."}).count(),0);
    pass('Late failed request cannot overwrite a newer filter result');
    await page.unroute(endpoint);
    await page.getByLabel('Search courses').fill('no-matching-course-qa-78291');
    await page.getByRole('heading',{name:'No matching courses.'}).waitFor();
    await page.getByRole('button',{name:'Clear filters'}).click();
    await page.locator('.course-card').first().waitFor();
    pass('Successful empty result and clear-filters action work');
    await page.route('**/api/method/nightjar_learning.accounts.register',r=>r.fulfill({status:417,contentType:'application/json',body:JSON.stringify({_server_messages:JSON.stringify([JSON.stringify({message:"Failed to get method for command nightjar_learning.accounts.register with module has no attribute register"})])})}));
    await page.goto(base+'/learn#view=signup');
    await page.getByLabel('Full name',{exact:true}).fill('QA learner');
    await page.getByLabel('Email address').fill('qa-unsubmitted@example.invalid');
    await page.getByLabel('Password',{exact:true}).fill('Temporary-QA-only-78291');
    await page.getByLabel('Confirm password',{exact:true}).fill('Temporary-QA-only-78291');
    await page.getByRole('button',{name:'Create account',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'server update is incomplete'}).waitFor();
    assert.equal(await page.getByText(/has no attribute/).count(),0);
    pass('Missing backend method produces useful signup error without a traceback');
    const bootHtml = await page.evaluate(() => fetch('/learn').then(r => r.text()));
    assert.match(bootHtml, /"api_contract"\s*:\s*1/);
    await page.route('**/learn', r => r.fulfill({status:200,contentType:'text/html',
      body:bootHtml.replace(/"api_contract"\s*:\s*1/, '"api_contract": 0')}));
    await page.reload();
    await page.getByRole('heading',{name:'A platform update needs to finish.'}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Create account',exact:true}).count(),0);
    pass('Old backend boot blocks incompatible forms before submitting');
    assert.deepEqual(errors,[]); pass('No uncaught errors in recovery scenarios');
  } finally {
    fs.writeFileSync('recovery-browser-results.json',JSON.stringify(results,null,2));
    await browser.close();
  }
})().catch(e=>{console.error(e);process.exit(1)});
