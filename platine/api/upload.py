import frappe
import os
from platine.utils.s3 import generate_presigned_put


@frappe.whitelist()
def get_presigned_upload_url(filename, is_private=0, content_type="application/octet-stream"):
    """
    Generate a presigned PUT URL for direct browser -> S3 upload.
    Returns: { upload_url, s3_key, cdn_url (if public) }
    """
    frappe.has_permission("File", "create", throw=True)

    is_private = frappe.utils.cint(is_private)

    # Sanitize filename
    filename = os.path.basename(filename)

    s3_key = f"{'private' if is_private else 'public'}/{filename}"

    upload_url = generate_presigned_put(
        s3_key=s3_key,
        content_type=content_type,
        is_private=bool(is_private),
    )

    result = {
        "upload_url": upload_url,
        "s3_key": s3_key,
        "is_private": bool(is_private),
    }

    if not is_private:
        settings = frappe.get_single("Platine Settings")
        result["cdn_url"] = f"{settings.cdn_url.rstrip('/')}/{s3_key}"

    return result


@frappe.whitelist()
def confirm_upload(s3_key, filename, is_private=0, doctype=None, docname=None, folder="Home/Attachments"):
    """
    Called after successful direct S3 upload.
    Creates the corresponding Frappe File doc.
    """
    frappe.has_permission("File", "create", throw=True)

    is_private = frappe.utils.cint(is_private)
    settings = frappe.get_single("Platine Settings")

    if is_private:
        file_url = f"/private/files/{os.path.basename(filename)}"
    else:
        file_url = f"{settings.cdn_url.rstrip('/')}/{s3_key}"

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": os.path.basename(filename),
        "file_url": file_url,
        "is_private": is_private,
        "folder": folder,
        "attached_to_doctype": doctype,
        "attached_to_name": docname,
    })

    # Disable our after_insert hook for this doc (already on S3)
    file_doc.flags.platine_skip_upload = True
    file_doc.insert()

    return {"name": file_doc.name, "file_url": file_url}
