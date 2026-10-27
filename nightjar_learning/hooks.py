app_name = "nightjar_learning"
app_title = "Nightjar Learning"
app_publisher = "Nightjar contributors"
app_description = "Private learning experience for Frappe Learning"
app_email = "maintainers@example.invalid"
app_license = "AGPL-3.0-or-later"
web_include_js = [
    "/assets/nightjar_learning/language-switch.js",
    "/assets/nightjar_learning/login-feedback.js",
]
web_include_css = ["/assets/nightjar_learning/login-feedback.css"]
app_include_js = ["/assets/nightjar_learning/language-switch.js"]
app_include_css = ["/assets/nightjar_learning/login-feedback.css"]
required_apps = ["lms"]
after_install = "nightjar_learning.install.after_install"
after_migrate = "nightjar_learning.install.after_install"
override_doctype_class = {
    "LMS Enrollment": "nightjar_learning.guards.Enrollment",
    "Discussion Reply": "nightjar_learning.guards.PrivateDiscussionReply",
}
doc_events = {
    "LMS Enrollment": {"validate": "nightjar_learning.guards.validate_enrollment"},
    "LMS Payment": {"validate": "nightjar_learning.guards.validate_payment"},
    "LMS Course Progress": {"validate": "nightjar_learning.guards.validate_progress"},
    "LMS Video Watch Duration": {
        "validate": "nightjar_learning.guards.validate_progress"
    },
    "Discussion Topic": {"validate": "nightjar_learning.guards.validate_discussion"},
    "Discussion Reply": {"validate": "nightjar_learning.guards.validate_discussion"},
}
has_permission = {
    d: "nightjar_learning.guards.own_record"
    for d in [
        "LMS Enrollment",
        "LMS Course Progress",
        "LMS Video Watch Duration",
        "LMS Payment",
    ]
}
has_permission.update(
    {
        d: "nightjar_learning.guards.discussion_permission"
        for d in ["Discussion Topic", "Discussion Reply"]
    }
)
permission_query_conditions = {
    d: "nightjar_learning.guards." + f
    for d, f in [
        ("LMS Enrollment", "enrollment_query"),
        ("LMS Course Progress", "progress_query"),
        ("LMS Video Watch Duration", "watch_query"),
        ("LMS Payment", "payment_query"),
        ("Discussion Topic", "topic_query"),
        ("Discussion Reply", "reply_query"),
    ]
}
override_whitelisted_methods = {
    "lms.lms.utils.get_lesson": "nightjar_learning.guards.get_lesson",
    "lms.lms.doctype.course_lesson.course_lesson.save_progress": "nightjar_learning.guards.save_progress",
}
scheduler_events = {"daily": ["nightjar_learning.video.prune_events"]}

has_permission["Course Lesson"] = "nightjar_learning.guards.lesson_permission"
permission_query_conditions["Course Lesson"] = "nightjar_learning.guards.lesson_query"
override_whitelisted_methods[
    "lms.lms.doctype.course_lesson.course_lesson.serve_resource"
] = "nightjar_learning.guards.serve_resource"

doc_events["LMS Course Review"] = {"validate": "nightjar_learning.community.validate_review"}
before_request = ['nightjar_learning.navigation.before_request']
after_request = ['nightjar_learning.navigation.after_request']
override_whitelisted_methods.update({
    'lms.lms.utils.get_quiz_with_questions': 'nightjar_learning.assessments.get_quiz_with_questions',
    'lms.lms.doctype.lms_quiz.lms_quiz.submit_quiz': 'nightjar_learning.assessments.submit_quiz',
    'lms.lms.doctype.lms_quiz.lms_quiz.check_answer': 'nightjar_learning.assessments.check_answer',
})
