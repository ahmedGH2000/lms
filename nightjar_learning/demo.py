import frappe
from nightjar_learning.access import is_admin, deny

COURSES = [
    (
        "Build your first web application",
        "Web development",
        "Beginner",
        0,
        "Bring an idea to life with routes, forms, and a small application you understand.",
    ),
    (
        "Vue, one component at a time",
        "Frontend",
        "Beginner",
        0,
        "Build a clear mental model of components, reactive state, and everyday interactions.",
    ),
    (
        "A practical guide to API design",
        "Backend",
        "Intermediate",
        1,
        "Make endpoints that are predictable, useful, and a pleasure to work with.",
    ),
    (
        "SQL that makes sense",
        "Databases",
        "Beginner",
        0,
        "Ask better questions of your data, from your first SELECT to useful joins.",
    ),
    (
        "Write tests with confidence",
        "Testing",
        "Intermediate",
        0,
        "Test the behaviors that matter and make changes without second-guessing yourself.",
    ),
    (
        "Secure by design",
        "Security",
        "Advanced",
        1,
        "Work through authorization, private files, and the decisions behind safer applications.",
    ),
]


def seed():
    if not is_admin():
        deny()
    if not frappe.conf.developer_mode:
        frappe.throw("Demo seed requires developer mode.")
    for title, category, level, paid, intro in COURSES:
        existing = frappe.db.get_value("LMS Course", {"title": title}, "name")
        if existing:
            # Recount only derived metadata; never replace existing lessons.
            from lms.lms.utils import get_lesson_count
            frappe.db.set_value("LMS Course", existing, "lessons", get_lesson_count(existing))
            continue
        if not frappe.db.exists("LMS Category", category):
            frappe.get_doc(dict(doctype="LMS Category", category=category)).insert(
                ignore_permissions=True
            )
        c = frappe.get_doc(
            dict(
                doctype="LMS Course",
                title=title,
                short_introduction=intro,
                description=f"<p>{intro}</p><p>Original demonstration course. Expand these starter lessons in the teaching studio before inviting learners.</p>",
                category=category,
                nj_difficulty=level,
                paid_course=paid,
                course_price=49 if paid else 0,
                currency="USD",
                featured=int(title == COURSES[0][0]),
                instructors=[{"instructor": frappe.session.user}],
                published=1,
                status="Approved",
            )
        ).insert(ignore_permissions=True)
        ch = frappe.get_doc(
            dict(doctype="Course Chapter", title="The foundations", course=c.name)
        ).insert(ignore_permissions=True)
        for text in [
            "Understand the building blocks",
            "Try a small example",
            "Reflect and take the next step",
        ]:
            l = frappe.get_doc(
                dict(
                    doctype="Course Lesson",
                    title=text,
                    course=c.name,
                    chapter=ch.name,
                    body=f"## {text}\n\n{intro}\n\n### Try it yourself\n\nChoose a small example. Write down its input, the expected result, and one thing that could go wrong. Explain your reasoning in the discussion.\n\nThese are starter prompts, not a complete teaching curriculum.",
                )
            ).insert(ignore_permissions=True)
            ch.append("lessons", {"lesson": l.name})
        ch.save(ignore_permissions=True)
        c.reload()
        c.append("chapters", {"chapter": ch.name})
        c.save(ignore_permissions=True)
        # The chapter's first save ran before it was linked to this course.
        ch.update_lesson_count()
    frappe.db.commit()
