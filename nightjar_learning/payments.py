import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import now_datetime
from nightjar_learning.access import user, is_admin, is_staff, instructor, deny, approved


def can_review(course, member=None):
    member = member or frappe.session.user
    return is_staff(member) and instructor(course, member)


def require_reviewer(course):
    user()
    if not can_review(course):
        deny("You can only review requests for courses you teach.")


def enroll_member(course, member):
    frappe.db.get_value("LMS Course", course, "name", for_update=True)
    existing = frappe.db.exists("LMS Enrollment", {"course": course, "member": member})
    if existing:
        return existing
    return (
        frappe.get_doc(
            {
                "doctype": "LMS Enrollment",
                "course": course,
                "member": member,
                "member_type": "Student",
            }
        )
        .insert(ignore_permissions=True)
        .name
    )


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=20, seconds=60)
def enroll(course):
    member = user()
    row = frappe.get_doc("LMS Course", course)
    if not row.published or row.disable_self_learning:
        deny("This course is not open for enrollment.")
    if row.paid_course and not approved(course, member):
        deny("Payment approval is required.")
    return enroll_member(course, member)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=5, seconds=60)
def request_payment(course, reference):
    member = user()
    frappe.db.get_value("LMS Course", course, "name", for_update=True)
    row = frappe.get_doc("LMS Course", course)
    if not row.published or not row.paid_course or row.disable_self_learning:
        deny()
    reference = str(reference or "").strip()
    if not 3 <= len(reference) <= 140:
        frappe.throw("Enter a payment reference of 3–140 characters.")
    if frappe.db.exists("LMS Enrollment", {"course": course, "member": member}):
        frappe.throw("You are already enrolled.")
    existing = frappe.db.exists(
        "NJ Payment Request",
        {"course": course, "member": member, "status": ["in", ["Pending", "Approved"]]},
    )
    if existing:
        return {
            "name": existing,
            "existing": True,
            "status": frappe.db.get_value("NJ Payment Request", existing, "status"),
        }
    from nightjar_learning.receipts import read_upload, save_receipt
    upload = read_upload()
    doc = frappe.get_doc(
        {
            "doctype": "NJ Payment Request",
            "course": course,
            "member": member,
            "reference": reference,
            "amount": row.course_price,
            "currency": row.currency,
            "status": "Pending",
        }
    )
    if upload:
        save_receipt(doc, upload)
    previous_create = getattr(frappe.flags, "nightjar_payment_create", None)
    frappe.flags.nightjar_payment_create = (course, member)
    try:
        doc.insert(ignore_permissions=True)
    except Exception:
        if upload:
            from nightjar_learning.receipts import remove_receipt
            remove_receipt(doc.receipt_key)
        raise
    finally:
        frappe.flags.nightjar_payment_create = previous_create
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist(methods=["POST"])
def decide(request, decision, note=""):
    user()
    course = frappe.db.get_value("NJ Payment Request", request, "course")
    if not course:
        deny()
    require_reviewer(course)
    frappe.db.get_value("LMS Course", course, "name", for_update=True)
    frappe.db.get_value("NJ Payment Request", request, "name", for_update=True)
    doc = frappe.get_doc("NJ Payment Request", request)
    if doc.status == decision:
        return {"status": decision}
    if decision not in {
        "Pending": {"Approved", "Rejected"},
        "Approved": {"Revoked"},
    }.get(doc.status, set()):
        frappe.throw(
            "Invalid transition. A new request is needed after rejection or revocation."
        )
    note = str(note or "").strip()
    if not note:
        frappe.throw("Record how you verified the payment or why it was rejected.")
    doc.status = decision
    doc.review_note = note[:1000]
    doc.reviewed_by = frappe.session.user
    doc.reviewed_at = now_datetime()
    previous_review = getattr(frappe.flags, "nightjar_payment_review", None)
    frappe.flags.nightjar_payment_review = (doc.name, decision)
    try:
        doc.save(ignore_permissions=True)
    finally:
        frappe.flags.nightjar_payment_review = previous_review
    # A narrow server-only context lets the existing enrollment hook accept
    # this reviewed student without granting instructors generic enrollment rights.
    previous = getattr(frappe.flags, 'nightjar_review_enrollment', None)
    frappe.flags.nightjar_review_enrollment = (doc.course, doc.member)
    try:
        if decision == "Approved":
            enroll_member(doc.course, doc.member)
        if decision == "Revoked":
            name = frappe.db.exists("LMS Enrollment", {"course": doc.course, "member": doc.member})
            if name:
                frappe.delete_doc("LMS Enrollment", name, ignore_permissions=True)
    finally:
        frappe.flags.nightjar_review_enrollment = previous
    return {"status": decision}


@frappe.whitelist()
def requests():
    member = user()
    fields = [
        "name",
        "course",
        "amount",
        "currency",
        "status",
        "creation",
        "review_note",
    ]
    fields += ["member", "reference", "receipt_name", "receipt_size"]
    rows = frappe.get_all(
        "NJ Payment Request",
        filters={"member": member},
        fields=fields,
        order_by="creation desc",
        limit_page_length=100,
    )
    for row in rows:
        from nightjar_learning.localization import translated

        course = frappe.get_doc("LMS Course", row.course)
        row.course_title = translated(course, "title") or row.course
    return rows


@frappe.whitelist()
def review_requests(start=0, status=None):
    member = user()
    if not is_staff(member):
        deny("Payment review is available to teaching staff only.")
    filters = {}
    if not is_admin(member):
        courses = frappe.get_all("Course Instructor", filters={"parenttype": "LMS Course", "instructor": member}, pluck="parent")
        if not courses:
            return {"items": [], "has_more": False}
        filters["course"] = ["in", courses]
    if status:
        if status not in {"Pending", "Approved", "Rejected", "Revoked"}:
            frappe.throw("Choose a valid request status.")
        filters["status"] = status
    start = max(0, int(start))
    rows = frappe.get_all("NJ Payment Request", filters=filters,
        fields=["name", "course", "member", "reference", "amount", "currency", "status", "creation",
                "review_note", "reviewed_by", "receipt_name", "receipt_size"],
        order_by="creation desc, name desc", start=start, limit_page_length=51)
    for row in rows[:50]:
        from nightjar_learning.localization import translated
        course = frappe.get_doc("LMS Course", row.course)
        row.course_title = translated(course, "title") or row.course
    return {"items": rows[:50], "has_more": len(rows) > 50}


@frappe.whitelist()
@rate_limit(limit=30, seconds=60)
def receipt(request):
    from nightjar_learning.receipts import receipt_response
    member = user()
    doc = frappe.get_doc("NJ Payment Request", request)
    if doc.member != member and not can_review(doc.course, member):
        deny("You cannot access this receipt.")
    return receipt_response(doc)
