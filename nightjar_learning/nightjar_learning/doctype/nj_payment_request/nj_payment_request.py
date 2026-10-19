import frappe
from frappe.model.document import Document


class NJPaymentRequest(Document):
    def validate(self):
        from nightjar_learning.access import deny
        from nightjar_learning.payments import can_review
        old = self.get_doc_before_save()
        if self.is_new():
            if getattr(frappe.flags, "nightjar_payment_create", None) != (self.course, self.member):
                deny("Submit enrollment requests through Nightjar.")
            if self.status != "Pending" or self.reviewed_by or self.reviewed_at:
                deny("New requests must be pending.")
        if old:
            if any(self.get(k) != old.get(k) for k in
                   ("member", "course", "amount", "currency", "reference", "receipt_key", "receipt_name", "receipt_size", "receipt_type")):
                deny("Payment details and receipts cannot be replaced after submission.")
            if getattr(frappe.flags, "nightjar_payment_review", None) != (self.name, self.status) or not can_review(self.course):
                deny("Use Payment requests in the teaching studio to review this request.")

    def on_trash(self):
        # Keep the file until the database transaction commits successfully.
        from nightjar_learning.receipts import remove_receipt
        key = self.receipt_key
        if key:
            frappe.db.after_commit.add(lambda: remove_receipt(key))
