import os

import frappe
from platine.utils.s3 import download_file, file_exists_on_s3, build_s3_key
from platine.utils.logger import log_event, Timer


def rollback_files():
    """
    Background job: download all S3 files back to local storage and restore
    local file_url paths so Frappe can serve them natively again.

    - Public files: file_url is a CDN URL  → download from S3 → restore to /files/
    - Private files: file_url is local path but file absent on disk → download from S3
    """
    settings = frappe.get_single("Platine Settings")
    cdn_base = (settings.cdn_url or "").rstrip("/")
    bucket_name = settings.bucket_name or ""
    site_path = frappe.get_site_path()

    # --- Collect public files on S3 (file_url starts with CDN base) ---
    public_files = []
    if cdn_base:
        public_files = frappe.get_all(
            "File",
            filters=[["file_url", "like", f"{cdn_base}/%"]],
            fields=["name", "file_name", "file_url", "is_private"],
            order_by="creation asc",
        )

    # --- Collect private files on S3 (local copy absent) ---
    all_private = frappe.get_all(
        "File",
        filters=[["file_url", "like", "/private/files/%"]],
        fields=["name", "file_name", "file_url", "is_private"],
        order_by="creation asc",
    )
    private_files = []
    for f in all_private:
        filename = f["file_name"] or os.path.basename(f["file_url"])
        local_path = os.path.join(site_path, "private", "files", filename)
        if not os.path.exists(local_path):
            private_files.append(f)

    all_files = public_files + private_files
    total = len(all_files)
    success = 0
    errors = 0

    _update_status(f"0/{total} files restored")

    for i, f in enumerate(all_files):
        try:
            _rollback_single_file(f, cdn_base, bucket_name, site_path)
            success += 1
        except Exception as e:
            errors += 1
            frappe.log_error(
                f"S3 Rollback — {f['name']}: {e}", "Platine Rollback"
            )
            log_event(event_type="Rollback", status="Error", file_name=f.get("file_name", ""), s3_key="", message=str(e))

        if (i + 1) % 10 == 0 or (i + 1) == total:
            _update_status(f"{i+1}/{total} files restored ({errors} errors)")

        frappe.db.commit()

    _update_status(f"Rollback completed: {success} succeeded, {errors} errors out of {total}")
    log_event(
        event_type="Rollback",
        status="Success" if errors == 0 else "Error",
        message=f"Rollback completed: {success} succeeded, {errors} errors out of {total}",
    )


def _rollback_single_file(file_data: dict, cdn_base: str, bucket_name: str, site_path: str):
    """Download one file from S3 and restore its local path."""
    file_url = file_data["file_url"] or ""
    filename = file_data["file_name"] or os.path.basename(file_url)
    is_private = file_data["is_private"]

    # Derive the S3 key
    if file_url.startswith(cdn_base):
        # Public file: strip cdn_base/ prefix → s3_key
        s3_key = file_url[len(cdn_base):].lstrip("/")
    else:
        # Private file: derive key with folder prefix
        s3_key = build_s3_key(filename, is_private=True)

    if not file_exists_on_s3(s3_key):
        return  # Nothing on S3 to restore, skip

    # Build the local destination path
    if is_private:
        local_path = os.path.join(site_path, "private", "files", filename)
    else:
        local_path = os.path.join(site_path, "public", "files", filename)

    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    download_file(s3_key, local_path)

    # Restore file_url to the standard Frappe local path
    local_file_url = f"/private/files/{filename}" if is_private else f"/files/{filename}"
    frappe.db.set_value("File", file_data["name"], "file_url", local_file_url)


def _update_status(status: str):
    frappe.db.set_value("Platine Settings", "Platine Settings", "rollback_status", status)
    frappe.db.commit()
