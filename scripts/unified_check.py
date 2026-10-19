"""Regression checks for the unified experience. Disposable development site only."""
import json,os,secrets,re
from pathlib import Path
if os.environ.get('NJ_RUN_INTEGRATION') != '1': raise SystemExit('Requires NJ_RUN_INTEGRATION=1 and a disposable site')
bench=Path(os.environ['FRAPPE_BENCH_ROOT']).resolve()
output=Path.cwd()/'unified-test-results.json'
site=os.environ.get('NJ_TEST_SITE','nightjar.localhost')
if not site.endswith('.localhost'): raise SystemExit('Use a disposable .localhost site')
fixture_path=Path(os.environ['NJ_BROWSER_FIXTURE']).resolve()
os.chdir(bench/'sites')
import frappe
from werkzeug.test import Client
from werkzeug.wrappers import Response
from frappe.app import application
frappe.init(site=site);frappe.connect();frappe.set_user('Administrator')
from nightjar_learning.install import after_install
after_install();frappe.db.set_single_value('Website Settings','disable_signup',0);frappe.clear_cache();frappe.db.commit();frappe.destroy()
results=[]
def check(label,ok):
 results.append({'test':label,'result':'PASS' if ok else 'FAIL'});print(label,results[-1]['result'],flush=True)
 if not ok:raise AssertionError(label)
def call(c,method,args={},token=None):
 return c.post('/api/method/'+method,json=args,headers={'Host':site,**({'X-Frappe-CSRF-Token':token} if token else {})})
def boot(c):
 r=c.get('/learn',headers={'Host':site})
 return json.loads(re.search(r'<script id="nightjar-boot" type="application/json">(.*?)</script>',r.text,re.S)[1])
admin=Client(application,Response);student=Client(application,Response);other=Client(application,Response);guest=Client(application,Response)
pwd=secrets.token_urlsafe(24); email='unified-'+secrets.token_hex(5)+'@example.invalid'
try:
 r=call(guest,'nightjar_learning.accounts.register',{'email':email,'full_name':'New learner','password':pwd,'confirm_password':'wrong'})
 check('Mismatched registration passwords rejected',r.status_code!=200)
 r=call(student,'nightjar_learning.accounts.register',{'email':email,'full_name':'New learner','password':pwd,'confirm_password':pwd,'roles':['System Manager']})
 check('Student creates account without email delivery',r.status_code==200)
 r=call(student,'nightjar_learning.accounts.login',{'email':email,'password':pwd})
 check('Student signs in with chosen password',r.status_code==200 and r.json['message']['signed_in'])
 sb=boot(student);st=sb['csrf_token']
 check('Signup cannot assign administrator roles','System Manager' not in sb['roles'] and 'LMS Student' in sb['roles'])
 check('Student native LMS entry redirects to Nightjar',student.get('/lms',headers={'Host':site}).headers.get('Location')=='/learn')
 check('Login entry redirects to custom login',guest.get('/login',headers={'Host':site}).headers.get('Location')=='/learn#view=login')
 r=call(student,'nightjar_learning.accounts.save_profile',{'first_name':'Updated','last_name':'Learner','bio':'Hello'},st)
 check('Student edits own profile',r.status_code==200 and r.json['message']['first_name']=='Updated')
 check('Student cannot list other accounts',call(student,'nightjar_learning.accounts.members',{},st).status_code==403)
 check('Student cannot reset another password',call(student,'nightjar_learning.accounts.set_student_password',{'member':'Administrator','password':pwd,'confirm_password':pwd},st).status_code==403)
 check('Wrong current password rejected',call(student,'nightjar_learning.accounts.change_password',{'old_password':'wrong','password':pwd,'confirm_password':pwd},st).status_code!=200)
 student=Client(application,Response)
 r=call(student,'nightjar_learning.accounts.login',{'email':email,'password':pwd});check('Student signs in again after failed password verification',r.status_code==200 and r.json['message']['signed_in']);st=boot(student)['csrf_token']
 ap=os.environ['NJ_TEST_ADMIN_PASSWORD']
 check('Administrator custom login',call(admin,'nightjar_learning.accounts.login',{'email':'Administrator','password':ap}).status_code==200)
 at=boot(admin)['csrf_token']
 check('Administrator keeps native teaching access',admin.get('/lms',headers={'Host':site}).status_code==200)
 fixture=json.loads(fixture_path.read_text());course=fixture['free'];lesson=fixture['lesson']
 check('Unauthorized lesson remains blocked',call(student,'nightjar_learning.api.lesson_detail',{'lesson':lesson},st).status_code==403)
 check('Free enrollment',call(student,'nightjar_learning.payments.enroll',{'course':course},st).status_code==200)
 r=call(student,'nightjar_learning.community.review',{'course':course,'rating':'5','text':'Useful explanations'},st)
 check('Enrolled student posts course review',r.status_code==200)
 review=next(x['name'] for x in r.json['message']['items'] if x['is_mine'])
 check('Duplicate review rejected',call(student,'nightjar_learning.community.review',{'course':course,'rating':'4','text':'Another'},st).status_code!=200)
 check('Student cannot impersonate instructor reply',call(student,'nightjar_learning.community.respond',{'review':review,'text':'fake instructor'},st).status_code==403)
 check('Instructor replies to review',call(admin,'nightjar_learning.community.respond',{'review':review,'text':'Thank you!'},at).status_code==200)
 r=call(student,'nightjar_learning.api.comment',{'lesson':lesson,'text':'My question'},st)
 check('Student posts lesson discussion',r.status_code==200);comment=r.json['message']['name']
 check('Student replies in discussion',call(student,'nightjar_learning.api.comment',{'lesson':lesson,'text':'A follow-up','reply_to':comment},st).status_code==200)
 check('Student cannot moderate posts',call(student,'nightjar_learning.community.remove',{'kind':'comment','name':comment},st).status_code==403)
 check('Administrator removes comment preserving thread',call(admin,'nightjar_learning.community.remove',{'kind':'comment','name':comment},at).status_code==200)
 check('Administrator deletes review reply',call(admin,'nightjar_learning.community.remove',{'kind':'review_reply','name':review},at).status_code==200)
 check('Administrator deletes review',call(admin,'nightjar_learning.community.remove',{'kind':'review','name':review},at).status_code==200)
 new_email='managed-'+secrets.token_hex(5)+'@example.invalid'
 check('Administrator creates student with password',call(admin,'nightjar_learning.accounts.add_student',{'email':new_email,'full_name':'Managed learner','password':pwd,'confirm_password':pwd},at).status_code==200)
 new_pwd=secrets.token_urlsafe(24)
 check('Administrator sets student password',call(admin,'nightjar_learning.accounts.set_student_password',{'member':new_email,'password':new_pwd,'confirm_password':new_pwd},at).status_code==200)
 check('Assigned password works',call(other,'nightjar_learning.accounts.login',{'email':new_email,'password':new_pwd}).status_code==200)
 ot=boot(other)['csrf_token']
 check('Another student enrolls in same course',call(other,'nightjar_learning.payments.enroll',{'course':course},ot).status_code==200)
 check('Students can reply to each other',call(other,'nightjar_learning.api.comment',{'lesson':lesson,'text':'A peer answer','reply_to':comment},ot).status_code==200)
 check('Guest quiz read denied',call(guest,'lms.lms.utils.get_quiz_with_questions',{'quiz':'nightjar-practice-checkpoint'}).status_code in (401,403))
 check('Guest cannot list accounts',call(guest,'nightjar_learning.accounts.members').status_code in (401,403))
 check('CSRF required for authenticated mutations',call(student,'nightjar_learning.accounts.save_profile',{'first_name':'Blocked'}).status_code!=200)
 check('Profile password update',call(student,'nightjar_learning.accounts.change_password',{'old_password':pwd,'password':new_pwd,'confirm_password':new_pwd},st).status_code==200)
 check('Changed password authenticates',call(Client(application,Response),'nightjar_learning.accounts.login',{'email':email,'password':new_pwd}).status_code==200)
finally:
 output.write_text(json.dumps(results,indent=2))
