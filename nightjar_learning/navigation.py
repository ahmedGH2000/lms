"""Keep public/student page entry points in Nightjar; retain staff tools."""
from urllib.parse import urlencode
import frappe


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
    elif path == '/lms' or path.startswith('/lms/'):
        roles = frappe.get_roles() if frappe.session.user != 'Guest' else []
        staff = frappe.session.user == 'Administrator' or bool(set(roles) & {'System Manager','Moderator','Course Creator'})
        if not staff and not request.args.get('nightjar_lesson') and request.headers.get('Sec-Fetch-Dest') != 'iframe':
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
