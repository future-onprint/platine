import frappe
import os
from platine.utils.s3 import generate_presigned_put, build_s3_key, set_object_acl
from platine.utils.logger import log_event

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}


def _is_image(filename):
    if not filename:
        return False
    return os.path.splitext(filename)[1].lower() in _IMAGE_EXTENSIONS


def _generate_and_upload_thumbnail(file_doc, s3_key, is_private):
    """Download original from S3, generate thumbnail, upload, store key on File doc."""
    import tempfile
    from platine.utils.s3 import download_file, upload_file

    if not _is_image(file_doc.file_name):
        return

    ext = os.path.splitext(file_doc.file_name)[1]
    tmp_original = None
    tmp_thumb = None

    try:
        import PIL.Image as Image

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            tmp_original = f.name
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            tmp_thumb = f.name

        download_file(s3_key, tmp_original)

        with Image.open(tmp_original) as img:
            img.thumbnail((300, 300))
            img.save(tmp_thumb)

        thumb_filename = f"thumb_{file_doc.file_name}"
        thumb_key = build_s3_key(thumb_filename, is_private=is_private)
        upload_file(tmp_thumb, thumb_key, is_private=is_private)

        frappe.db.set_value("File", file_doc.name, "platine_s3_thumbnail_key", thumb_key)
        file_doc.platine_s3_thumbnail_key = thumb_key

    except Exception as e:
        frappe.log_error(
            f"Platine: thumbnail generation error for presigned upload {file_doc.name}: {e}",
            "Platine S3 Upload",
        )
    finally:
        for path in (tmp_original, tmp_thumb):
            if path and os.path.exists(path):
                os.remove(path)


_PENDING_KEY_PREFIX = "platine_pending_upload:"


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

    settings = frappe.get_single("Platine Settings")

    s3_key = build_s3_key(filename, is_private=bool(is_private))

    expiry_seconds = (settings.presigned_url_expiry or 60) * 60

    upload_url = generate_presigned_put(
        s3_key=s3_key,
        content_type=content_type,
        is_private=bool(is_private),
    )

    # Register the pending upload in Redis so confirm_upload can verify ownership.
    frappe.cache().set_value(
        f"{_PENDING_KEY_PREFIX}{s3_key}",
        frappe.session.user,
        expires_in_sec=expiry_seconds,
    )

    result = {
        "upload_url": upload_url,
        "s3_key": s3_key,
        "is_private": bool(is_private),
    }

    if not is_private:
        public_base = (settings.cdn_url or settings.endpoint_url or "").rstrip("/")
        result["cdn_url"] = f"{public_base}/{s3_key}"

    return result


@frappe.whitelist()
def confirm_upload(s3_key, filename, is_private=0, file_size=0, doctype=None, docname=None, folder="Home/Attachments"):
    """
    Called after successful direct S3 upload.
    Creates the corresponding Frappe File doc.
    """
    frappe.has_permission("File", "create", throw=True)

    # Verify the s3_key was issued to the current user by get_presigned_upload_url.
    pending_user = frappe.cache().get_value(f"{_PENDING_KEY_PREFIX}{s3_key}")
    if pending_user != frappe.session.user:
        frappe.throw(frappe._("Invalid or expired upload token."), frappe.PermissionError)
    frappe.cache().delete_value(f"{_PENDING_KEY_PREFIX}{s3_key}")

    is_private = frappe.utils.cint(is_private)
    file_size = frappe.utils.cint(file_size)
    settings = frappe.get_single("Platine Settings")

    if is_private:
        file_url = f"/private/files/{os.path.basename(filename)}"
    else:
        public_base = (settings.cdn_url or settings.endpoint_url or "").rstrip("/")
        file_url = f"{public_base}/{s3_key}"

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": os.path.basename(filename),
        "file_url": file_url,
        "is_private": is_private,
        "folder": folder,
        "attached_to_doctype": doctype,
        "attached_to_name": docname,
        "platine_s3_key": s3_key,
        "file_size": file_size,
    })

    # Apply ACL on the S3 object — presigned PUT skips ACL in the signature,
    # so we enforce it server-side after the upload completes.
    set_object_acl(s3_key, is_private=bool(is_private))

    # Disable our after_insert hook for this doc (already on S3)
    file_doc.flags.platine_skip_upload = True
    file_doc.insert()

    # Generate thumbnail for image uploads (after_insert is skipped for presigned uploads)
    if _is_image(os.path.basename(filename)):
        _generate_and_upload_thumbnail(file_doc, s3_key, is_private=bool(is_private))

    log_event(
        event_type="Upload",
        status="Success",
        message="Presigned upload confirmed",
        file_name=os.path.basename(filename),
        s3_key=s3_key,
        is_private=bool(is_private),
    )

    return file_doc.as_dict()
