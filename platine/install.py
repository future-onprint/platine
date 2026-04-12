import frappe
import json
from platine.platine.doctype.platine_settings.platine_settings import DEFAULT_CORS_CONFIG


def after_install():
	settings = frappe.get_single("Platine Settings")
	if not settings.cors_config:
		settings.cors_config = json.dumps(DEFAULT_CORS_CONFIG, indent=2)
		settings.save()
		frappe.db.commit()
