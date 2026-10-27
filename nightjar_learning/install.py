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
                ,
                {"fieldname":"nj_title_ar","label":"Arabic title","fieldtype":"Data","insert_after":"nj_difficulty"},
                {"fieldname":"nj_title_en","label":"English title","fieldtype":"Data","insert_after":"nj_title_ar"},
                {"fieldname":"nj_short_introduction_ar","label":"Arabic short introduction","fieldtype":"Small Text","insert_after":"nj_title_en"},
                {"fieldname":"nj_short_introduction_en","label":"English short introduction","fieldtype":"Small Text","insert_after":"nj_short_introduction_ar"},
                {"fieldname":"nj_description_ar","label":"Arabic description","fieldtype":"Text Editor","insert_after":"nj_short_introduction_en"},
                {"fieldname":"nj_description_en","label":"English description","fieldtype":"Text Editor","insert_after":"nj_description_ar"},
            ],
            "Course Chapter": [
                {"fieldname":"nj_title_ar","label":"Arabic title","fieldtype":"Data","insert_after":"title"},
                {"fieldname":"nj_title_en","label":"English title","fieldtype":"Data","insert_after":"nj_title_ar"},
            ],
            "Course Lesson": [
                {"fieldname":"nj_title_ar","label":"Arabic title","fieldtype":"Data","insert_after":"title"},
                {"fieldname":"nj_title_en","label":"English title","fieldtype":"Data","insert_after":"nj_title_ar"},
                {"fieldname":"nj_body_ar","label":"Arabic lesson body","fieldtype":"Long Text","insert_after":"nj_title_en"},
                {"fieldname":"nj_body_en","label":"English lesson body","fieldtype":"Long Text","insert_after":"nj_body_ar"},
                {"fieldname":"nj_content_ar","label":"Arabic structured content","fieldtype":"Long Text","insert_after":"nj_body_en"},
                {"fieldname":"nj_content_en","label":"English structured content","fieldtype":"Long Text","insert_after":"nj_content_ar"},
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
