import frappe
import json
from frappe.model.document import Document


DEFAULT_CORS_CONFIG = {
	"CORSRules": [
		{
			"AllowedHeaders": ["*"],
			"AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
			"AllowedOrigins": ["*"],
			"ExposeHeaders": ["ETag"],
			"MaxAgeSeconds": 3600,
		}
	]
}


class PlatineSettings(Document):
	def validate(self):
		for field in ("endpoint_url", "cdn_url"):
			value = self.get(field)
			if value and value.endswith("/"):
				frappe.throw(
					frappe._("The field {0} must not end with a trailing slash.").format(
						frappe.bold(self.meta.get_label(field))
					)
				)

	def on_update(self):
		pass


@frappe.whitelist()
def get_default_cors_config():
	return json.dumps(DEFAULT_CORS_CONFIG, indent=2)
