import os
import frappe
from frappe import _
from platine.utils.s3 import build_s3_key


@frappe.whitelist()
def relink_files():
    """
    Re-compute file_url for all public files stored on S3 using the current
    cdn_url and folder_prefix from Platine Settings.

    Run this after changing cdn_url or folder_prefix to avoid broken links.
    Private files are unaffected (their file_url is always a local path).
    """
    frappe.only_for("System Manager")

    settings = frappe.get_single("Platine Settings")
    cdn_base = (settings.cdn_url or settings.endpoint_url or "").rstrip("/")

    if not cdn_base:
        frappe.throw(_("CDN URL or Endpoint URL must be set in Platine Settings."))

    # All public files currently pointing to an HTTP URL (on S3 / CDN)
    files = frappe.get_all(
        "File",
        filters=[["file_url", "like", "http%"], ["is_private", "=", 0]],
        fields=["name", "file_name", "file_url"],
    )

    updated = 0
    errors = 0

    for f in files:
        try:
            filename = f["file_name"] or os.path.basename(f["file_url"])
            if not filename:
                continue
            new_url = f"{cdn_base}/{build_s3_key(filename, is_private=False)}"
            if new_url != f["file_url"]:
                frappe.db.set_value("File", f["name"], "file_url", new_url)
                updated += 1
        except Exception as e:
            errors += 1
            frappe.log_error(f"Platine relink — {f['name']}: {e}", "Platine Relink")

    frappe.db.commit()

    return {
        "success": errors == 0,
        "updated": updated,
        "errors": errors,
        "message": _("{0} file(s) updated, {1} error(s).").format(updated, errors),
    }
