"""Keep public/student page entry points in Nightjar; retain staff tools."""
from urllib.parse import urlencode
import frappe


def landing_page():
    from nightjar_learning.access import is_staff
    return '/lms' if is_staff() else '/learn#view=dashboard'


def before_request():
    from nightjar_learning.localization import apply_request_language
    apply_request_language()
    # Receipts have no public File record and can only be read via payments.receipt.
    from urllib.parse import unquote
    path = unquote(frappe.request.path)
    if path.startswith('/private/files/nightjar-receipts/'):
        frappe.throw('Use the payment request to download this receipt.', frappe.PermissionError)


def after_request(response, request=None):
    request = getattr(frappe.local, 'request', None)
    if not request or request.method != 'GET':
        return
    path = request.path.rstrip('/') or '/'
    target = None
    if path == '/':
        target = '/learn'
    elif path == '/login':
        target = '/learn#view=login'
    elif path in ('/me', '/update-profile'):
        target = '/learn#view=profile'
    elif path == '/update-password':
        key = request.args.get('key')
        target = '/learn#' + urlencode({'view':'reset','key':key}) if key else '/learn#view=forgot'
    elif path == '/app' or path.startswith('/app/') or path == '/desk' or path.startswith('/desk/'):
        from nightjar_learning.access import is_staff
        if not is_staff():
            target = '/learn'
    elif path == '/lms' or path.startswith('/lms/'):
        roles = frappe.get_roles() if frappe.session.user != 'Guest' else []
        staff = frappe.session.user == 'Administrator' or bool(set(roles) & {'System Manager','Moderator','Course Creator'})
        # Native quiz/assignment frames stay inside the Nightjar lesson.
        # A lesson query selects only the content renderer, never the LMS shell.
        activity = request.args.get('nightjar_lesson')
        if activity:
            from nightjar_learning.access import require_lesson
            require_lesson(activity)
        embedded = request.headers.get('Sec-Fetch-Dest') == 'iframe' and (
            path.startswith('/lms/quizzes/') or path.startswith('/lms/assignments/') or path.startswith('/lms/programming-exercises/')
        )
        if not staff and not activity and not embedded:
            target = '/learn'
            parts = path.split('/')
            if len(parts) >= 4 and parts[2] == 'courses':
                course = parts[3]
                params = {'course':course}
                if len(parts) >= 6 and parts[4] == 'learn':
                    try:
                        chapter, lesson = [int(x) for x in parts[5].split('-')]
                        ch = frappe.db.get_value('Chapter Reference',{'parent':course,'idx':chapter},'chapter')
                        name = frappe.db.get_value('Lesson Reference',{'parent':ch,'idx':lesson},'lesson') if ch else None
                        if name: params['lesson'] = name
                    except (ValueError, TypeError):
                        pass
                target += '#' + urlencode(params)
    if target:
        response.status_code = 302
        response.headers['Location'] = target
        response.headers['Cache-Control'] = 'no-store'
        response.set_data('')
