import math, os
from urllib.parse import urlencode
import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import add_days, now_datetime
from werkzeug.wrappers import Response
from nightjar_learning.access import user, require_lesson, deny
from nightjar_learning.tokens import issue, verify, safe_path


def secret():
    s = os.environ.get("NIGHTJAR_VIDEO_SECRET")
    if not s or len(s.encode()) < 32:
        frappe.throw("Private video is not configured. Contact your administrator.")
    return s


def url(token, filename):
    return "/api/method/nightjar_learning.video.resource?" + urlencode(
        {"token": token, "filename": filename}
    )


def log(lesson, event, position=0):
    frappe.get_doc(
        dict(
            doctype="NJ Playback Event",
            member=frappe.session.user,
            lesson=lesson,
            event=event,
            position=position,
        )
    ).insert(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=60)
def authorize(lesson):
    member = user()
    require_lesson(lesson)
    asset = frappe.db.get_value(
        "NJ Video Asset",
        {"lesson": lesson, "active": 1},
        ["asset_id", "duration"],
        as_dict=True,
    )
    if not asset:
        frappe.throw("No private video is attached to this lesson.")
    token = issue(
        secret(),
        member=member,
        session=frappe.session.sid,
        lesson=lesson,
        asset=asset.asset_id,
    )
    log(lesson, "grant")
    return dict(
        manifest=url(token, "index.m3u8"),
        token=token,
        expires_in=300,
        duration=asset.duration,
        watermark=member,
        position=frappe.db.get_value(
            "NJ Video Position", {"member": member, "lesson": lesson}, "position"
        )
        or 0,
    )


@frappe.whitelist()
@rate_limit(limit=600, seconds=60)
def resource(token, filename):
    member = user()
    try:
        claims = verify(secret(), token, member=member, session=frappe.session.sid)
    except ValueError:
        deny("Playback authorization expired. Reload the lesson.")
    require_lesson(claims["l"])
    if not frappe.db.exists(
        "NJ Video Asset", {"lesson": claims["l"], "asset_id": claims["a"], "active": 1}
    ):
        deny()
    root = os.environ.get("NIGHTJAR_MEDIA_ROOT")
    if not root:
        frappe.throw("Private media storage is not configured.")
    try:
        path = safe_path(root, claims["a"], filename)
    except (ValueError, OSError):
        deny("Media unavailable.")
    headers = {
        "Cache-Control": "private, no-store",
        "Pragma": "no-cache",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
    }
    if filename == "index.m3u8":
        lines = []
        for line in path.read_text().splitlines():
            if line.startswith("#EXT-X-KEY:"):
                line = line.replace('URI="key.bin"', f'URI="{url(token, "key.bin")}"')
            elif line and not line.startswith("#"):
                safe_path(root, claims["a"], line)
                line = url(token, line)
            lines.append(line)
        return Response(
            "\n".join(lines) + "\n",
            headers=headers,
            mimetype="application/vnd.apple.mpegurl",
        )
    if filename.endswith(".ts") and os.environ.get("NIGHTJAR_USE_ACCEL") == "1":
        headers["X-Accel-Redirect"] = f"/_nj_media/{claims['a']}/{filename}"
        return Response(headers=headers, mimetype="video/mp2t")
    return Response(
        path.read_bytes(),
        headers=headers,
        mimetype="video/mp2t"
        if filename.endswith(".ts")
        else "application/octet-stream",
    )


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=60)
def heartbeat(lesson, position, event="heartbeat"):
    member = user()
    course = require_lesson(lesson)
    if event not in {"heartbeat", "ended"}:
        frappe.throw("Invalid playback event.")
    duration = frappe.db.get_value(
        "NJ Video Asset", {"lesson": lesson, "active": 1}, "duration"
    )
    try:
        value = float(position)
    except (ValueError, TypeError):
        frappe.throw("Invalid playback position.")
    if not duration or not math.isfinite(value) or value < 0 or value > duration + 2:
        frappe.throw("Position is outside this video.")
    value = min(value, duration)
    frappe.db.get_value("User", member, "name", for_update=True)
    name = frappe.db.exists("NJ Video Position", {"member": member, "lesson": lesson})
    if name:
        frappe.db.set_value(
            "NJ Video Position", name, dict(position=value, duration=duration)
        )
    else:
        frappe.get_doc(
            dict(
                doctype="NJ Video Position",
                member=member,
                lesson=lesson,
                position=value,
                duration=duration,
            )
        ).insert(ignore_permissions=True)
    enrollment = frappe.db.exists(
        "LMS Enrollment", {"member": member, "course": course}
    )
    if enrollment:
        frappe.db.set_value("LMS Enrollment", enrollment, "current_lesson", lesson)
    log(lesson, event, value)
    return {"position": value}


def prune_events():
    frappe.db.delete(
        "NJ Playback Event", {"creation": ["<", add_days(now_datetime(), -30)]}
    )
