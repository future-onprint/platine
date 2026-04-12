import frappe
from platine.utils.s3 import generate_presigned_get, get_s3_key_from_file_url


@frappe.whitelist()
def generate_share_link(file_name, expiry_seconds=None):
	"""
	Generate a share link for a file.
	- Public file: returns the direct CDN URL
	- Private file: returns a presigned URL with chosen expiry

	expiry_seconds: int (None = read from Settings)
	"""
	doc = frappe.get_doc("File", file_name)

	if not frappe.has_permission("File", "read", doc=doc):
		frappe.throw(frappe._("Access denied"), frappe.PermissionError)

	if not doc.is_private:
		return {
			"url": doc.file_url,
			"expires": None,
			"is_private": False,
		}

	s3_key = doc.get("platine_s3_key") or get_s3_key_from_file_url(doc.file_url)
	if not s3_key:
		frappe.throw(
			frappe._("Cannot generate a share link: file {0} is not stored on S3.").format(
				frappe.bold(doc.file_name)
			)
		)

	expiry = int(expiry_seconds) if expiry_seconds else None
	url = generate_presigned_get(s3_key, expiry_seconds=expiry)

	actual_expiry = expiry or (frappe.get_single("Platine Settings").presigned_url_expiry * 60)

	return {
		"url": url,
		"expires_in_seconds": actual_expiry,
		"is_private": True,
	}
