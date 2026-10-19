import frappe
from frappe.model.document import Document


class NJVideoAsset(Document):
    def validate(self):
        import re
        from nightjar_learning.access import is_admin, deny

        if not is_admin():
            deny()
        if not re.fullmatch(r"[a-f0-9]{32}", self.asset_id or "") or self.duration <= 0:
            frappe.throw("Use the asset ID and duration produced by the packager.")
