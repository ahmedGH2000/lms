import html
import frappe
from frappe.rate_limiter import rate_limit
from nightjar_learning.access import user, instructor, require_lesson, can_learn, deny


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def catalog(search="", category="", level="", start=0):
    start = max(0, min(int(start), 10000))
    filters = {"published": 1}
    if category:
        filters["category"] = str(category)[:140]
    if level in {"Beginner", "Intermediate", "Advanced"}:
        filters["nj_difficulty"] = level
    if search:
        filters["title"] = ["like", "%" + str(search)[:100] + "%"]
    rows = frappe.get_all(
        "LMS Course",
        filters=filters,
        fields=[
            "name",
            "title",
            "short_introduction",
            "image",
            "category",
            "nj_difficulty",
            "paid_course",
            "course_price",
            "currency",
            "lessons",
            "featured",
            "card_gradient",
        ],
        order_by="published_on desc, creation desc, name asc",
        start=start,
        limit_page_length=24,
    )
    for row in rows:
        teachers = frappe.get_all(
            "Course Instructor",
            filters={"parenttype": "LMS Course", "parent": row.name},
            pluck="instructor",
            order_by="idx",
        )
        row.instructors = [
            {"name": frappe.db.get_value("User", t, "full_name") or "Instructor"}
            for t in teachers
        ]
    categories = frappe.get_all(
        "LMS Course", filters={"published": 1}, pluck="category", distinct=True
    )
    return dict(
        courses=rows,
        categories=sorted(c for c in categories if c),
        total=frappe.db.count("LMS Course", filters=filters),
    )


@frappe.whitelist()
def dashboard():
    member = user()
    result = []
    for row in frappe.get_all(
        "LMS Enrollment",
        filters={"member": member},
        fields=["course", "progress", "current_lesson"],
        order_by="modified desc",
        limit_page_length=100,
    ):
        c = frappe.db.get_value(
            "LMS Course",
            row.course,
            [
                "name",
                "title",
                "short_introduction",
                "image",
                "nj_difficulty",
                "category",
                "lessons",
            ],
            as_dict=True,
        )
        if c and can_learn(row.course):
            c.update(
                dict(progress=row.progress or 0, current_lesson=row.current_lesson)
            )
            result.append(c)
    return result


@frappe.whitelist(allow_guest=True)
def course_detail(course):
    doc = frappe.get_doc("LMS Course", course)
    if not doc.published and not instructor(course):
        deny()
    chapters = []
    for ref in doc.chapters:
        ch = frappe.get_doc("Course Chapter", ref.chapter)
        lessons = []
        for item in ch.lessons:
            l = frappe.db.get_value(
                "Course Lesson", item.lesson, ["name", "title"], as_dict=True
            )
            if l:
                l.duration = frappe.db.get_value(
                    "NJ Video Asset", {"lesson": l.name, "active": 1}, "duration"
                )
                lessons.append(l)
        chapters.append(dict(name=ch.name, title=ch.title, lessons=lessons))
    result = {
        k: doc.get(k)
        for k in [
            "name",
            "title",
            "description",
            "short_introduction",
            "category",
            "nj_difficulty",
            "image",
            "paid_course",
            "course_price",
            "currency",
        ]
    }
    result.update(
        chapters=chapters,
        can_learn=can_learn(course),
        enrollment=frappe.db.get_value(
            "LMS Enrollment",
            {"course": course, "member": frappe.session.user},
            ["progress", "current_lesson"],
            as_dict=True,
        ),
        instructors=[
            {
                "name": frappe.db.get_value("User", i.instructor, "full_name")
                or "Instructor"
            }
            for i in doc.instructors
        ],
    )
    return result


@frappe.whitelist()
def lesson_detail(lesson):
    course = require_lesson(lesson)
    doc = frappe.get_doc("Course Lesson", lesson)
    return dict(
        name=doc.name,
        title=doc.title,
        course=course,
        body=doc.body,
        youtube=doc.youtube,
        quiz_id=doc.quiz_id,
        content=doc.content,
        private_video=bool(
            frappe.db.exists("NJ Video Asset", {"lesson": lesson, "active": 1})
        ),
        complete=bool(
            frappe.db.exists(
                "LMS Course Progress",
                {"member": frappe.session.user, "lesson": lesson, "status": "Complete"},
            )
        ),
    )


@frappe.whitelist(methods=["POST"])
def complete(lesson):
    from nightjar_learning.guards import save_progress

    course = require_lesson(lesson)
    save_progress(lesson, course)
    return dict(
        complete=bool(
            frappe.db.exists(
                "LMS Course Progress",
                {"member": frappe.session.user, "lesson": lesson, "status": "Complete"},
            )
        ),
        progress=frappe.db.get_value(
            "LMS Enrollment",
            {"course": course, "member": frappe.session.user},
            "progress",
        )
        or 0,
    )


@frappe.whitelist()
def discussion(lesson):
    course = require_lesson(lesson)
    topics = frappe.get_all(
        "Discussion Topic",
        filters={"reference_doctype": "Course Lesson", "reference_docname": lesson},
        pluck="name",
    )
    if not topics:
        return []
    rows = frappe.get_all(
        "Discussion Reply",
        filters={"topic": ["in", topics]},
        fields=["name", "reply", "owner", "creation", "nj_reply_to"],
        order_by="creation asc",
        limit_page_length=200,
    )
    for r in rows:
        r.author = frappe.db.get_value("User", r.owner, "full_name") or "Learner"
        r.instructor = instructor(course, r.owner)
        del r["owner"]
    return rows


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=60)
def comment(lesson, text, reply_to=None):
    require_lesson(lesson)
    text = str(text or "").strip()
    if not 1 <= len(text) <= 4000:
        frappe.throw("Write between 1 and 4,000 characters.")
    frappe.db.get_value("Course Lesson", lesson, "name", for_update=True)
    topic = frappe.db.exists(
        "Discussion Topic",
        {"reference_doctype": "Course Lesson", "reference_docname": lesson},
    )
    if not topic:
        topic = (
            frappe.get_doc(
                dict(
                    doctype="Discussion Topic",
                    title="Lesson discussion",
                    reference_doctype="Course Lesson",
                    reference_docname=lesson,
                )
            )
            .insert(ignore_permissions=True)
            .name
        )
    if reply_to and frappe.db.get_value("Discussion Reply", reply_to, "topic") != topic:
        deny("Reply belongs to another lesson.")
    row = frappe.get_doc(
        dict(
            doctype="Discussion Reply",
            topic=topic,
            reply="<p>" + html.escape(text).replace("\n", "<br>") + "</p>",
            nj_reply_to=reply_to,
        )
    ).insert(ignore_permissions=True)
    return {"name": row.name}
