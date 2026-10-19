import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import now_datetime
from nightjar_learning.access import user, is_admin, deny, approved


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
            "status": frappe.db.get_value("NJ Payment Request", existing, "status"),
        }
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
    ).insert(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist(methods=["POST"])
def decide(request, decision, note=""):
    if not is_admin():
        deny("Only system administrators can approve payments.")
    course = frappe.db.get_value("NJ Payment Request", request, "course")
    if not course:
        deny()
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
    if not str(note).strip():
        frappe.throw("Record how you verified the payment or why it was rejected.")
    doc.status = decision
    doc.review_note = str(note)[:1000]
    doc.reviewed_by = frappe.session.user
    doc.reviewed_at = now_datetime()
    doc.save(ignore_permissions=True)
    if decision == "Approved":
        enroll_member(doc.course, doc.member)
    if decision == "Revoked":
        name = frappe.db.exists(
            "LMS Enrollment", {"course": doc.course, "member": doc.member}
        )
        if name:
            frappe.delete_doc("LMS Enrollment", name, ignore_permissions=True)
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
    if is_admin():
        fields += ["member", "reference"]
    return frappe.get_all(
        "NJ Payment Request",
        filters={} if is_admin() else {"member": member},
        fields=fields,
        order_by="creation desc",
        limit_page_length=100,
    )
