import os

import frappe
from platine.utils.s3 import upload_file
from platine.utils.logger import log_event, Timer


def migrate_files():
    """Background job: migrate all local files to S3."""
    files = frappe.get_all(
        "File",
        filters=[
            ["file_url", "like", "/files/%"],
            ["file_url", "not like", "http%"],
        ],
        fields=["name", "file_name", "file_url", "is_private"],
        order_by="creation asc",
    )

    private_files = frappe.get_all(
        "File",
        filters=[
            ["file_url", "like", "/private/files/%"],
        ],
        fields=["name", "file_name", "file_url", "is_private"],
        order_by="creation asc",
    )

    all_files = files + private_files
    total = len(all_files)
    success = 0
    errors = 0

    _update_status(f"0/{total} files migrated")

    for i, f in enumerate(all_files):
        try:
            _migrate_single_file(f)
            success += 1
        except Exception as e:
            errors += 1
            frappe.log_error(f"S3 Migration — {f['name']}: {e}", "Platine Migration")
            log_event(event_type="Migration", status="Error", file_name=f.get("file_name", ""), s3_key="", message=str(e))

        if (i + 1) % 10 == 0 or (i + 1) == total:
            _update_status(f"{i+1}/{total} files migrated ({errors} errors)")

        frappe.db.commit()

    _update_status(f"Completed: {success} succeeded, {errors} errors out of {total}")
    log_event(
        event_type="Migration",
        status="Success" if errors == 0 else "Error",
        message=f"Completed: {success} succeeded, {errors} errors out of {total}",
    )


def _migrate_single_file(file_data):
    site_path = frappe.get_site_path()
    filename = file_data["file_name"] or os.path.basename(file_data["file_url"])
    is_private = file_data["is_private"]

    if is_private:
        local_path = os.path.join(site_path, "private", "files", filename)
        s3_key = f"private/{filename}"
    else:
        local_path = os.path.join(site_path, "public", "files", filename)
        s3_key = f"public/{filename}"

    if not os.path.exists(local_path):
        return

    cdn_url = upload_file(local_path, s3_key, is_private=is_private)
    os.remove(local_path)

    if not is_private and cdn_url:
        frappe.db.set_value("File", file_data["name"], "file_url", cdn_url)


def _update_status(status):
    frappe.db.set_value("Platine Settings", "Platine Settings", "migration_status", status)
    frappe.db.commit()
