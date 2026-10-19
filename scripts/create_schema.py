import json
from pathlib import Path

root = (
    Path(__file__).resolve().parents[1] / "nightjar_learning/nightjar_learning/doctype"
)


def f(n, t="Data", o=None, **k):
    return dict(
        fieldname=n,
        label=n.replace("_", " ").title(),
        fieldtype=t,
        **({"options": o} if o else {}),
        **k,
    )


def make(n, fields, cls, body):
    s = n.lower().replace(" ", "_")
    p = root / s
    p.mkdir(exist_ok=True)
    d = dict(
        doctype="DocType",
        name=n,
        module="Nightjar Learning",
        autoname="hash",
        engine="InnoDB",
        field_order=[x["fieldname"] for x in fields],
        fields=fields,
        track_changes=1,
        permissions=[
            dict(role="System Manager", read=1, write=1, create=1, delete=1, report=1)
        ],
        sort_field="modified",
        sort_order="DESC",
    )
    (p / (s + ".json")).write_text(json.dumps(d, indent=2) + "\n")
    (p / "__init__.py").write_text("")
    (p / (s + ".py")).write_text(
        "import frappe\nfrom frappe.model.document import Document\n\nclass "
        + cls
        + "(Document):\n"
        + body
        + "\n"
    )


# Payment Request schema/controller is maintained directly in the app;
# do not regenerate it here and erase receipt fields or permission guards.
make(
    "NJ Video Asset",
    [
        f("lesson", "Link", "Course Lesson", reqd=1, unique=1),
        f("asset_id", reqd=1, unique=1),
        f("duration", "Float", reqd=1),
        f("active", "Check", default=1),
        f("label"),
    ],
    "NJVideoAsset",
    """    def validate(self):
        import re
        from nightjar_learning.access import is_admin, deny
        if not is_admin(): deny()
        if not re.fullmatch(r'[a-f0-9]{32}',self.asset_id or '') or self.duration <= 0: frappe.throw('Use the asset ID and duration produced by the packager.')
""",
)
make(
    "NJ Video Position",
    [
        f("member", "Link", "User", reqd=1),
        f("lesson", "Link", "Course Lesson", reqd=1),
        f("position", "Float"),
        f("duration", "Float"),
    ],
    "NJVideoPosition",
    "    pass",
)
make(
    "NJ Playback Event",
    [
        f("member", "Link", "User", reqd=1),
        f("lesson", "Link", "Course Lesson", reqd=1),
        f("event", "Select", "grant\nheartbeat\nended", reqd=1),
        f("position", "Float"),
    ],
    "NJPlaybackEvent",
    "    pass",
)
