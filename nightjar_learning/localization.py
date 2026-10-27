"""Arabic/English preferences and optional translated learning content."""

import json

import frappe
from frappe.rate_limiter import rate_limit

from nightjar_learning.access import instructor, is_admin, is_staff, user, deny


LANGUAGES = ("ar", "en")


def normalize_language(value=None):
    value = str(value or "").lower().replace("_", "-")
    return "ar" if value.startswith("ar") else "en" if value.startswith("en") else None


def current_language(value=None):
    """Resolve the explicit request, shared browser cookie, or account preference."""
    explicit = normalize_language(value)
    if explicit:
        return explicit
    request = getattr(frappe.local, "request", None)
    if request:
        saved = normalize_language(request.cookies.get("nightjar_language"))
        if saved:
            return saved
    member = getattr(getattr(frappe, "session", None), "user", "Guest")
    if member and member != "Guest":
        saved = normalize_language(frappe.db.get_value("User", member, "language"))
        if saved:
            return saved
    return "ar"


def apply_request_language():
    # Frappe and LMS already ship Arabic catalogs. Selecting frappe.local.lang here
    # makes the same preference apply to /lms and /app as well as Nightjar.
    frappe.local.lang = current_language()


def translated(doc, field, language=None):
    """Return selected language, the other language, then the original field."""
    language = current_language(language)
    other = "en" if language == "ar" else "ar"
    return (
        doc.get(f"nj_{field}_{language}")
        or doc.get(f"nj_{field}_{other}")
        or doc.get(field)
    )


def translate_fields(doc, fields, language=None):
    for field in fields:
        doc[field] = translated(doc, field, language)
    return doc


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=20, seconds=60)
def set_language(language):
    language = normalize_language(language)
    if not language:
        frappe.throw("Choose Arabic or English.")
    member = getattr(frappe.session, "user", "Guest")
    if member != "Guest":
        frappe.db.set_value("User", member, "language", language, update_modified=False)
        frappe.clear_cache(user=member)
    frappe.local.lang = language
    return {"language": language, "direction": "rtl" if language == "ar" else "ltr"}


def require_translator(course):
    user()
    if not is_staff() or not instructor(course):
        deny("You can translate only courses you teach.")


@frappe.whitelist()
def translation_courses():
    member = user()
    if not is_staff(member):
        deny("Course translations are available to teaching staff only.")
    filters = {}
    if not is_admin(member):
        courses = frappe.get_all(
            "Course Instructor",
            filters={
                "parenttype": "LMS Course",
                "instructor": member,
            },
            pluck="parent",
        )
        if not courses:
            return []
        filters["name"] = ["in", courses]
    return frappe.get_all(
        "LMS Course",
        filters=filters,
        fields=["name", "title", "nj_title_ar", "nj_title_en"],
        order_by="modified desc",
        limit_page_length=200,
    )


def _values(doc, fields):
    return {
        language: {field: doc.get(f"nj_{field}_{language}") or "" for field in fields}
        for language in ("ar", "en")
    }


@frappe.whitelist()
def translation_bundle(course):
    require_translator(course)
    course_doc = frappe.get_doc("LMS Course", course)
    chapters = []
    for reference in course_doc.chapters:
        chapter = frappe.get_doc("Course Chapter", reference.chapter)
        lessons = []
        for item in chapter.lessons:
            lesson = frappe.get_doc("Course Lesson", item.lesson)
            lessons.append(
                {
                    "name": lesson.name,
                    "original": {"title": lesson.title, "body": lesson.body or "", "content": lesson.content or ""},
                    "translations": _values(lesson, ("title", "body", "content")),
                }
            )
        chapters.append(
            {
                "name": chapter.name,
                "original": {"title": chapter.title},
                "translations": _values(chapter, ("title",)),
                "lessons": lessons,
            }
        )
    return {
        "course": {
            "name": course_doc.name,
            "original": {
                "title": course_doc.title,
                "short_introduction": course_doc.short_introduction or "",
                "description": course_doc.description or "",
            },
            "translations": _values(course_doc, ("title", "short_introduction", "description")),
        },
        "chapters": chapters,
    }


def _payload(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            frappe.throw("The translation payload is invalid.")
    if not isinstance(value, dict):
        frappe.throw("The translation payload is invalid.")
    return value


def _clean(value, maximum):
    value = str(value or "")
    if len(value) > maximum:
        frappe.throw(f"Translated content must be under {maximum + 1:,} characters.")
    return value


def _save_fields(doctype, name, values, allowed):
    updates = {}
    for language in LANGUAGES:
        translated_values = values.get(language, {})
        if not isinstance(translated_values, dict):
            frappe.throw("The translation payload is invalid.")
        for field, maximum in allowed.items():
            value = _clean(translated_values.get(field), maximum)
            if field == "content" and value.strip():
                try:
                    parsed = json.loads(value)
                    if not isinstance(parsed, dict):
                        raise ValueError
                except (TypeError, ValueError):
                    frappe.throw("Structured lesson content must be valid JSON.")
            updates[f"nj_{field}_{language}"] = value
    frappe.db.set_value(doctype, name, updates)


@frappe.whitelist(methods=["POST"])
def save_translation_bundle(course, payload):
    require_translator(course)
    payload = _payload(payload)
    frappe.db.get_value("LMS Course", course, "name", for_update=True)
    _save_fields(
        "LMS Course",
        course,
        _payload(payload.get("course", {})),
        {"title": 140, "short_introduction": 500, "description": 100_000},
    )
    chapters = payload.get("chapters", [])
    if not isinstance(chapters, list) or len(chapters) > 500:
        frappe.throw("The translation payload is invalid.")
    for chapter_values in chapters:
        if not isinstance(chapter_values, dict):
            frappe.throw("The translation payload is invalid.")
        chapter = chapter_values.get("name")
        if not frappe.db.exists("Chapter Reference", {"parent": course, "chapter": chapter}):
            deny("Chapter belongs to another course.")
        _save_fields("Course Chapter", chapter, chapter_values, {"title": 140})
        lessons = chapter_values.get("lessons", [])
        if not isinstance(lessons, list) or len(lessons) > 1000:
            frappe.throw("The translation payload is invalid.")
        for lesson_values in lessons:
            if not isinstance(lesson_values, dict):
                frappe.throw("The translation payload is invalid.")
            lesson = lesson_values.get("name")
            if frappe.db.get_value("Course Lesson", lesson, "course") != course:
                deny("Lesson belongs to another course.")
            _save_fields(
                "Course Lesson",
                lesson,
                lesson_values,
                {"title": 140, "body": 100_000, "content": 500_000},
            )
    return {"saved": True}
