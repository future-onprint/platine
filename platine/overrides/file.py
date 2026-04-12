import os
import frappe
from frappe import _
from platine.utils.logger import log_event, Timer


def is_platine_enabled():
    try:
        return frappe.db.get_single_value("Platine Settings", "enabled")
    except Exception:
        return False


def get_s3_key_for_file(file_doc):
    """Determine the s3_key for a File doc."""
    from platine.utils.s3 import build_s3_key
    filename = file_doc.file_name or os.path.basename(file_doc.file_url or "")
    return build_s3_key(filename, is_private=bool(file_doc.is_private))


def after_insert(doc, method=None):
    """
    Hook after_insert on File.
    - Check Platine is enabled
    - Skip external URLs (already on S3 or other)
    - Generate thumbnail BEFORE S3 upload
    - Upload original + thumbnail to S3
    - Remove local files
    - Update file_url for public files (direct CDN URL)
    """
    if not is_platine_enabled():
        return

    # Skip if already uploaded via presigned URL
    if doc.flags.get("platine_skip_upload"):
        return

    # Skip external URLs
    if doc.file_url and (doc.file_url.startswith("http://") or doc.file_url.startswith("https://")):
        return

    # Skip if no local file
    if not doc.file_url:
        return

    from platine.utils.s3 import upload_file, build_s3_key

    # Local file path
    site_path = frappe.get_site_path()
    if doc.is_private:
        local_path = os.path.join(site_path, "private", "files", doc.file_name)
    else:
        local_path = os.path.join(site_path, "public", "files", doc.file_name)

    if not os.path.exists(local_path):
        return

    s3_key = get_s3_key_for_file(doc)

    with Timer() as t:
        try:
            # Generate thumbnail if image (BEFORE S3 upload)
            thumbnail_local_path = None
            thumbnail_s3_key = None
            if _is_image(doc.file_name):
                thumbnail_local_path = _generate_thumbnail(doc, local_path)
                if thumbnail_local_path:
                    thumb_filename = os.path.basename(thumbnail_local_path)
                    thumbnail_s3_key = build_s3_key(thumb_filename, is_private=bool(doc.is_private))

            # Upload original file
            cdn_url = upload_file(local_path, s3_key, is_private=doc.is_private)

            # Upload thumbnail if generated
            if thumbnail_local_path and os.path.exists(thumbnail_local_path):
                upload_file(thumbnail_local_path, thumbnail_s3_key, is_private=doc.is_private)
                os.remove(thumbnail_local_path)

            # Remove local original file
            os.remove(local_path)

            # Persist S3 key on the File doc for reliable future lookups
            frappe.db.set_value("File", doc.name, "platine_s3_key", s3_key)
            doc.platine_s3_key = s3_key

            # Update file_url for public files (direct CDN URL)
            if not doc.is_private and cdn_url:
                frappe.db.set_value("File", doc.name, "file_url", cdn_url)
                doc.file_url = cdn_url

            log_event(
                event_type="Upload",
                status="Success",
                file_name=doc.file_name or "",
                s3_key=s3_key,
                is_private=bool(doc.is_private),
                duration_ms=t.elapsed_ms,
            )

        except Exception as e:
            frappe.log_error(f"Platine: S3 upload error for {doc.name}: {e}", "Platine S3 Upload")
            log_event(
                event_type="Upload",
                status="Error",
                file_name=doc.file_name or "",
                s3_key="",
                is_private=bool(doc.is_private),
                message=str(e),
            )


def on_trash(doc, method=None):
    """
    Hook on_trash on File.
    Delete the S3 object and its thumbnail (if any).
    Skips head_object check — delete_file handles NoSuchKey gracefully.
    """
    if not is_platine_enabled():
        return

    from platine.utils.s3 import delete_file, get_s3_key_from_file_url, build_s3_key

    file_name = doc.file_name or ""

    # ── Main object ──────────────────────────────────────────────────────────
    try:
        # Prefer stored key; fall back to URL parsing for legacy docs
        s3_key = doc.get("platine_s3_key") or get_s3_key_from_file_url(doc.file_url)
        if not s3_key:
            log_event(event_type="Delete", status="Error", file_name=file_name,
                      s3_key="", is_private=bool(doc.is_private),
                      message=f"Could not resolve S3 key from file_url: {doc.file_url}")
            return
        delete_file(s3_key)
        log_event(event_type="Delete", status="Success", file_name=file_name,
                  s3_key=s3_key, is_private=bool(doc.is_private))
    except Exception as e:
        frappe.log_error(f"Platine: S3 deletion error for {doc.name}: {e}", "Platine S3 Delete")
        log_event(event_type="Delete", status="Error", file_name=file_name,
                  s3_key="", is_private=bool(doc.is_private), message=str(e))
        return

    # ── Thumbnail (uploaded by after_insert, no separate File doc) ───────────
    if file_name and _is_image(file_name):
        try:
            thumb_key = build_s3_key(f"thumb_{file_name}", is_private=bool(doc.is_private))
            delete_file(thumb_key)
        except Exception as e:
            frappe.log_error(f"Platine: thumbnail deletion error for {doc.name}: {e}", "Platine S3 Delete")


def download_file(file_url=None):
    """
    Override of frappe.core.doctype.file.file.download_file.
    If file is on S3 -> presigned URL -> 302 redirect.
    Otherwise fallback to native Frappe behavior.
    """
    if not is_platine_enabled():
        return _frappe_download_file(file_url)

    from platine.utils.s3 import generate_presigned_get, get_s3_key_from_file_url, file_exists_on_s3

    try:
        s3_key = get_s3_key_from_file_url(file_url)
        if s3_key and file_exists_on_s3(s3_key):
            settings = frappe.get_single("Platine Settings")
            expiry = (settings.presigned_url_expiry or 60) * 60
            filename = os.path.basename(file_url or "")
            presigned_url = generate_presigned_get(s3_key, expiry_seconds=expiry, filename=filename)
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = presigned_url
            if frappe.db.get_single_value("Platine Settings", "log_downloads_enabled"):
                log_event(event_type="Download", status="Success", file_name=os.path.basename(file_url or ""), s3_key=s3_key)
            return
    except Exception as e:
        frappe.log_error(f"Platine: presigned URL error for {file_url}: {e}", "Platine S3 Download")
        if frappe.db.get_single_value("Platine Settings", "log_downloads_enabled"):
            log_event(event_type="Download", status="Error", file_name=os.path.basename(file_url or ""), s3_key="", message=str(e))

    # Native fallback
    return _frappe_download_file(file_url)


def _frappe_download_file(file_url):
    """Call native Frappe download_file."""
    from frappe.core.doctype.file.file import download_file as frappe_download_file
    return frappe_download_file(file_url=file_url)


def _is_image(filename):
    if not filename:
        return False
    ext = os.path.splitext(filename)[1].lower()
    return ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}


def _generate_thumbnail(doc, local_path):
    """
    Generate a thumbnail locally.
    Returns the local path of the thumbnail or None.
    """
    try:
        import PIL.Image as Image

        thumb_filename = f"thumb_{os.path.basename(local_path)}"
        if doc.is_private:
            thumb_path = os.path.join(frappe.get_site_path(), "private", "files", thumb_filename)
        else:
            thumb_path = os.path.join(frappe.get_site_path(), "public", "files", thumb_filename)

        with Image.open(local_path) as img:
            img.thumbnail((300, 300))
            img.save(thumb_path)

        return thumb_path if os.path.exists(thumb_path) else None
    except Exception:
        return None
