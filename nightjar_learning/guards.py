import frappe
from lms.lms.doctype.lms_enrollment.lms_enrollment import LMSEnrollment
from frappe.website.doctype.discussion_reply.discussion_reply import DiscussionReply
from nightjar_learning.access import is_admin, approved, can_learn, require_lesson, deny


class Enrollment(LMSEnrollment):
    def validate_course_enrollment_eligibility(self):
        row = frappe.db.get_value(
            "LMS Course",
            self.course,
            ["published", "disable_self_learning", "paid_course"],
            as_dict=True,
        )
        if not row:
            deny()
        if not is_admin() and (not row.published or row.disable_self_learning):
            deny("Course enrollment is closed.")
        if (
            row.paid_course
            and not is_admin()
            and not approved(self.course, self.member)
        ):
            deny("Payment approval is required.")


def validate_enrollment(doc, method=None):
    old = doc.get_doc_before_save()
    if old:
        if any(
            doc.get(k) != old.get(k)
            for k in (
                "member",
                "course",
                "payment",
                "enrollment_from_batch",
                "nj_approved_by",
            )
        ):
            deny("Enrollment identity is immutable.")
    elif is_admin():
        doc.nj_approved_by = frappe.session.user
    elif doc.member != frappe.session.user or doc.nj_approved_by:
        deny("You may only enroll yourself.")
    if (
        doc.current_lesson
        and frappe.db.get_value("Course Lesson", doc.current_lesson, "course")
        != doc.course
    ):
        deny("Resume lesson belongs to another course.")
    if not is_admin():
        if doc.member != frappe.session.user:
            deny()
        if frappe.db.get_value(
            "LMS Course", doc.course, "paid_course"
        ) and not approved(doc.course, doc.member):
            deny("Payment approval is required.")


def validate_payment(doc, method=None):
    if not is_admin() and not getattr(frappe.flags, "nightjar_verified_gateway", False):
        deny("A trusted server adapter or administrator must verify payments.")
    old = doc.get_doc_before_save()
    if old and any(
        doc.get(k) != old.get(k)
        for k in (
            "member",
            "payment_for_document_type",
            "payment_for_document",
            "amount",
            "currency",
        )
    ):
        deny("Payment identity is immutable.")


def validate_progress(doc, method=None):
    if not is_admin() and doc.member != frappe.session.user:
        deny("Progress belongs to the signed-in student.")
    old = doc.get_doc_before_save()
    if old and any(doc.get(k) != old.get(k) for k in ("member", "course", "lesson")):
        deny("Progress identity is immutable.")
    course = require_lesson(doc.lesson)
    if doc.get("course") and doc.course != course:
        deny("Wrong course for lesson.")


def own_record(doc, ptype="read", user=None):
    user = user or frappe.session.user
    return is_admin(user) or (user != "Guest" and doc.member == user)


def own_query(doctype, user=None):
    user = user or frappe.session.user
    return "" if is_admin(user) else f"`tab{doctype}`.member = {frappe.db.escape(user)}"


def enrollment_query(user=None):
    return own_query("LMS Enrollment", user)


def progress_query(user=None):
    return own_query("LMS Course Progress", user)


def watch_query(user=None):
    return own_query("LMS Video Watch Duration", user)


def payment_query(user=None):
    return own_query("LMS Payment", user)


def topic_for(doc):
    return (
        frappe.get_doc("Discussion Topic", doc.topic)
        if doc.doctype == "Discussion Reply"
        else doc
    )


def discussion_permission(doc, ptype="read", user=None):
    topic = topic_for(doc)
    member = user or frappe.session.user
    if topic.reference_doctype != "Course Lesson":
        return True
    if not can_learn(
        frappe.db.get_value("Course Lesson", topic.reference_docname, "course"), member
    ):
        return False
    return (
        ptype in {"read", "select", "create"} or is_admin(member) or doc.owner == member
    )


def validate_discussion(doc, method=None):
    old = doc.get_doc_before_save()
    if old and any(
        doc.get(k) != old.get(k)
        for k in ("topic", "reference_doctype", "reference_docname", "owner")
    ):
        deny("Discussion identity is immutable.")
    topic = topic_for(doc)
    if topic.reference_doctype != "Course Lesson":
        return
    require_lesson(topic.reference_docname)
    if not old and not is_admin():
        doc.owner = frappe.session.user
    if (
        doc.get("nj_reply_to")
        and frappe.db.get_value("Discussion Reply", doc.nj_reply_to, "topic")
        != doc.topic
    ):
        deny("Reply must belong to this lesson.")


def topic_query(user=None):
    user = user or frappe.session.user
    if is_admin(user):
        return ""
    u = frappe.db.escape(user)
    return f"""(`tabDiscussion Topic`.reference_doctype != 'Course Lesson' OR EXISTS (
        SELECT 1 FROM `tabCourse Lesson` l JOIN `tabLMS Course` c ON c.name=l.course
        WHERE l.name=`tabDiscussion Topic`.reference_docname AND (
        EXISTS (SELECT 1 FROM `tabCourse Instructor` i WHERE i.parent=c.name AND i.parenttype='LMS Course' AND i.instructor={u})
        OR (c.published=1 AND EXISTS (SELECT 1 FROM `tabLMS Enrollment` e WHERE e.course=c.name AND e.member={u}
        AND (c.paid_course=0 OR COALESCE(e.nj_approved_by,'') != ''
        OR EXISTS (SELECT 1 FROM `tabNJ Payment Request` r WHERE r.course=c.name AND r.member={u} AND r.status='Approved')
        OR EXISTS (SELECT 1 FROM `tabLMS Payment` p WHERE p.payment_for_document_type='LMS Course' AND p.payment_for_document=c.name AND p.member={u} AND p.payment_received=1 AND p.payment_for_certificate=0)))))))"""


def reply_query(user=None):
    q = topic_query(user)
    return (
        ""
        if not q
        else f"EXISTS (SELECT 1 FROM `tabDiscussion Topic` WHERE `tabDiscussion Topic`.name=`tabDiscussion Reply`.topic AND {q})"
    )


class PrivateDiscussionReply(DiscussionReply):
    def _private(self):
        return (
            frappe.db.get_value("Discussion Topic", self.topic, "reference_doctype")
            == "Course Lesson"
        )

    def on_update(self):
        if not self._private():
            super().on_update()

    def after_insert(self):
        if not self._private():
            super().after_insert()

    def after_delete(self):
        if not self._private():
            super().after_delete()


@frappe.whitelist(allow_guest=True)
def get_lesson(course, chapter, lesson):
    from lms.lms.utils import get_lesson as original

    ch = frappe.db.get_value(
        "Chapter Reference", {"parent": course, "idx": chapter}, "chapter"
    )
    name = (
        frappe.db.get_value("Lesson Reference", {"parent": ch, "idx": lesson}, "lesson")
        if ch
        else None
    )
    if not name or not frappe.db.get_value("Course Lesson", name, "include_in_preview"):
        require_lesson(name)
    return original(course, chapter, lesson)


@frappe.whitelist(methods=["POST"])
def save_progress(lesson, course, scorm_details=None):
    from lms.lms.doctype.course_lesson.course_lesson import save_progress as original

    if require_lesson(lesson) != course:
        deny()
    return original(lesson, course, scorm_details)


def lesson_permission(doc, ptype="read", user=None):
    from nightjar_learning.access import instructor

    member = user or frappe.session.user
    if ptype not in {"read", "select", "print"}:
        return instructor(doc.course, member)
    if doc.include_in_preview and frappe.db.get_value(
        "LMS Course", doc.course, "published"
    ):
        return True
    return can_learn(doc.course, member)


def lesson_query(user=None):
    # Apply the same paid-entitlement predicate as discussion list queries.
    q = topic_query(user)
    if not q:
        return ""
    start = q.index("EXISTS (")
    body = q[start:-1].replace(
        "l.name=`tabDiscussion Topic`.reference_docname",
        "l.name=`tabCourse Lesson`.name",
    )
    return (
        "((`tabCourse Lesson`.include_in_preview=1 AND EXISTS (SELECT 1 FROM `tabLMS Course` pc WHERE pc.name=`tabCourse Lesson`.course AND pc.published=1)) OR "
        + body
        + ")"
    )


@frappe.whitelist(allow_guest=True)
def serve_resource(file_url):
    from urllib.parse import unquote
    from lms.lms.doctype.course_lesson.course_lesson import (
        _resolve_lesson_references,
        serve_resource as original,
    )
    from nightjar_learning.access import instructor

    allowed = False
    for name, staff_only in _resolve_lesson_references(unquote(file_url)):
        lesson = frappe.get_doc("Course Lesson", name)
        if instructor(lesson.course) or (not staff_only and lesson_permission(lesson)):
            allowed = True
            break
    if not allowed:
        deny()
    return original(file_url)
