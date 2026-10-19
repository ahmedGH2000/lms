// Disposable local test site only; run via the local QA harness.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('fs'),assert=require('assert/strict'),crypto=require('crypto');
const root=process.cwd(),base=process.env.NJ_BASE_URL || 'http://nightjar.localhost:8000',results=[];
const pass=test=>{results.push({test,result:'PASS'});console.log('PASS',test)};
if(process.env.NJ_RUN_INTEGRATION !== '1' || !new URL(base).hostname.endsWith('.localhost')) throw new Error('Use NJ_RUN_INTEGRATION=1 and a disposable .localhost site');
if(!process.env.NJ_TEST_ADMIN_PASSWORD || !process.env.NJ_BROWSER_FIXTURE) throw new Error('Set NJ_TEST_ADMIN_PASSWORD and NJ_BROWSER_FIXTURE');
(async()=>{
 const browser=await chromium.launch({...(process.env.CHROMIUM_PATH ? {executablePath:process.env.CHROMIUM_PATH} : {}),headless:true,args:['--no-sandbox','--disable-gpu','--no-zygote','--host-resolver-rules=MAP nightjar.localhost 127.0.0.1']});
 const ctx=await browser.newContext();const page=await ctx.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
 for(let n=0;n<40;n++){try{await page.goto(base+'/learn');break}catch{await new Promise(r=>setTimeout(r,250))}}
 await page.getByRole('heading',{name:'Find your next skill'}).waitFor();
 for(const width of [320,390,768,1024,1440]){await page.setViewportSize({width,height:950});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));pass('Catalog fits '+width+'px')}
 await page.screenshot({path:root+'/unified-desktop.png',fullPage:true});
 await page.goto(base+'/learn#view=signup');await page.getByRole('heading',{name:'Create your account'}).waitFor();
 const email='browser-'+crypto.randomBytes(5).toString('hex')+'@example.invalid',pwd=crypto.randomBytes(20).toString('base64url');
 await page.getByLabel('Full name',{exact:true}).fill('Browser Student');await page.getByLabel('Email address').fill(email);await page.getByLabel('Password',{exact:true}).fill(pwd);await page.getByLabel('Confirm password',{exact:true}).fill(pwd);await page.getByRole('button',{name:'Create account',exact:true}).click();await page.getByRole('status').filter({hasText:'Your account is ready'}).waitFor();pass('Signup with chosen password');
 await page.goto(base+'/learn#view=login');await page.getByLabel('Email address').fill(email);await page.getByLabel('Password',{exact:true}).fill(pwd);await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL('**#view=dashboard');await page.getByRole('heading',{name:/Keep going/}).waitFor();pass('Custom student login and dashboard');
 await page.goto(base+'/learn#view=profile');await page.getByLabel('First name',{exact:true}).fill('Updated');await page.getByRole('button',{name:'Save profile'}).click();await page.getByRole('status').filter({hasText:'Profile saved'}).waitFor();pass('Custom profile save');
 await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:root+'/unified-mobile-profile.png',fullPage:true});pass('Profile fits phone');
 const fixture=JSON.parse(fs.readFileSync(process.env.NJ_BROWSER_FIXTURE));
 await page.goto(base+'/learn#course='+fixture.free);await page.getByRole('button',{name:'Enroll for free'}).click();await page.getByRole('heading',{name:/Lesson discussion/}).waitFor();
 await page.getByPlaceholder('What’s on your mind?').fill('Can you explain this step? '+email);await page.getByRole('button',{name:'Post comment',exact:true}).click();await page.getByText('Can you explain this step? '+email,{exact:true}).waitFor();pass('Enrollment and lesson comment stay in Nightjar');
 await page.getByRole('button',{name:'Mark as complete',exact:true}).click();await page.getByRole('button',{name:'✓ Lesson completed',exact:true}).waitFor();pass('Progress completion');
 await page.goto(base+'/learn#course='+fixture.free);await page.getByLabel('Your review',{exact:true}).fill('A clear and useful course. '+email);await page.getByRole('button',{name:'Post review',exact:true}).click();await page.getByText('A clear and useful course. '+email,{exact:true}).waitFor();pass('Student course review');
 await page.goto(base+'/learn#course='+fixture.free+'&lesson='+fixture.activity);
 const activity=page.frameLocator('#lesson-activity');await activity.getByRole('heading',{name:'Practice checkpoint',exact:true}).waitFor();await activity.getByRole('heading',{name:'Nightjar practice checkpoint',exact:true}).waitFor();pass('Native quiz renders inside Nightjar lesson');
 await activity.getByRole('button',{name:'Start Quiz',exact:true}).click();await activity.getByRole('radio',{name:'HTTPS',exact:true}).check();await activity.getByRole('button',{name:'Submit',exact:true}).click();await activity.getByRole('dialog').getByRole('button',{name:'Submit',exact:true}).click();await activity.getByText('100%',{exact:false}).first().waitFor();pass('Student completes native quiz inside Nightjar');
 await page.goto(base+'/lms');await page.waitForURL('**/learn');pass('Old student LMS link routes into Nightjar');
 await page.goto(base+'/learn#view=profile');await page.getByLabel('Current password',{exact:true}).fill(pwd);await page.getByLabel('New password',{exact:true}).fill(pwd+'new');await page.getByLabel('Confirm new password',{exact:true}).fill(pwd+'new');await page.getByRole('button',{name:'Save password',exact:true}).click();await page.getByRole('status').filter({hasText:'Password changed'}).waitFor();pass('Password change refreshes authenticated profile');await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.waitForURL('**/learn');pass('Custom logout');
 const admin=await browser.newContext(),ap=await admin.newPage();ap.on('pageerror',e=>errors.push(e.message));
 await ap.goto(base+'/learn#view=login');await ap.getByLabel('Email address').fill('Administrator');
 await ap.getByLabel('Password',{exact:true}).fill(process.env.NJ_TEST_ADMIN_PASSWORD);await ap.getByRole('button',{name:'Sign in',exact:true}).click();await ap.waitForURL('**#view=dashboard');await ap.getByRole('heading',{name:/Keep going/}).waitFor();pass('Administrator uses same custom login');
 await ap.goto(base+'/learn#view=members');await ap.getByRole('heading',{name:'Students',exact:true}).waitFor();await ap.getByRole('button',{name:'Add student',exact:true}).click();await ap.getByLabel('Full name',{exact:true}).fill('Managed Browser');await ap.getByLabel('Email',{exact:true}).fill('managed-browser-'+crypto.randomBytes(4).toString('hex')+'@example.invalid');await ap.getByLabel('New password',{exact:true}).fill(pwd);await ap.getByLabel('Confirm password',{exact:true}).fill(pwd);await ap.getByRole('button',{name:'Save account',exact:true}).click();await ap.getByRole('status').filter({hasText:'Account saved'}).waitFor();pass('Administrator creates student in Nightjar');
 await ap.goto(base+'/learn#course='+fixture.free);const card=ap.locator('.review-card').filter({hasText:'A clear and useful course. '+email});await card.getByLabel('Reply as instructor').fill('Glad it helped.');await card.getByRole('button',{name:'Post instructor reply'}).click();await card.getByText('Glad it helped.',{exact:true}).waitFor();pass('Instructor reply displayed on course review');
 ap.on('dialog',d=>d.accept());await card.getByRole('button',{name:'Delete reply',exact:true}).click();await card.getByText('Glad it helped.',{exact:true}).waitFor({state:'hidden'});pass('Administrator deletes review reply');
 await ap.goto(base+'/learn#course='+fixture.free+'&lesson='+fixture.lesson);const comment=ap.locator('.comment').filter({hasText:'Can you explain this step? '+email}).last();await comment.getByRole('button',{name:'Delete comment',exact:true}).click();await comment.getByText('Can you explain this step? '+email,{exact:true}).waitFor({state:'hidden'});pass('Administrator moderates lesson discussion');
 assert.deepEqual(errors,[]);pass('No uncaught browser errors');
 }finally{fs.writeFileSync(root+'/unified-browser-results.json',JSON.stringify(results,null,2));await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
