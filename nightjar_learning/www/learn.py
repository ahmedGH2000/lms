import frappe
import json
from pathlib import Path
from frappe.sessions import get_csrf_token

no_cache = 1


def get_context(context):
    context.no_cache = 1
    assets = json.loads((Path(__file__).resolve().parents[1] / 'public/ui/.vite/manifest.json').read_text())
    context.entry_js = '/assets/nightjar_learning/ui/' + assets['index.html']['file']
    context.boot = {
        "api_contract": 1,
        "user": frappe.session.user,
        "csrf_token": get_csrf_token(),
        "full_name": frappe.db.get_value("User", frappe.session.user, "full_name")
        or "Guest",
        "roles": frappe.get_roles() if frappe.session.user != "Guest" else [],
    }
