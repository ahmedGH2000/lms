import frappe


def deny(message="You do not have access to this learning resource."):
    frappe.throw(message, frappe.PermissionError)


def user():
    member = frappe.session.user
    if member == "Guest" or not frappe.db.get_value("User", member, "enabled"):
        deny("Sign in with an active account to continue.")
    return member


def is_admin(member=None):
    member = member or frappe.session.user
    return member == "Administrator" or "System Manager" in frappe.get_roles(member)


def instructor(course, member=None):
    member = member or frappe.session.user
    return is_admin(member) or bool(
        frappe.db.exists(
            "Course Instructor",
            {"parenttype": "LMS Course", "parent": course, "instructor": member},
        )
    )


def approved(course, member):
    return bool(
        frappe.db.exists(
            "NJ Payment Request",
            {"course": course, "member": member, "status": "Approved"},
        )
        or frappe.db.exists(
            "LMS Payment",
            {
                "payment_for_document_type": "LMS Course",
                "payment_for_document": course,
                "member": member,
                "payment_received": 1,
                "payment_for_certificate": 0,
            },
        )
        or frappe.db.get_value(
            "LMS Enrollment", {"course": course, "member": member}, "nj_approved_by"
        )
    )


def can_learn(course, member=None):
    member = member or frappe.session.user
    if member == "Guest" or not frappe.db.get_value("User", member, "enabled"):
        return False
    if instructor(course, member):
        return True
    row = frappe.db.get_value(
        "LMS Course", course, ["published", "paid_course"], as_dict=True
    )
    if (
        not row
        or not row.published
        or not frappe.db.exists("LMS Enrollment", {"course": course, "member": member})
    ):
        return False
    return not row.paid_course or approved(course, member)


def require_lesson(lesson):
    from lms.lms.permissions import get_locked_lessons

    user()
    course = frappe.db.get_value("Course Lesson", lesson, "course")
    if not course or not can_learn(course):
        deny(
            "Enroll first. Paid courses require verified payment or administrator approval."
        )
    if not instructor(course) and lesson in get_locked_lessons(course):
        deny("Complete the previous lesson first.")
    return course
