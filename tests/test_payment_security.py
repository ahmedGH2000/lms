"""Authorization/state regression tests against real Nightjar functions with an in-memory Frappe boundary.
Database locks/transactions and actual Frappe DocType permissions still require a live-site check.
"""
import importlib
import sys
from types import ModuleType, SimpleNamespace
from io import BytesIO
import pytest

class Attr(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__

class Denied(Exception): pass
class Invalid(Exception): pass

@pytest.fixture
def app(monkeypatch, tmp_path):
    f = ModuleType('frappe')
    f.session = Attr(user='teacher'); f.flags = Attr(); f.local = Attr()
    f.request = Attr(files={})
    roles = {'admin': ['System Manager'], 'teacher': ['Course Creator'], 'other-teacher': ['Course Creator'], 'student': ['LMS Student'], 'other-student': ['LMS Student'], 'moderator': ['Moderator'], 'disabled': ['System Manager']}
    owners = {'course-a': 'teacher', 'course-b': 'other-teacher'}
    requests = {}; enrollments = {}; queries = []
    f.PermissionError = Denied; f.DoesNotExistError = Invalid
    def throw(message, exception=Invalid): raise exception(message)
    f.throw = throw
    f.whitelist = lambda *a, **kw: lambda fn: fn
    f.get_roles = lambda member=None: roles.get(member or f.session.user, [])
    def get_value(dt, name, field, **kw):
        if dt == 'User': return name not in {'Guest', 'disabled'}
        if dt == 'LMS Course': return Attr(name=name, published=1, paid_course=1, disable_self_learning=0) if isinstance(field, list) else {'title': 'Course A', 'paid_course': 1, 'name': name}.get(field)
        if dt == 'NJ Payment Request': return requests.get(name, Attr()).get(field)
        if dt == 'LMS Enrollment': return None
    def exists(dt, filters):
        if dt == 'Course Instructor': return owners.get(filters['parent']) == filters['instructor']
        if dt == 'LMS Enrollment': return enrollments.get((filters['course'], filters['member']))
        if dt == 'NJ Payment Request':
            for name, doc in requests.items():
                if doc.course == filters['course'] and doc.member == filters['member']:
                    status = filters.get('status')
                    if (isinstance(status,list) and doc.status in status[1]) or doc.status == status: return name
        return False
    f.db = Attr(get_value=get_value, exists=exists, after_commit=Attr(add=lambda fn: None), after_rollback=Attr(add=lambda fn: None))
    def get_all(dt, **kwargs):
        queries.append((dt, kwargs))
        if dt == 'Course Instructor': return [c for c,t in owners.items() if t == kwargs['filters']['instructor']]
        return []
    f.get_all = get_all
    def get_doc(dt, name=None):
        if isinstance(dt, dict):
            doc = Attr(dt); doc.flags=Attr();doc.name='new-request'
            def insert(**kw): requests[doc.name] = doc;return doc
            doc.insert=insert
            return doc
        if dt == 'NJ Payment Request': return requests[name]
        if dt == 'LMS Course': return Attr(name=name, published=1, paid_course=1, disable_self_learning=0, course_price=30, currency='USD')
    f.get_doc = get_doc
    f.delete_doc = lambda dt, name, **kwargs: enrollments.pop(next(key for key,value in enrollments.items() if value == name))
    f.get_site_path = lambda *parts: str(tmp_path.joinpath(*parts))
    monkeypatch.setitem(sys.modules, 'frappe', f)
    for name, attrs in {
        'frappe.rate_limiter': {'rate_limit': lambda **kw: lambda fn: fn},
        'frappe.utils': {'now_datetime': lambda: 'today'},
        'frappe.model.document': {'Document': object},
        'lms.lms.doctype.lms_enrollment.lms_enrollment': {'LMSEnrollment': object},
        'frappe.website.doctype.discussion_reply.discussion_reply': {'DiscussionReply': object},
    }.items():
        module=ModuleType(name);module.__dict__.update(attrs);monkeypatch.setitem(sys.modules,name,module)
    modules={}
    for name in ['access','payments','guards','navigation','nightjar_learning.doctype.nj_payment_request.nj_payment_request']:
        fullname='nightjar_learning.'+name
        monkeypatch.delitem(sys.modules,fullname,raising=False)
        modules[name]=importlib.import_module(fullname)
    payment=modules['payments']
    def enrollment(course, member):
        doc=Attr(course=course,member=member,nj_approved_by=None,current_lesson=None,get_doc_before_save=lambda:None)
        modules['guards'].validate_enrollment(doc)
        enrollments[(course,member)]='enrollment-1'
    monkeypatch.setattr(payment,'enroll_member',enrollment)
    doc=Attr(name='request-1',course='course-a',member='student',status='Pending',flags=Attr(),reference='bank-123',receipt_key=None,receipt_name=None,save=lambda **kw:None)
    requests[doc.name]=doc
    yield Attr(f=f,p=payment,modules=modules,doc=doc,requests=requests,enrollments=enrollments,queries=queries)
    # Avoid leaking modules that captured fake Frappe into unrelated tests.
    for name in modules: sys.modules.pop('nightjar_learning.'+name,None)

@pytest.mark.parametrize('who,course,allowed',[
 ('teacher','course-a',True),('teacher','course-b',False),('other-teacher','course-a',False),
 ('student','course-a',False),('admin','course-a',True),('admin','course-b',True),
 ('moderator','course-a',False),('disabled','course-a',False),('Guest','course-a',False),
])
def test_reviewer_scope(app,who,course,allowed):
    assert bool(app.p.can_review(course,who)) == allowed

@pytest.mark.parametrize('who',['student','other-teacher','moderator','Guest','disabled'])
def test_unauthorized_decision_does_not_change_request(app,who):
    app.f.session.user=who
    with pytest.raises(Denied): app.p.decide('request-1','Approved','bank confirmed')
    assert app.doc.status == 'Pending' and not app.enrollments

def test_teacher_approval_and_revocation(app):
    app.p.decide('request-1','Approved','Bank transfer verified')
    assert app.doc.reviewed_by == 'teacher'
    assert app.enrollments[('course-a','student')] == 'enrollment-1'
    assert app.f.flags.nightjar_review_enrollment is None
    app.p.decide('request-1','Revoked','Refunded')
    assert not app.enrollments and app.doc.status == 'Revoked'
    with pytest.raises(Invalid): app.p.decide('request-1','Approved','Retry')

def test_missing_review_note_and_invalid_transition(app):
    for decision,note in [('Approved',' '),('Approved',None),('Revoked','test'),('anything','test')]:
        with pytest.raises(Invalid): app.p.decide('request-1',decision,note)
    assert app.doc.status == 'Pending'

def test_review_context_cleared_on_failed_enrollment(app,monkeypatch):
    def fail(*args): raise RuntimeError('DB failure')
    monkeypatch.setattr(app.p,'enroll_member',fail)
    with pytest.raises(RuntimeError): app.p.decide('request-1','Approved','paid')
    assert app.f.flags.nightjar_review_enrollment is None
    # Real Frappe rolls back the status save on this failed HTTP transaction.

def test_teacher_cannot_generically_enroll_other_student(app):
    app.doc.status='Approved'
    doc=Attr(course='course-a',member='student',nj_approved_by=None,current_lesson=None,get_doc_before_save=lambda:None)
    with pytest.raises(Denied): app.modules['guards'].validate_enrollment(doc)

def test_teacher_lists_only_assigned_courses(app):
    app.p.review_requests()
    assert app.queries[-1][1]['filters'] == {'course':['in',['course-a']]}
    app.f.session.user='admin';app.p.review_requests()
    assert app.queries[-1][1]['filters'] == {}
    app.f.session.user='student'
    with pytest.raises(Denied): app.p.review_requests()

def test_own_request_listing_even_for_staff(app):
    app.p.requests()
    assert app.queries[-1][1]['filters'] == {'member':'teacher'}

@pytest.mark.parametrize('who,allowed',[('student',True),('other-student',False),('teacher',True),('other-teacher',False),('admin',True),('Guest',False),('disabled',False)])
def test_receipt_download_live_authorization(app,monkeypatch,who,allowed):
    from nightjar_learning import receipts
    monkeypatch.setattr(receipts,'receipt_response',lambda doc: 'authorized receipt')
    app.f.session.user=who
    if allowed: assert app.p.receipt('request-1') == 'authorized receipt'
    else:
        with pytest.raises(Denied): app.p.receipt('request-1')

def test_blank_reference_never_creates_request(app):
    app.f.session.user='other-student'
    with pytest.raises(Invalid): app.p.request_payment('course-a','   ')
    assert len(app.requests)==1

def test_existing_request_reported_without_replacing_receipt(app):
    app.f.session.user='student'
    result=app.p.request_payment('course-a','new-reference')
    assert result['existing'] and app.doc.reference=='bank-123'

@pytest.mark.parametrize('who,target',[('teacher','/lms'),('admin','/lms'),('student','/learn#view=dashboard'),('Guest','/learn#view=dashboard')])
def test_login_landing(app,who,target):
    app.f.session.user=who
    assert app.modules['navigation'].landing_page()==target

@pytest.mark.parametrize('path',['/lms','/lms/payment-requests','/app','/app/user','/desk'])
def test_student_page_redirects(app,path):
    from werkzeug.wrappers import Response
    app.f.session.user='student'; app.f.local.request=Attr(path=path,method='GET',args={},headers={})
    response=Response('private page')
    app.modules['navigation'].after_request(response)
    assert response.status_code==302 and response.headers['Location']=='/learn' and response.data==b''

def test_receipt_storage_rollback_and_download_headers(app):
    from nightjar_learning import receipts
    callbacks=[];app.f.db.after_rollback.add=callbacks.append
    receipts.save_receipt(app.doc,('إيصال.png','image/png',b'image bytes'))
    path=receipts.receipt_path(app.doc.receipt_key)
    assert path.is_file() and (path.stat().st_mode & 0o777)==0o600
    response=receipts.receipt_response(app.doc)
    assert response.headers['Cache-Control']=='private, no-store'
    assert response.headers['Content-Disposition'].startswith('attachment;')
    response.headers['Content-Disposition'].encode('ascii')
    assert "filename*=UTF-8''" in response.headers['Content-Disposition']
    callbacks[0]();assert not path.exists()
    with pytest.raises(Denied): receipts.receipt_path('../secret')

def test_direct_receipt_url_denied(app):
    app.f.request.path='/private/files/nightjar-receipts/abc.bin'
    with pytest.raises(Denied): app.modules['navigation'].before_request()

@pytest.mark.parametrize('creating',[True,False])
def test_client_document_flags_cannot_authorize_payment_write(app,creating):
    cls=app.modules['nightjar_learning.doctype.nj_payment_request.nj_payment_request'].NJPaymentRequest
    doc=Attr(app.doc);doc.flags=Attr(nightjar_request_create=True,nightjar_review=True)
    doc.get_doc_before_save=lambda: None if creating else Attr(doc)
    doc.is_new=lambda:creating
    with pytest.raises(Denied):cls.validate(doc)


def test_native_activity_keeps_student_in_lesson(app,monkeypatch):
    from werkzeug.wrappers import Response
    app.f.session.user='student'
    checked=[];monkeypatch.setattr(app.modules['access'],'require_lesson',lambda lesson: checked.append(lesson))
    app.f.local.request=Attr(path='/lms',method='GET',args={'nightjar_lesson':'lesson-1'},headers={'Sec-Fetch-Dest':'iframe'})
    response=Response('lesson content');app.modules['navigation'].after_request(response)
    assert response.status_code==200 and checked==['lesson-1']


def test_staff_can_visit_learn_and_lms(app):
    from werkzeug.wrappers import Response
    for path in ['/learn','/lms','/app']:
        app.f.local.request=Attr(path=path,method='GET',args={},headers={})
        response=Response('page');app.modules['navigation'].after_request(response)
        assert response.status_code==200
