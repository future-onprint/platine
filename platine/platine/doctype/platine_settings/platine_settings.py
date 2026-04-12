import re
import frappe
import json
from frappe.model.document import Document

_MIME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9!#$&\-^_]*/[a-zA-Z0-9][a-zA-Z0-9!#$&\-^_.+]*$")


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
		if self.enabled:
			required = ("access_key", "secret_key", "endpoint_url", "bucket_name", "region", "cdn_url")
			missing = [
				frappe.bold(self.meta.get_label(f))
				for f in required
				if not self.get(f)
			]
			if missing:
				frappe.throw(
					frappe._("The following fields are required to enable the S3 integration: {0}").format(
						", ".join(missing)
					)
				)

		for field in ("endpoint_url", "cdn_url"):
			value = self.get(field)
			if value and value.endswith("/"):
				frappe.throw(
					frappe._("The field {0} must not end with a trailing slash.").format(
						frappe.bold(self.meta.get_label(field))
					)
				)

		if self.stream_mime_types:
			invalid = [
				line.strip()
				for line in self.stream_mime_types.splitlines()
				if line.strip() and not _MIME_RE.match(line.strip())
			]
			if invalid:
				frappe.throw(
					frappe._("Invalid MIME type(s) in {0}: {1}").format(
						frappe.bold(self.meta.get_label("stream_mime_types")),
						", ".join(frappe.bold(v) for v in invalid),
					)
				)

	def before_save(self):
		self._old_folder_prefix = (
			frappe.db.get_single_value("Platine Settings", "folder_prefix") or ""
		)

	def on_update(self):
		old_prefix = getattr(self, "_old_folder_prefix", None)
		new_prefix = self.folder_prefix or ""
		if old_prefix is not None and old_prefix != new_prefix:
			frappe.enqueue(
				"platine.reprefix.reprefix_files",
				queue="long",
				timeout=7200,
				job_id="platine_reprefix",
				deduplicate=True,
				old_prefix=old_prefix,
				new_prefix=new_prefix,
			)


@frappe.whitelist()
def get_default_cors_config():
	return json.dumps(DEFAULT_CORS_CONFIG, indent=2)
