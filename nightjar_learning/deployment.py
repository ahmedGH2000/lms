"""Operator-only checks, invoked with bench execute (never a public API)."""
import importlib.util
from pathlib import Path
import secrets
import frappe


def check():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('nightjar_verify', root/'deploy/verify_release.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.verify(root, imports=True)
    for field in ('nj_response', 'nj_responder'):
        if not frappe.get_meta('LMS Course Review').has_field(field):
            frappe.throw('Missing review fields. Run bench migrate for this site.')
    frappe.db.sql('select 1')
    # PING alone succeeds during Redis MISCONF. Verify an actual expiring write.
    key = 'nightjar-health-' + secrets.token_hex(12)
    frappe.cache.setex(key, 15, 'ready')
    if frappe.cache.get(key) != b'ready':
        frappe.throw('Redis write/read verification failed.')
    frappe.cache.delete(key)
    result.update(database='ok', redis_write='ok', review_schema='ok')
    return result
