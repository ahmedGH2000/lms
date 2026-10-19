"""Account operations for the native LMS forms; Frappe owns authentication."""

import frappe
from frappe import _
from frappe.utils import validate_email_address

LMS_ROLES = {"LMS Student", "Course Creator", "Moderator", "Batch Evaluator"}


@frappe.whitelist(methods=["POST"])
def create_member(email: str, first_name: str, last_name: str = "", roles=None):
    # Native member creation needs User.create; assigning LMS roles also needs
    # Moderator. Keep both checks even if a caller bypasses the UI.
    try:
        frappe.only_for("Moderator")
    except frappe.PermissionError:
        frappe.throw(_("You are not permitted to manage learning accounts."), frappe.PermissionError)
    if not frappe.has_permission("User", "create"):
        frappe.throw(_("Creating accounts requires User-create permission. Ask your administrator."), frappe.PermissionError)
    email = validate_email_address((email or "").strip().lower(), throw=True)
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()
    if not first_name or len(first_name) > 140 or len(last_name) > 140:
        frappe.throw(_("Enter a first name and keep each name under 141 characters."))
    if isinstance(roles, str):
        try:
            roles = frappe.parse_json(roles)
        except (ValueError, TypeError):
            frappe.throw(_("Choose valid learning roles."))
    if roles is None:
        roles = ["LMS Student"]
    if not isinstance(roles, list) or any(not isinstance(r, str) or r not in LMS_ROLES for r in roles):
        frappe.throw(_("Only learning roles can be assigned here."), frappe.PermissionError)
    if frappe.db.exists("User", email):
        frappe.throw(_("This email already has an account. Edit that member to change their roles."))

    try:
        user = frappe.get_doc({
            "doctype": "User", "email": email, "first_name": first_name,
            "last_name": last_name, "enabled": 1, "user_type": "Website User",
            "send_welcome_email": 1,
            "roles": [{"role": role} for role in sorted(set(roles) | {"LMS Student"})],
        }).insert()
        if "Batch Evaluator" in roles:
            # Preserve native Course Evaluator creation and its validations.
            from lms.lms.api import save_evaluator_role
            save_evaluator_role(user.name, 1)
        # A request commits both the account and roles together; no second RPC.
        return {"name": user.name, "full_name": user.full_name,
                "email_sent": bool(user.flags.email_sent)}
    except (frappe.QueryTimeoutError, frappe.QueryDeadlockError):
        frappe.db.rollback()
        frappe.throw(_("The database is busy. The account was not saved. Wait a moment and try again."))


from frappe.rate_limiter import rate_limit
from nightjar_learning.access import user as current_user, is_admin, deny


def validate_password(password, confirm):
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        frappe.throw('Choose a password between 12 and 128 characters.')
    if password != confirm:
        frappe.throw('The passwords do not match.')
    from frappe.core.doctype.user.user import test_password_strength, handle_password_test_fail
    result = test_password_strength(password)
    feedback = result.get('feedback')
    if feedback and not feedback.get('password_policy_validation_passed', False):
        handle_password_test_fail(feedback)


@frappe.whitelist(allow_guest=True, methods=['POST'])
@rate_limit(limit=5, seconds=3600)
def register(email, full_name, password, confirm_password):
    from frappe.core.doctype.user.user import is_signup_disabled
    from frappe.utils import cint, escape_html
    if is_signup_disabled():
        frappe.throw('Registration is currently closed. Contact the instructor.')
    limit = cint(frappe.get_system_settings('max_signups_allowed_per_hour') or 300)
    if frappe.db.get_creation_count('User', 60) >= limit:
        frappe.throw('Registration is temporarily busy. Please try again later.')
    email = validate_email_address(str(email or '').strip().lower(), throw=True)
    full_name = str(full_name or '').strip()
    if not 1 <= len(full_name) <= 140:
        frappe.throw('Enter your name (up to 140 characters).')
    validate_password(password, confirm_password)
    if frappe.db.exists('User', email):
        frappe.throw('Unable to register this email. Try signing in or recovering your account.')
    doc = frappe.get_doc(dict(doctype='User', email=email, first_name=escape_html(full_name),
        enabled=1, user_type='Website User', new_password=password, send_welcome_email=0,
        roles=[{'role': 'LMS Student'}]))
    doc.insert(ignore_permissions=True)
    return {'created': True}


@frappe.whitelist(methods=['POST'])
@rate_limit(limit=10, seconds=60)
def login(email, password, otp=None, tmp_id=None):
    # Use the native login manager: password checks, lockout, IP policy and 2FA.
    frappe.local.form_dict.update(usr=email, pwd=password)
    if otp:
        frappe.local.form_dict.update(otp=otp, tmp_id=tmp_id)
    frappe.local.login_manager.login()
    return {'signed_in': frappe.session.user != 'Guest', 'verification': frappe.local.response.get('verification'), 'tmp_id': frappe.local.response.get('tmp_id'), 'redirect_to': frappe.local.response.get('redirect_to')}

# Guest login must remain possible without replacing Frappe's authentication.
login = frappe.whitelist(allow_guest=True, methods=['POST'])(login)


@frappe.whitelist(methods=['POST'])
def logout():
    current_user()
    frappe.local.login_manager.logout()
    return True


@frappe.whitelist()
def profile():
    name = current_user()
    return frappe.db.get_value('User', name, ['email', 'first_name', 'last_name', 'bio'], as_dict=True)


@frappe.whitelist(methods=['POST'])
def save_profile(first_name, last_name='', bio=''):
    name = current_user()
    first_name, last_name, bio = (str(v or '') for v in (first_name, last_name, bio))
    if not str(first_name).strip() or max(len(str(first_name)), len(str(last_name))) > 140 or len(str(bio)) > 2000:
        frappe.throw('Enter a name under 141 characters and a bio under 2,001 characters.')
    doc = frappe.get_doc('User', name)
    from frappe.utils import escape_html
    doc.first_name = escape_html(first_name.strip())
    doc.last_name = escape_html(last_name.strip())
    doc.bio = escape_html(bio)
    doc.save(ignore_permissions=True)
    return profile()


@frappe.whitelist(allow_guest=True, methods=['POST'])
@rate_limit(limit=5, seconds=3600)
def recover(email):
    from frappe.core.doctype.user.user import reset_password
    reset_password(str(email or '').strip().lower())
    return 'If the account is eligible, a password reset email has been requested. If it does not arrive, contact your instructor.'


@frappe.whitelist(allow_guest=True, methods=['POST'])
@rate_limit(limit=5, seconds=3600)
def change_password(password, confirm_password, old_password=None, key=None):
    validate_password(password, confirm_password)
    if not key:
        current_user()
        if not old_password:
            frappe.throw('Enter your current password.')
    from frappe.core.doctype.user.user import update_password
    result = update_password(password, old_password=old_password, key=key, logout_all_sessions=1)
    if frappe.local.response.get('http_status_code') == 410:
        frappe.throw('This reset link has expired. Request a new one.')
    return {'changed': True}


def require_admin():
    current_user()
    if not is_admin():
        deny('Only an administrator can manage accounts.')


@frappe.whitelist()
def members(search='', start=0):
    require_admin()
    filters = {'name': ['not in', ['Administrator', 'Guest']]}
    if search:
        filters['email'] = ['like', '%' + str(search)[:140] + '%']
    return frappe.get_all('User', filters=filters, fields=['name', 'full_name', 'enabled', 'user_type'],
        order_by='creation desc', start=max(0, int(start)), limit_page_length=50)


@frappe.whitelist(methods=['POST'])
def add_student(email, full_name, password, confirm_password):
    require_admin()
    validate_password(password, confirm_password)
    email = validate_email_address(str(email).strip().lower(), throw=True)
    if not str(full_name).strip() or len(full_name) > 140:
        frappe.throw('Enter a name under 141 characters.')
    if frappe.db.exists('User', email):
        frappe.throw('An account already exists for this email.')
    from frappe.utils import escape_html
    frappe.get_doc(dict(doctype='User', email=email, first_name=escape_html(full_name.strip()),
        user_type='Website User', enabled=1, send_welcome_email=0, new_password=password,
        roles=[{'role':'LMS Student'}])).insert()
    return True


@frappe.whitelist(methods=['POST'])
def set_student_password(member, password, confirm_password):
    require_admin()
    validate_password(password, confirm_password)
    doc = frappe.get_doc('User', member)
    if doc.user_type != 'Website User' or member in ('Guest', 'Administrator'):
        deny('Use advanced settings to manage staff accounts.')
    doc.new_password = password
    doc.logout_all_sessions = 1
    doc.save()
    return True
