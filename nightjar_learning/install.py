import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_install():
    create_custom_fields(
        {
            "LMS Course Review": [
                {"fieldname":"nj_response","label":"Instructor response","fieldtype":"Small Text","read_only":1},
                {"fieldname":"nj_responder","label":"Responded by","fieldtype":"Link","options":"User","read_only":1},
            ],
            "LMS Course": [
                {
                    "fieldname": "nj_difficulty",
                    "label": "Difficulty",
                    "fieldtype": "Select",
                    "options": "Beginner\nIntermediate\nAdvanced",
                    "default": "Beginner",
                    "insert_after": "category",
                }
            ],
            "LMS Enrollment": [
                {
                    "fieldname": "nj_approved_by",
                    "label": "Administrator approval",
                    "fieldtype": "Link",
                    "options": "User",
                    "read_only": 1,
                    "no_copy": 1,
                    "insert_after": "payment",
                }
            ],
            "Discussion Reply": [
                {
                    "fieldname": "nj_reply_to",
                    "label": "Reply to",
                    "fieldtype": "Link",
                    "options": "Discussion Reply",
                    "insert_after": "reply",
                }
            ],
        },
        update=True,
    )
    frappe.db.add_unique("NJ Video Position", ["member", "lesson"])
    frappe.db.add_index("NJ Payment Request", ["member", "course", "status"])
    frappe.db.add_index("NJ Playback Event", ["creation"])
