import html
import frappe
from frappe.rate_limiter import rate_limit
from nightjar_learning.access import user, instructor, require_lesson, can_learn, deny
from nightjar_learning.localization import translate_fields, translated


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def catalog(search="", category="", level="", start=0, lang=None):
    start = max(0, min(int(start), 10000))
    filters = {"published": 1}
    or_filters = {}
    if category:
        filters["category"] = str(category)[:140]
    if level in {"Beginner", "Intermediate", "Advanced"}:
        filters["nj_difficulty"] = level
    if search:
        pattern = "%" + str(search)[:100] + "%"
        or_filters = {
            "title": ["like", pattern],
            "nj_title_ar": ["like", pattern],
            "nj_title_en": ["like", pattern],
        }
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
            "nj_title_ar",
            "nj_title_en",
            "nj_short_introduction_ar",
            "nj_short_introduction_en",
        ],
        order_by="published_on desc, creation desc, name asc",
        start=start,
        limit_page_length=24,
        **({"or_filters": or_filters} if or_filters else {}),
    )
    for row in rows:
        translate_fields(row, ("title", "short_introduction"), lang)
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
    if or_filters:
        count_rows = frappe.get_all(
            "LMS Course",
            filters=filters,
            or_filters=or_filters,
            fields=["count(name) as total"],
            limit_page_length=1,
        )
        count = count_rows[0].get("total", 0) if count_rows else 0
    else:
        count = frappe.db.count("LMS Course", filters=filters)
    return dict(
        courses=rows,
        categories=sorted(c for c in categories if c),
        total=count,
    )


@frappe.whitelist()
def dashboard(lang=None):
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
                "nj_title_ar",
                "nj_title_en",
                "nj_short_introduction_ar",
                "nj_short_introduction_en",
            ],
            as_dict=True,
        )
        if c and can_learn(row.course):
            translate_fields(c, ("title", "short_introduction"), lang)
            c.update(
                dict(progress=row.progress or 0, current_lesson=row.current_lesson)
            )
            result.append(c)
    return result


@frappe.whitelist(allow_guest=True)
def course_detail(course, lang=None):
    doc = frappe.get_doc("LMS Course", course)
    if not doc.published and not instructor(course):
        deny()
    chapters = []
    for ref in doc.chapters:
        ch = frappe.get_doc("Course Chapter", ref.chapter)
        lessons = []
        for item in ch.lessons:
            l = frappe.db.get_value(
                "Course Lesson",
                item.lesson,
                ["name", "title", "nj_title_ar", "nj_title_en"],
                as_dict=True,
            )
            if l:
                translate_fields(l, ("title",), lang)
                l.duration = frappe.db.get_value(
                    "NJ Video Asset", {"lesson": l.name, "active": 1}, "duration"
                )
                lessons.append(l)
        chapters.append(
            dict(name=ch.name, title=translated(ch, "title", lang), lessons=lessons)
        )
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
    for field in ("title", "short_introduction", "description"):
        result[field] = translated(doc, field, lang)
    return result


@frappe.whitelist()
def lesson_detail(lesson, lang=None):
    course = require_lesson(lesson)
    doc = frappe.get_doc("Course Lesson", lesson)
    return dict(
        name=doc.name,
        title=translated(doc, "title", lang),
        course=course,
        body=translated(doc, "body", lang),
        youtube=doc.youtube,
        quiz_id=doc.quiz_id,
        content=translated(doc, "content", lang),
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
