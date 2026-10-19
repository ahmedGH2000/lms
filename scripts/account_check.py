"""Real-database regression. Run only on a disposable local development site."""
import ast
import json
import os
from pathlib import Path
import secrets
import subprocess
import time

if os.environ.get("NJ_RUN_INTEGRATION") != "1":
    raise SystemExit("Set NJ_RUN_INTEGRATION=1 only on a disposable test site.")
root = Path(os.environ["FRAPPE_BENCH_ROOT"]).resolve()
site = os.environ.get("NJ_TEST_SITE", "nightjar.localhost")
if not site.endswith(".localhost"):
    raise SystemExit("Requires a disposable .localhost site")
os.chdir(root / "sites")
import frappe
import pymysql
from frappe.app import application
from werkzeug.test import Client
from werkzeug.wrappers import Response

frappe.init(site=site)
frappe.connect()
if not frappe.conf.developer_mode:
    raise SystemExit("Requires developer_mode")
frappe.set_user("Administrator")
student_email = "qa-student-" + secrets.token_hex(5) + "@example.invalid"
student_password = secrets.token_urlsafe(24)
frappe.get_doc({"doctype": "User", "email": student_email, "first_name": "Student", "send_welcome_email": 0,
    "roles": [{"role": "LMS Student"}]}).insert()
from frappe.utils.password import update_password
update_password(student_email, student_password)
frappe.db.set_single_value("Website Settings", "disable_signup", 0)
frappe.db.set_default("email_user_password", "")
frappe.db.commit()
cfg = dict(frappe.conf)

# Hold precisely the shared reminder row from the reported stack trace.
holder = pymysql.connect(host=cfg["db_host"], port=int(cfg.get("db_port") or 3306),
    user=cfg.get("db_user") or cfg["db_name"], password=cfg["db_password"], database=cfg["db_name"])
with holder.cursor() as cursor:
    cursor.execute("SELECT name FROM tabDefaultValue WHERE defkey=%s AND parent=%s FOR UPDATE", ("email_user_password", "__default"))

results = []
def check(name, passed):
    results.append({"test": name, "result": "PASS" if passed else "FAIL"})
    print(results[-1], flush=True)
    if not passed:
        raise AssertionError(name)

try:
    frappe.db.sql("SET SESSION innodb_lock_wait_timeout=1")
    original_source = subprocess.check_output(["git", "-C", str(Path(frappe.__file__).parents[1]), "show", "HEAD:frappe/core/doctype/user/user.py"], text=True)
    original = next(n for n in ast.parse(original_source).body if isinstance(n, ast.FunctionDef) and n.name == "ask_pass_update")
    namespace = {"frappe": frappe}
    exec(compile(ast.Module(body=[original], type_ignores=[]), "original-user.py", "exec"), namespace)
    timed_out = False
    try:
        namespace["ask_pass_update"]()
    except frappe.QueryTimeoutError:
        timed_out = True
    finally:
        frappe.db.rollback()
    check("Original code reproduces the shared-row lock timeout", timed_out)
    from frappe.core.doctype.user.user import ask_pass_update
    started = time.monotonic()
    ask_pass_update()
    check("Patched unchanged reminder does not wait on held row", time.monotonic() - started < 1)
    frappe.destroy()

    guest = Client(application, Response)
    admin = Client(application, Response)
    def rpc(client, method, args, token=None):
        return client.post("/api/method/" + method, json=args,
            headers={"Host": site, "Accept": "application/json", **({"X-Frappe-CSRF-Token": token} if token else {})})
    email = "qa-signup-" + secrets.token_hex(5) + "@example.invalid"
    response = rpc(guest, "frappe.core.doctype.user.user.sign_up", {"email": email, "full_name": "Signup regression", "redirect_to": "/learn"})
    check("Native signup succeeds while unrelated reminder row is locked", response.status_code == 200)
    response = rpc(admin, "login", {"usr": "Administrator", "pwd": os.environ["NJ_TEST_ADMIN_PASSWORD"]})
    check("Administrator login", response.status_code == 200)
    import re
    page = admin.get("/learn", headers={"Host": site})
    token = json.loads(re.search(r'<script id="nightjar-boot" type="application/json">(.*?)</script>', page.text, re.S)[1])["csrf_token"]
    instructor = "qa-teacher-" + secrets.token_hex(5) + "@example.invalid"
    method = "nightjar_learning.accounts.create_member"
    args = {"email": instructor, "first_name": "New", "last_name": "Instructor", "roles": ["Course Creator"]}
    response = rpc(admin, method, args)
    check("Member creation rejects missing CSRF token", response.status_code == 400 and response.json.get("exc_type") == "CSRFTokenError")
    response = rpc(admin, method, {**args, "roles": "invalid-json"}, token)
    check("Malformed roles rejected with validation feedback", response.status_code == 417 and "valid learning roles" in response.text)
    response = rpc(admin, method, args, token)
    check("Instructor creation succeeds while reminder row is locked", response.status_code == 200)
    response = rpc(admin, method, args, token)
    check("Duplicate member rejected with readable message", response.status_code == 417 and "already has" in response.text)
    response = rpc(guest, method, {**args, "email": "unauthorized@example.invalid"})
    check("Guest cannot create instructors", response.status_code in (401, 403))
    response = rpc(admin, method, {**args, "roles": ["System Manager"], "email": "qa-escalation@example.invalid"}, token)
    check("Privileged role rejected by allowlist", response.status_code == 403)
    response = rpc(admin, method, {**args, "first_name": "", "email": "qa-invalid@example.invalid"}, token)
    check("Missing first name rejected", response.status_code == 417)
    response = rpc(admin, method, {**args, "email": "not-an-email"}, token)
    check("Malformed email rejected", response.status_code == 417)
    from unittest.mock import patch
    failed_email = "qa-rollback-" + secrets.token_hex(5) + "@example.invalid"
    with patch("lms.lms.api.save_evaluator_role", side_effect=frappe.ValidationError("Simulated evaluator validation failure")):
        response = rpc(admin, method, {**args, "email": failed_email, "roles": ["Batch Evaluator"]}, token)
    check("Secondary evaluator failure rejects whole request", response.status_code == 417)

    student = Client(application, Response)
    response = rpc(student, "login", {"usr": student_email, "pwd": student_password})
    check("Student login", response.status_code == 200)
    page = student.get("/learn", headers={"Host": site})
    student_token = json.loads(re.search(r'<script id="nightjar-boot" type="application/json">(.*?)</script>', page.text, re.S)[1])["csrf_token"]
    response = rpc(student, method, {**args, "email": "qa-forbidden@example.invalid"}, student_token)
    check("Signed-in student cannot create instructors", response.status_code == 403)
finally:
    holder.rollback()
    holder.close()
    frappe.destroy()

frappe.init(site=site)
frappe.connect()
check("Saved instructor has Course Creator role", "Course Creator" in frappe.get_roles(instructor))
check("Signup user has student role and no privileged roles", "LMS Student" in frappe.get_roles(email) and not ({"Moderator", "Course Creator", "System Manager"} & set(frappe.get_roles(email))))
check("Rejected privileged account was not inserted", not frappe.db.exists("User", "qa-escalation@example.invalid"))
check("Failed evaluator creation rolls back User and roles", not frappe.db.exists("User", failed_email))
check("Student request created no account", not frappe.db.exists("User", "qa-forbidden@example.invalid"))
frappe.destroy()
Path(os.environ.get("NJ_ACCOUNT_RESULTS", "/tmp/nightjar-account-results.json")).write_text(json.dumps(results, indent=2))
