import os

import frappe
from platine.utils.s3 import copy_object, delete_file, file_exists_on_s3
from platine.utils.logger import log_event


def reprefix_files(old_prefix: str, new_prefix: str):
    """
    Background job: move all S3 files from old_prefix to new_prefix.
    - Copies each object to the new key, then deletes the original.
    - Updates file_url for public files in the Frappe database.
    Called automatically when folder_prefix changes in Platine Settings.
    """
    settings = frappe.get_single("Platine Settings")
    cdn_base = (settings.cdn_url or settings.endpoint_url or "").rstrip("/")
    site_path = frappe.get_site_path()

    # --- Public files: file_url starts with CDN base ---
    public_files = []
    if cdn_base:
        public_files = frappe.get_all(
            "File",
            filters=[["file_url", "like", f"{cdn_base}/%"], ["is_private", "=", 0]],
            fields=["name", "file_name", "file_url", "is_private"],
            order_by="creation asc",
        )

    # --- Private files: local copy absent (on S3) ---
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

    _update_status(f"0/{total} files moved")

    for i, f in enumerate(all_files):
        try:
            _reprefix_single_file(f, old_prefix, new_prefix, cdn_base)
            success += 1
        except Exception as e:
            errors += 1
            frappe.log_error(f"Platine Reprefix — {f['name']}: {e}", "Platine Reprefix")
            log_event(
                event_type="Migration",
                status="Error",
                file_name=f.get("file_name", ""),
                s3_key="",
                message=str(e),
            )

        if (i + 1) % 10 == 0 or (i + 1) == total:
            _update_status(f"{i + 1}/{total} files moved ({errors} errors)")

        frappe.db.commit()

    summary = f"Reprefix completed: {success} succeeded, {errors} errors out of {total}"
    _update_status(summary)
    log_event(
        event_type="Migration",
        status="Success" if errors == 0 else "Error",
        message=summary,
    )


def _reprefix_single_file(file_data: dict, old_prefix: str, new_prefix: str, cdn_base: str):
    filename = file_data["file_name"] or os.path.basename(file_data["file_url"])
    is_private = bool(file_data["is_private"])
    kind = "private" if is_private else "public"

    old_key = f"{old_prefix}/{kind}/{filename}" if old_prefix else f"{kind}/{filename}"
    new_key = f"{new_prefix}/{kind}/{filename}" if new_prefix else f"{kind}/{filename}"

    if old_key == new_key:
        return

    if not file_exists_on_s3(old_key):
        return

    copy_object(old_key, new_key, is_private=is_private)
    delete_file(old_key)

    update = {"platine_s3_key": new_key}
    if not is_private and cdn_base:
        update["file_url"] = f"{cdn_base}/{new_key}"
    frappe.db.set_value("File", file_data["name"], update)


def _update_status(status: str):
    frappe.db.set_value("Platine Settings", "Platine Settings", "reprefix_status", status)
    frappe.db.commit()
