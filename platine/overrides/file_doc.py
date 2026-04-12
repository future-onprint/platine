import os
import frappe
from frappe.core.doctype.file.file import File

_URL_PREFIXES = ("http://", "https://")


class PlatineFile(File):
    """
    Extends Frappe's File document to handle is_private changes for S3 files.
    Frappe's default handle_is_private_changed() throws FileNotFoundError when
    the file is not on disk. We intercept it to move the S3 object instead.
    """

    def before_insert(self):
        if not self.flags.get("platine_skip_upload"):
            return super().before_insert()

        # File is already on S3 (presigned upload). Run the standard setup
        # steps but skip save_file / get_content — the file is not on disk.
        # Only private files hit this path; public files have a CDN URL so
        # is_remote_file is True and Frappe skips save_file on its own.
        if hasattr(frappe.local, "rollback_observers"):
            frappe.local.rollback_observers.append(self)
        self.set_folder_name()
        self.validate_attachment_limit()
        self.set_file_type()
        self.validate_file_extension()

    def validate_file_on_disk(self):
        """
        Override Frappe's check to skip the on-disk assertion when the file
        lives on S3. After handle_is_private_changed() updates file_url to a
        local-style path (/private/files/...), Frappe would throw because the
        file is not physically on disk — but it exists on S3.
        """
        full_path = self.get_full_path()

        if full_path.startswith(_URL_PREFIXES):
            return True

        if os.path.exists(full_path):
            return True

        try:
            enabled = frappe.db.get_single_value("Platine Settings", "enabled")
        except Exception:
            enabled = False

        if enabled:
            from platine.utils.s3 import file_exists_on_s3

            s3_key = self.get("platine_s3_key")
            if s3_key and file_exists_on_s3(s3_key):
                return True

        frappe.throw(frappe._("File {0} does not exist").format(self.file_url), IOError)

    def handle_is_private_changed(self):
        if not self.has_value_changed("is_private"):
            return

        try:
            enabled = frappe.db.get_single_value("Platine Settings", "enabled")
        except Exception:
            enabled = False

        if not enabled:
            return super().handle_is_private_changed()

        old_doc = self.get_doc_before_save()
        old_file_url = (old_doc.file_url if old_doc else None) or self.file_url

        # If the file exists locally, let Frappe handle it normally
        local_path = os.path.join(frappe.get_site_path(), old_file_url.lstrip("/"))
        if os.path.exists(local_path):
            return super().handle_is_private_changed()

        # File is on S3 — move it and update the URL
        self._handle_s3_privacy_change(old_doc)

    def _handle_s3_privacy_change(self, old_doc):
        from platine.utils.s3 import (
            copy_object,
            delete_file,
            file_exists_on_s3,
            get_settings,
        )

        new_is_private = bool(self.is_private)

        # Always derive old_key from the stored field — never reconstruct it,
        # since the key contains a random suffix that cannot be recomputed.
        old_key = (old_doc and old_doc.get("platine_s3_key")) or self.get("platine_s3_key")
        if not old_key:
            return

        # Derive new_key by flipping the public/private segment in the existing key.
        if new_is_private:
            new_key = old_key.replace("/public/", "/private/", 1)
        else:
            new_key = old_key.replace("/private/", "/public/", 1)

        if old_key == new_key:
            return

        if not file_exists_on_s3(old_key):
            return

        copy_object(old_key, new_key, is_private=new_is_private)
        delete_file(old_key)

        self.platine_s3_key = new_key

        filename = self.file_name or os.path.basename(self.file_url or "")
        if new_is_private:
            self.file_url = f"/private/files/{filename}"
        else:
            s = get_settings()
            cdn_base = (s.cdn_url or s.endpoint_url).rstrip("/")
            self.file_url = f"{cdn_base}/{new_key}"
