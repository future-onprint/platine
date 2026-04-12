import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import now_datetime


class PlatineLog(Document):
    def autoname(self):
        dt = now_datetime()
        prefix = dt.strftime("LOG-%d-%m-%Y-%H-%M-%S-")
        self.name = make_autoname(prefix + ".##")
