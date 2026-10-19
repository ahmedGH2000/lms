"""Apply paid-course and prerequisite gates to native quiz API entry points."""
import frappe
from nightjar_learning.access import user, can_learn, require_lesson, deny


def require_quiz(quiz):
    user()
    from lms.lms.permissions import can_access_quiz
    if not can_access_quiz(quiz):
        deny()
    row = frappe.db.get_value('LMS Quiz', quiz, ['course', 'lesson'], as_dict=True)
    if row and row.course and not can_learn(row.course):
        deny('Enroll in this course before opening its assessments.')
    if row and row.lesson:
        require_lesson(row.lesson)


@frappe.whitelist()
def get_quiz_with_questions(quiz):
    require_quiz(quiz)
    from lms.lms.utils import get_quiz_with_questions as original
    return original(quiz)


@frappe.whitelist(methods=['POST'])
def submit_quiz(quiz, results=None, violation_count=0, submission_reason='manual', violation_events=None):
    require_quiz(quiz)
    from lms.lms.doctype.lms_quiz.lms_quiz import submit_quiz as original
    return original(quiz, results, violation_count, submission_reason, violation_events)


@frappe.whitelist(methods=['POST'])
def check_answer(quiz, question, question_type, answers):
    require_quiz(quiz)
    from lms.lms.doctype.lms_quiz.lms_quiz import check_answer as original
    return original(quiz, question, question_type, answers)
