import os, json, secrets, re, sys, time, traceback
from pathlib import Path

project = Path(__file__).resolve().parents[1]
if os.environ.get("NJ_RUN_INTEGRATION") != "1":
    raise SystemExit("Set NJ_RUN_INTEGRATION=1 only for a disposable development site.")
site = os.environ.get("NJ_TEST_SITE", "nightjar.localhost")
if not site.endswith(".localhost"):
    raise SystemExit("Integration tests require a disposable .localhost site.")
root = Path(os.environ["FRAPPE_BENCH_ROOT"]).resolve()
media_root = Path(os.environ["NIGHTJAR_MEDIA_ROOT"]).resolve()
output = Path.cwd() / "integration-results.json"
os.environ["NIGHTJAR_VIDEO_SECRET"] = secrets.token_urlsafe(48)
os.chdir(root / "sites")

import frappe
from werkzeug.test import Client
from werkzeug.wrappers import Response
from frappe.app import application
from frappe.utils.password import update_password

frappe.init(site=site)
frappe.connect()
frappe.set_user("Administrator")
if not frappe.conf.developer_mode:
    raise SystemExit("Enable developer_mode on this disposable site first.")
frappe.flags.mute_emails = True
frappe.db.set_single_value("System Settings", "setup_complete", 1)
frappe.db.set_single_value("Website Settings", "disable_signup", 0)
from nightjar_learning.demo import seed

seed()
creds = {"Administrator": os.environ["NJ_TEST_ADMIN_PASSWORD"]}
for email, name, role in [
    ("alice@example.invalid", "Alice", "LMS Student"),
    ("bob@example.invalid", "Bob", "LMS Student"),
    ("instructor@example.invalid", "Maya", "Course Creator"),
]:
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            dict(
                doctype="User",
                email=email,
                first_name=name,
                enabled=1,
                send_welcome_email=0,
                user_type="Website User",
                roles=[{"role": role}],
            )
        ).insert(ignore_permissions=True)
    creds[email] = secrets.token_urlsafe(24)
    update_password(email, creds[email])
free = frappe.db.get_value(
    "LMS Course", {"title": "Build your first web application"}, "name"
)
paid = frappe.db.get_value(
    "LMS Course", {"title": "A practical guide to API design"}, "name"
)
lesson = frappe.get_all(
    "Course Lesson", filters={"course": free}, pluck="name", order_by="creation"
)[0]
paid_lesson = frappe.get_all(
    "Course Lesson", filters={"course": paid}, pluck="name", order_by="creation"
)[0]
metadata = json.loads(Path(os.environ["NJ_TEST_MEDIA_METADATA"]).read_text())
if not frappe.db.exists("NJ Video Asset", {"lesson": lesson}):
    frappe.get_doc(
        dict(doctype="NJ Video Asset", lesson=lesson, **metadata, active=1)
    ).insert(ignore_permissions=True)
c = frappe.get_doc("LMS Course", free)
if not any(i.instructor == "instructor@example.invalid" for i in c.instructors):
    c.append("instructors", {"instructor": "instructor@example.invalid"})
    c.save(ignore_permissions=True)
# Reset only these isolated regression users' request/enrollment records between runs.
for dt in [
    "NJ Payment Request",
    "NJ Video Position",
    "NJ Playback Event",
    "LMS Course Progress",
    "LMS Enrollment",
]:
    frappe.db.delete(
        dt, {"member": ["in", ["alice@example.invalid", "bob@example.invalid"]]}
    )
frappe.db.commit()
frappe.destroy()
results = []


def check(name, fn):
    try:
        fn()
        results.append(dict(test=name, result="PASS"))
        print("PASS", name, flush=True)
    except Exception as e:
        results.append(dict(test=name, result="FAIL", detail=str(e)[:2000]))
        print("FAIL", name, str(e)[:1000], flush=True)
        traceback.print_exc()


def client():
    return Client(application, Response)


def req(c, method, args=None, write=False, csrf=None):
    headers = {"Host": site, "Accept": "application/json"}
    if csrf:
        headers["X-Frappe-CSRF-Token"] = csrf
    return c.open(
        "/api/method/" + method,
        method="POST" if write else "GET",
        json=args if write else None,
        query_string=None if write else args,
        headers=headers,
    )


def ok(r):
    assert r.status_code == 200, (r.status_code, r.get_data(as_text=True)[:1500])
    return r.get_json().get("message")


def blocked(r):
    assert r.status_code in (401, 403, 417), (
        r.status_code,
        r.get_data(as_text=True)[:1500],
    )


def login(c, who):
    ok(req(c, "login", {"usr": who, "pwd": creds[who]}, True))
    r = c.get("/learn", headers={"Host": site})
    assert r.status_code == 200, r.text[-2000:]
    m = re.search(
        r'<script id="nightjar-boot" type="application/json">(.*?)</script>',
        r.text,
        re.S,
    )
    assert m, r.text[-1000:]
    return json.loads(m[1])["csrf_token"]


guest = client()
alice = client()
bob = client()
admin = client()
teacher = client()
tokens = {}
state = {}
check("Guest catalog", lambda: ok(req(guest, "nightjar_learning.api.catalog")))
check(
    "Guest protected lesson denied",
    lambda: blocked(
        req(guest, "nightjar_learning.api.lesson_detail", {"lesson": lesson})
    ),
)
check(
    "Registration through Frappe API",
    lambda: ok(
        req(
            guest,
            "frappe.core.doctype.user.user.sign_up",
            {
                "email": "newlearner-" + secrets.token_hex(4) + "@example.invalid",
                "full_name": "New Learner",
                "redirect_to": "/learn",
            },
            True,
        )
    ),
)
check(
    "Wrong password rejected",
    lambda: blocked(
        req(guest, "login", {"usr": "alice@example.invalid", "pwd": "incorrect"}, True)
    ),
)
for label, cli, email in [
    ("alice", alice, "alice@example.invalid"),
    ("bob", bob, "bob@example.invalid"),
    ("admin", admin, "Administrator"),
    ("teacher", teacher, "instructor@example.invalid"),
]:
    check(
        label + " login and page boot",
        lambda label=label, cli=cli, email=email: tokens.update(
            {label: login(cli, email)}
        ),
    )
if len(tokens) != 4:
    output.write_text(json.dumps(results, indent=2))
    sys.exit(1)


def call(c, who, method, args=None, write=False):
    return req(c, "nightjar_learning." + method, args, write, tokens[who])


check(
    "Unenrolled student denied",
    lambda: blocked(call(alice, "alice", "api.lesson_detail", {"lesson": lesson})),
)
check(
    "Free enrollment",
    lambda: ok(call(alice, "alice", "payments.enroll", {"course": free}, True)),
)
check(
    "Enrolled lesson access",
    lambda: ok(call(alice, "alice", "api.lesson_detail", {"lesson": lesson})),
)
check(
    "Paid enrollment requires approval",
    lambda: blocked(call(alice, "alice", "payments.enroll", {"course": paid}, True)),
)
check(
    "Instructor reads own course",
    lambda: ok(call(teacher, "teacher", "api.lesson_detail", {"lesson": lesson})),
)
check(
    "Instructor denied unrelated paid course",
    lambda: blocked(
        call(teacher, "teacher", "api.lesson_detail", {"lesson": paid_lesson})
    ),
)
check(
    "Manual payment request",
    lambda: state.update(
        request=ok(
            call(
                alice,
                "alice",
                "payments.request_payment",
                {"course": paid, "reference": "TEST-TRANSFER"},
                True,
            )
        )["name"]
    ),
)
check(
    "Student approval attempt denied",
    lambda: blocked(
        call(
            alice,
            "alice",
            "payments.decide",
            {"request": state["request"], "decision": "Approved", "note": "attempt"},
            True,
        )
    ),
)
check(
    "Pending request cannot read paid lesson",
    lambda: blocked(call(alice, "alice", "api.lesson_detail", {"lesson": paid_lesson})),
)
check(
    "Administrator approves and enrolls",
    lambda: ok(
        call(
            admin,
            "admin",
            "payments.decide",
            {
                "request": state["request"],
                "decision": "Approved",
                "note": "Test transfer verified",
            },
            True,
        )
    ),
)
check(
    "Approved student reads paid lesson",
    lambda: ok(call(alice, "alice", "api.lesson_detail", {"lesson": paid_lesson})),
)
check(
    "Approval retry idempotent",
    lambda: ok(
        call(
            admin,
            "admin",
            "payments.decide",
            {"request": state["request"], "decision": "Approved", "note": "Retry"},
            True,
        )
    ),
)
check(
    "Other student denied paid content",
    lambda: blocked(call(bob, "bob", "api.lesson_detail", {"lesson": paid_lesson})),
)
check(
    "Lesson comment creation",
    lambda: state.update(
        comment=ok(
            call(
                alice,
                "alice",
                "api.comment",
                {
                    "lesson": lesson,
                    "text": "Why validate on the server? <script>alert(1)</script>",
                },
                True,
            )
        )["name"]
    ),
)
check(
    "Instructor reply",
    lambda: ok(
        call(
            teacher,
            "teacher",
            "api.comment",
            {
                "lesson": lesson,
                "text": "The caller can modify browser inputs.",
                "reply_to": state["comment"],
            },
            True,
        )
    ),
)
check(
    "Other student denied discussion",
    lambda: blocked(call(bob, "bob", "api.discussion", {"lesson": lesson})),
)


def complete_test():
    d = ok(call(alice, "alice", "api.complete", {"lesson": lesson}, True))
    assert d["complete"] and d["progress"] > 0, d
    rows = ok(call(alice, "alice", "api.dashboard"))
    assert any(c["name"] == free and c["progress"] > 0 for c in rows), rows


check("Completion updates real dashboard progress", complete_test)
check(
    "Private playback grant",
    lambda: state.update(
        grant=ok(call(alice, "alice", "video.authorize", {"lesson": lesson}, True))
    ),
)
check(
    "Unenrolled playback denied",
    lambda: blocked(call(bob, "bob", "video.authorize", {"lesson": lesson}, True)),
)


def resource(c, who, filename):
    return call(
        c,
        who,
        "video.resource",
        {"filename": filename, "token": state["grant"]["token"]},
    )


def media_test(filename, kind):
    r = resource(alice, "alice", filename)
    assert r.status_code == 200, r.text[:1000]
    assert "no-store" in r.headers["Cache-Control"]
    if kind == "manifest":
        assert (
            "METHOD=AES-128" in r.text and "nightjar_learning.video.resource?" in r.text
        )
    elif kind == "key":
        assert len(r.data) == 16
    else:
        assert len(r.data) > 16


check("Protected HLS manifest", lambda: media_test("index.m3u8", "manifest"))
check("Protected AES key", lambda: media_test("key.bin", "key"))
check("Protected encrypted segment", lambda: media_test("segment_00000.ts", "segment"))
check(
    "Shared token denied in other session",
    lambda: blocked(resource(bob, "bob", "key.bin")),
)
check("Path traversal denied", lambda: blocked(resource(alice, "alice", "../key.bin")))
check(
    "Heartbeat saves resume position",
    lambda: ok(
        call(alice, "alice", "video.heartbeat", {"lesson": lesson, "position": 5}, True)
    ),
)
check(
    "Invalid video position rejected",
    lambda: blocked(
        call(
            alice,
            "alice",
            "video.heartbeat",
            {"lesson": lesson, "position": 99999},
            True,
        )
    ),
)
check(
    "Revocation removes paid access",
    lambda: (
        ok(
            call(
                admin,
                "admin",
                "payments.decide",
                {
                    "request": state["request"],
                    "decision": "Revoked",
                    "note": "Test refund",
                },
                True,
            )
        ),
        blocked(call(alice, "alice", "api.lesson_detail", {"lesson": paid_lesson})),
    ),
)
check(
    "Generic REST cannot enroll another member",
    lambda: blocked(
        req(
            alice,
            "frappe.client.insert",
            {
                "doc": {
                    "doctype": "LMS Enrollment",
                    "member": "bob@example.invalid",
                    "course": free,
                }
            },
            True,
            tokens["alice"],
        )
    ),
)
check(
    "Generic REST cannot read other member enrollment",
    lambda: blocked(
        req(
            bob,
            "frappe.client.get",
            {
                "doctype": "LMS Enrollment",
                "filters": json.dumps(
                    {"member": "alice@example.invalid", "course": free}
                ),
            },
            False,
            tokens["bob"],
        )
    ),
)
check(
    "Generic REST cannot forge payment",
    lambda: blocked(
        req(
            alice,
            "frappe.client.insert",
            {
                "doc": {
                    "doctype": "LMS Payment",
                    "member": "alice@example.invalid",
                    "payment_received": 1,
                }
            },
            True,
            tokens["alice"],
        )
    ),
)


def csrf_test():
    r = req(
        alice,
        "nightjar_learning.api.comment",
        {"lesson": lesson, "text": "CSRF attempt"},
        True,
    )
    assert r.status_code == 400 and r.get_json()["exc_type"] == "CSRFTokenError"


check("Missing CSRF rejected", csrf_test)


def list_discussion():
    r = ok(
        req(
            bob,
            "frappe.client.get_list",
            {
                "doctype": "Discussion Reply",
                "fields": json.dumps(["name", "reply"]),
                "filters": json.dumps({"name": state["comment"]}),
            },
            False,
            tokens["bob"],
        )
    )
    assert r == [], r


check("Generic REST discussion query hides private comments", list_discussion)
check(
    "Native lesson API denies unpaid student",
    lambda: blocked(
        req(
            bob,
            "lms.lms.utils.get_lesson",
            {"course": paid, "chapter": 1, "lesson": 1},
            False,
            tokens["bob"],
        )
    ),
)
check(
    "Generic REST lesson read denied",
    lambda: blocked(
        req(
            bob,
            "frappe.client.get",
            {"doctype": "Course Lesson", "name": paid_lesson},
            False,
            tokens["bob"],
        )
    ),
)


def list_lessons():
    rows = ok(
        req(
            teacher,
            "frappe.client.get_list",
            {
                "doctype": "Course Lesson",
                "fields": json.dumps(["name"]),
                "filters": json.dumps({"course": paid}),
            },
            False,
            tokens["teacher"],
        )
    )
    assert rows == [], rows


check("Generic REST lesson list hides paid lessons", list_lessons)
check(
    "Guest denied signed video token",
    lambda: blocked(resource(guest, "bob", "key.bin")),
)


def nginx_test():
    import subprocess, threading, urllib.request, urllib.error, tempfile
    from werkzeug.serving import make_server
    from urllib.parse import urlencode

    binary = os.environ["NJ_NGINX_BIN"]
    snippet = (
        (project / "deploy/nginx-media.conf")
        .read_text()
        .replace("/var/lib/nightjar/media/", str(media_root) + "/")
    )
    server = make_server("127.0.0.1", 18000, application, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with tempfile.TemporaryDirectory(dir=root) as temp:
        cfg = Path(temp) / "nginx.conf"
        cfg.write_text(
            f"user root; daemon off; pid {temp}/pid; error_log stderr crit; events {{worker_connections 64;}} http {{access_log off; client_body_temp_path {temp}/body; proxy_temp_path {temp}/proxy; fastcgi_temp_path {temp}/fastcgi; uwsgi_temp_path {temp}/uwsgi; scgi_temp_path {temp}/scgi; upstream frappe {{server 127.0.0.1:18000;}} server {{listen 127.0.0.1:18880; server_name nightjar.localhost;"
            + snippet
            + "}}"
        )
        process = subprocess.Popen(
            [binary, "-p", temp, "-c", str(cfg)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        os.environ["NIGHTJAR_USE_ACCEL"] = "1"

        def fetch(path, cookie=True):
            headers = {"Host": site, "Accept": "application/json"}
            if cookie:
                headers["Cookie"] = "sid=" + alice.get_cookie("sid", domain=site).value
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(
                        "http://127.0.0.1:18880" + path, headers=headers
                    ),
                    timeout=10,
                ) as r:
                    return r.status, r.read(), r.headers
            except urllib.error.HTTPError as e:
                return e.code, e.read(), e.headers

        try:
            for _ in range(50):
                try:
                    status, _, _ = fetch(
                        "/_nj_media/" + metadata["asset_id"] + "/segment_00000.ts"
                    )
                    break
                except urllib.error.URLError:
                    if process.poll() is not None:
                        raise AssertionError(process.stderr.read().decode())
                    time.sleep(0.1)
            assert status == 404
            path = "/api/method/nightjar_learning.video.resource?" + urlencode(
                {"filename": "segment_00000.ts", "token": state["grant"]["token"]}
            )
            status, data, headers = fetch(path)
            assert status == 200, (status, data[:1000])
            assert (
                data
                == (media_root / metadata["asset_id"] / "segment_00000.ts").read_bytes()
            )
            assert "no-store" in headers["Cache-Control"]
            status, _, _ = fetch(path, False)
            assert status in (401, 403)
        finally:
            os.environ.pop("NIGHTJAR_USE_ACCEL", None)
            process.terminate()
            process.communicate(timeout=10)
            server.shutdown()


if os.environ.get("NJ_NGINX_BIN"):
    check("NGINX internal segments, authenticated proxy and guest denial", nginx_test)


def revoke_video():
    name = ok(
        req(
            alice,
            "frappe.client.get",
            {
                "doctype": "LMS Enrollment",
                "filters": json.dumps(
                    {"course": free, "member": "alice@example.invalid"}
                ),
            },
            False,
            tokens["alice"],
        )
    )["name"]
    ok(
        req(
            admin,
            "frappe.client.delete",
            {"doctype": "LMS Enrollment", "name": name},
            True,
            tokens["admin"],
        )
    )
    blocked(resource(alice, "alice", "key.bin"))


check(
    "Existing playback token denied immediately after enrollment removal", revoke_video
)
output.write_text(json.dumps(results, indent=2))
print(
    json.dumps(
        dict(
            passed=sum(r["result"] == "PASS" for r in results),
            failed=sum(r["result"] == "FAIL" for r in results),
        )
    ),
    flush=True,
)
sys.exit(any(r["result"] == "FAIL" for r in results))
