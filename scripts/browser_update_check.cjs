// Production-asset UI checks with API doubles; never connects to a real site.
// Requires Playwright/Chromium. Run after frontend/npm run build.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const ui=path.resolve(__dirname,'../nightjar_learning/public/ui');
const entry=JSON.parse(fs.readFileSync(path.join(ui,'.vite/manifest.json')))['index.html'].file;
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox'],...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
 const context=await browser.newContext(),page=await context.newPage();
 let role='guest',loginRole='staff',failure=false,payments=[];const errors=[];let count=0;
 const pass=s=>{count++;console.log('PASS',s)};
 page.on('pageerror',e=>errors.push(e.message));
 const course={name:'newest',title:'Build your first website',image:'/course-image.svg',short_introduction:'Practical web design, one step at a time.',category:'Web development',lessons:8,paid_course:1,course_price:30,currency:'USD',instructors:[{name:'Your teacher'}],chapters:[],description:'Learn through practice.'};
 await context.route('http://nightjar.test/**',async route=>{
  const request=route.request(),url=new URL(request.url());
  const json=d=>route.fulfill({contentType:'application/json',body:JSON.stringify({message:d})});
  if(url.pathname.startsWith('/api/method/nightjar_learning.')){
   const method=url.pathname.split('nightjar_learning.')[1];
   if(method==='api.catalog')return json({courses:[course,{...course,name:'older',title:'Older featured course',featured:1,image:'/missing.png'}],categories:['Web development'],total:2});
   if(method==='api.course_detail')return json(course);
   if(method==='api.dashboard'||method==='payments.requests')return json([]);
   if(method==='community.reviews')return json({items:[],total:0,average:0});
   if(method==='accounts.register')return json({created:true});
   if(method==='accounts.login'){role=loginRole;return json({signed_in:true,landing_page:role==='staff'?'/lms':'/learn#view=dashboard'});}
   if(method==='payments.request_payment'){
    payments.push({body:request.postData(),headers:request.headers()});
    if(failure)return route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({_server_messages:JSON.stringify([JSON.stringify({message:'This image could not be read.'})])})});
    return json({name:'request-1',status:'Pending'});
   }
   return json({});
  }
  if(url.pathname==='/lms')return route.fulfill({contentType:'text/html',body:'<h1>LMS destination</h1>'});
  if(url.pathname==='/course-image.svg')return route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500"><rect width="800" height="500" fill="#28596c"/><circle cx="400" cy="250" r="130" fill="#d5dfd8"/><text x="400" y="265" text-anchor="middle" font-size="40">WEB DESIGN</text></svg>'});
  if(url.pathname.startsWith('/assets/nightjar_learning/ui/')){
   const filename=path.resolve(ui,url.pathname.slice('/assets/nightjar_learning/ui/'.length));
   if(!filename.startsWith(ui+path.sep)||!fs.existsSync(filename))return route.fulfill({status:404,body:''});
   return route.fulfill({contentType:{'.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.woff':'font/woff'}[path.extname(filename)]||'application/octet-stream',body:fs.readFileSync(filename)});
  }
  if(url.pathname!=='/learn')return route.fulfill({status:404,body:''});
  const boot={api_contract:2,user:role==='guest'?'Guest':role+'@example.invalid',roles:role==='staff'?['Course Creator']:[],csrf_token:'test-token',full_name:'Test Learner'};
  return route.fulfill({contentType:'text/html',body:`<!DOCTYPE html><html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/assets/nightjar_learning/ui/index.css"><body><script id="nightjar-boot" type="application/json">${JSON.stringify(boot)}</script><div id="app"></div><script type="module" src="/assets/nightjar_learning/ui/${entry}"></script></body></html>`});
 });
 try{
  await page.goto('http://nightjar.test/learn');await page.locator('.featured-course-image').waitFor();
  assert.equal(await page.locator('.featured-course-image').getAttribute('src'),'/course-image.svg');assert.equal(await page.locator('.featured h2').textContent(),'Build your first website');pass('Newest course shows its real thumbnail');
  await page.locator('.course-card').nth(1).locator('.art-symbol').waitFor();pass('Broken image has fallback');
  for(const width of [320,390,768,1440]){await page.setViewportSize({width,height:900});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}pass('Catalog fits phone, tablet and desktop');
  if(process.env.NJ_SCREENSHOTS){fs.mkdirSync(process.env.NJ_SCREENSHOTS,{recursive:true});await page.screenshot({path:path.join(process.env.NJ_SCREENSHOTS,'catalog.png'),fullPage:true});}
  await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await page.locator('.intro-side svg').evaluate(e=>getComputedStyle(e).animationName),'none');pass('Reduced motion disables animation');
  await page.goto('http://nightjar.test/learn#view=signup');await page.getByLabel('Full name').fill('Test Learner');await page.getByLabel('Email address').fill('test@example.invalid');await page.getByLabel('Password',{exact:true}).fill('A-strong-test-password!');await page.getByLabel('Confirm password').fill('A-strong-test-password!');await page.getByRole('button',{name:'Create account',exact:true}).click();
  await page.waitForURL('**#view=login');await page.getByText('Your account is ready. Sign in with your email and password.',{exact:true}).waitFor();assert.equal(await page.getByLabel('Email address').inputValue(),'test@example.invalid');assert.equal(await page.getByLabel('Password',{exact:true}).inputValue(),'');pass('Signup redirects to sign-in with confirmation and cleared password');
  await page.getByLabel('Password',{exact:true}).fill('A-strong-test-password!');await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL('**/lms');pass('Staff lands on LMS');
  role='guest';loginRole='student';await page.goto('http://nightjar.test/learn#view=login');await page.getByLabel('Email address').fill('test@example.invalid');await page.getByLabel('Password',{exact:true}).fill('A-strong-test-password!');await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL('**/learn#view=dashboard');await page.waitForLoadState('networkidle');pass('Student lands on Learn');
  await page.goto('http://nightjar.test/learn#course=newest');await page.getByRole('button',{name:'Request enrollment',exact:true}).click();const dialog=page.getByRole('dialog');await dialog.waitFor();await page.setViewportSize({width:390,height:844});assert(await dialog.evaluate(e=>{const r=e.getBoundingClientRect();return r.width<=innerWidth&&r.height<=innerHeight}));pass('Receipt dialog fits phone');
  await page.getByLabel('Receipt (optional)').setInputFiles({name:'receipt.svg',mimeType:'image/svg+xml',buffer:Buffer.from('<svg/>')});await dialog.getByText('Choose one JPG, PNG, or PDF receipt no larger than 10 MB.').waitFor();assert.equal(await page.getByLabel('Receipt (optional)').inputValue(),'');pass('Invalid attachment rejected');
  await page.getByRole('button',{name:'Send for verification'}).click();assert.equal(payments.length,0);pass('Payment text required');
  await page.getByLabel('Payment details (required)').fill('Bank transfer 123, paid today');await page.getByLabel('Receipt (optional)').setInputFiles({name:'receipt.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-test-fixture')});failure=true;await page.getByRole('button',{name:'Send for verification'}).click();await dialog.getByText('This image could not be read.').waitFor();assert.equal(await page.getByLabel('Payment details (required)').inputValue(),'Bank transfer 123, paid today');assert((await page.getByLabel('Receipt (optional)').inputValue()).includes('receipt.pdf'));pass('Failed request preserves form');
  if(process.env.NJ_SCREENSHOTS)await page.screenshot({path:path.join(process.env.NJ_SCREENSHOTS,'receipt-phone.png'),fullPage:true});
  failure=false;await page.getByRole('button',{name:'Send for verification'}).click();await dialog.waitFor({state:'hidden'});const last=payments.at(-1);assert(last.headers['content-type'].startsWith('multipart/form-data; boundary='));assert.equal(last.headers['x-frappe-csrf-token'],'test-token');assert(last.body.includes('name="reference"')&&last.body.includes('name="receipt"; filename="receipt.pdf"'));pass('Text and receipt sent together with CSRF token');
  await page.getByRole('button',{name:'Request enrollment',exact:true}).click();await page.getByLabel('Payment details (required)').fill('Text-only transfer');await page.getByRole('button',{name:'Send for verification'}).click();await dialog.waitFor({state:'hidden'});assert(!payments.at(-1).body.includes('name="receipt"'));pass('Text-only request works');
  assert.deepEqual(errors,[]);pass('No uncaught browser errors');console.log(`${count} checks passed (mock APIs, no real database).`);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
