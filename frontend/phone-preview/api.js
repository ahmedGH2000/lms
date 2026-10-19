// Offline design preview only. No Frappe API or real account/payment operations.
export const boot={user:'alex@example.invalid',full_name:'Alex Morgan',roles:[]};
const copy=v=>JSON.parse(JSON.stringify(v));
const rows=[
 ['web','Build your first web application','Web development','Beginner',0,'Bring an idea to life with routes, forms, and a small application you understand.','Maya Bennett'],
 ['vue','Vue, one component at a time','Frontend','Beginner',0,'Build a clear mental model of components, reactive state, and everyday interactions.','Leo Morgan'],
 ['api','A practical guide to API design','Backend','Intermediate',1,'Make endpoints that are predictable, useful, and a pleasure to work with.','Maya Bennett'],
 ['sql','SQL that makes sense','Databases','Beginner',0,'Ask better questions of your data, from your first SELECT to useful joins.','Alex Rivera'],
 ['tests','Write tests with confidence','Testing','Intermediate',0,'Test the behaviors that matter and make changes without second-guessing yourself.','Leo Morgan'],
 ['secure','Secure by design','Security','Advanced',1,'Work through authorization, private files, and the decisions behind safer applications.','Alex Rivera']
];
const courses=rows.map(([name,title,category,nj_difficulty,paid_course,short_introduction,teacher],i)=>({name,title,category,nj_difficulty,paid_course,short_introduction,course_price:49,currency:'USD',lessons:6,featured:i===0,instructors:[{name:teacher}],description:`<p>${short_introduction}</p><p>Start with a clear foundation, then bring everything together in a practical project. Each focused lesson helps you understand not just what to build, but why it works.</p><h3>What you’ll explore</h3><ul><li>The essential building blocks, explained clearly.</li><li>Small examples you can adapt to your own ideas.</li><li>A hands-on project to put your new skills into practice.</li></ul>`,chapters:[{name:name+'-foundations',title:'The foundations',lessons:['Start with a small idea','Understand the building blocks','Connect the pieces'].map((title,j)=>({name:name+'-'+(j+1),title,duration:420+j*120}))},{name:name+'-practice',title:'Put it into practice',lessons:['Build your first feature','Make it your own','Reflect and take the next step'].map((title,j)=>({name:name+'-'+(j+4),title,duration:540+j*90}))}]}));
const enrolled={web:33,vue:67,sql:100};
const done=new Set(['web-1','web-2','vue-1','vue-2','vue-3','vue-4',...Array.from({length:6},(_,i)=>'sql-'+(i+1))]);
const discussion={};const requests=[];
function detail(name){const c=courses.find(c=>c.name===name);if(!c)throw Error('Course not found.');return {...c,can_learn:name in enrolled,enrollment:name in enrolled?{progress:enrolled[name],current_lesson:name+'-'+(name==='web'?3:1)}:null};}
const escape=s=>s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export async function rpc(method,args={}){
 if(method==='api.catalog'){const filtered=courses.filter(c=>(!args.search||c.title.toLowerCase().includes(args.search.toLowerCase()))&&(!args.category||c.category===args.category)&&(!args.level||c.nj_difficulty===args.level));return copy({courses:filtered.slice(args.start||0,(args.start||0)+24),categories:[...new Set(courses.map(c=>c.category))],total:filtered.length});}
 if(method==='api.dashboard')return copy(courses.filter(c=>c.name in enrolled).map(c=>({...c,progress:enrolled[c.name]})));
 if(method==='api.course_detail')return copy(detail(args.course));
 if(method==='api.lesson_detail'){const c=courses.find(c=>c.chapters.some(ch=>ch.lessons.some(l=>l.name===args.lesson)));if(!c)throw Error('Lesson not found.');const l=c.chapters.flatMap(ch=>ch.lessons).find(l=>l.name===args.lesson);return copy({...l,course:c.name,private_video:true,complete:done.has(l.name),body:'## Small steps, real understanding\n\nIn this lesson, we connect the ideas you have learned and turn them into a small, working feature. Take your time, experiment, and make it your own.\n\n### Try it yourself\n\nChoose one small feature you would like to build. Write down its input, the result you expect, and one thing that could go wrong. Share your approach in the discussion below.\n\n> This is sample content for the offline design preview.',content:''});}
 if(method==='api.discussion'){if(!discussion[args.lesson])discussion[args.lesson]=[{name:'question',author:'Sam Taylor',creation:'2026-10-13 09:30:00',reply:'<p>Breaking this down into smaller steps makes it much clearer. Would you start with the form or the data model?</p>',instructor:false},{name:'reply',author:'Maya Bennett',creation:'2026-10-13 10:15:00',reply:'<p>Start with the smallest useful interaction. Sketch the form, then work out what data that interaction needs. Great question!</p>',instructor:true,nj_reply_to:'question'}];return copy(discussion[args.lesson]);}
 if(method==='api.comment'){await rpc('api.discussion',args);const row={name:'comment-'+Date.now(),author:'Alex Morgan',creation:new Date().toISOString(),reply:'<p>'+escape(args.text)+'</p>',nj_reply_to:args.reply_to};discussion[args.lesson].push(row);return {name:row.name};}
 if(method==='api.complete'){done.add(args.lesson);const id=args.lesson.split('-')[0];enrolled[id]=Math.round([...done].filter(l=>l.startsWith(id+'-')).length/6*100);return {complete:true,progress:enrolled[id]};}
 if(method==='payments.enroll'){enrolled[args.course]=0;return 'preview-enrollment';}
 if(method==='payments.requests')return copy(requests);
 if(method==='payments.request_payment'){requests.push({name:'sample-request',course:courses.find(c=>c.name===args.course).title,status:'Pending',review_note:'Preview only — nothing has been submitted.'});return {name:'sample-request',status:'Pending'};}
 throw Error('This action is available in the full LMS.');
}
export const money=c=>c.paid_course?`${c.currency||''} ${Number(c.course_price||0).toLocaleString()}`:'Free';
export const duration=n=>n?`${Math.ceil(n/60)} min`:'Lesson';
