"""Course reviews and moderation, backed by native Frappe records."""
import html
import frappe
from frappe.rate_limiter import rate_limit
from nightjar_learning.access import user, can_learn, instructor, is_admin, deny


def visible(course):
    if not frappe.db.get_value('LMS Course', course, 'published') and not instructor(course):
        deny()


@frappe.whitelist(allow_guest=True)
def reviews(course):
    visible(course)
    rows = frappe.get_all('LMS Course Review', filters={'course':course},
        fields=['name','owner','rating','review','creation','nj_response','nj_responder'],
        order_by='creation desc', limit_page_length=200)
    for row in rows:
        row.author = frappe.db.get_value('User', row.owner, 'full_name') or 'Learner'
        row.responder = frappe.db.get_value('User', row.nj_responder, 'full_name') if row.nj_responder else None
        row.is_mine = row.owner == frappe.session.user
        del row['owner']
        del row['nj_responder']
    return {'items':rows, 'can_reply': instructor(course), 'can_moderate':is_admin(),
        'can_review':can_learn(course) and not instructor(course)}


@frappe.whitelist(methods=['POST'])
@rate_limit(limit=10, seconds=60)
def review(course, rating, text):
    user()
    if not can_learn(course) or instructor(course):
        deny('Only enrolled students may review this course.')
    text = str(text or '').strip()
    if str(rating) not in ('1','2','3','4','5') or not 1 <= len(text) <= 4000:
        frappe.throw('Choose 1–5 stars and write between 1 and 4,000 characters.')
    frappe.db.get_value('LMS Course',course,'name',for_update=True)
    doc = frappe.get_doc(dict(doctype='LMS Course Review',course=course,rating=int(rating)/5,
        review=html.escape(text)))
    doc.insert(ignore_permissions=True)
    return reviews(course)


@frappe.whitelist(methods=['POST'])
def respond(review, text):
    user()
    doc = frappe.get_doc('LMS Course Review',review)
    if not instructor(doc.course):
        deny('Only the course instructor may reply to this review.')
    text = str(text or '').strip()
    if not 1 <= len(text) <= 4000:
        frappe.throw('Write between 1 and 4,000 characters.')
    # Native review validation rejects any second save; update only these server-owned fields.
    frappe.db.set_value('LMS Course Review',doc.name,{'nj_response':html.escape(text),'nj_responder':frappe.session.user})
    return reviews(doc.course)


@frappe.whitelist(methods=['POST'])
def remove(kind, name):
    user()
    if not is_admin():
        deny('Only an administrator may remove community posts.')
    if kind == 'review_reply':
        frappe.db.set_value('LMS Course Review',name,{'nj_response':None,'nj_responder':None})
    elif kind == 'review':
        frappe.delete_doc('LMS Course Review',name)
    elif kind == 'comment':
        doc = frappe.get_doc('Discussion Reply',name)
        topic = frappe.get_doc('Discussion Topic',doc.topic)
        if topic.reference_doctype != 'Course Lesson':
            deny()
        # Preserve the thread and its child links while removing the content.
        doc.reply = '<p>[Removed by administrator]</p>'
        doc.save(ignore_permissions=True)
    else:
        frappe.throw('Unknown post type.')
    return True


def validate_review(doc, method=None):
    if not is_admin():
        old = doc.get_doc_before_save()
        if doc.owner != frappe.session.user or not can_learn(doc.course):
            deny()
        if (doc.get('nj_response') or doc.get('nj_responder')) and not old:
            deny('Instructor responses must use the reply action.')
        if old and any(doc.get(k) != old.get(k) for k in ('course','owner','nj_response','nj_responder')):
            deny('Review identity and instructor response are protected.')
