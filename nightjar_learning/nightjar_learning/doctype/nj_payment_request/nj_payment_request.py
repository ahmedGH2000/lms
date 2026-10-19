import frappe
from frappe.model.document import Document


class NJPaymentRequest(Document):
    def validate(self):
        from nightjar_learning.access import is_admin, deny

        old = self.get_doc_before_save()
        if self.is_new() and (
            self.status != "Pending" or self.reviewed_by or self.reviewed_at
        ):
            deny("New requests must be pending.")
        if old:
            if any(
                self.get(k) != old.get(k)
                for k in ("member", "course", "amount", "currency", "reference")
            ):
                deny("Payment identity and quote are immutable.")
            if not is_admin():
                deny("Only administrators may update requests.")
