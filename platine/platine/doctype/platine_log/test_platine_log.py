# Copyright (c) 2026, Underscore Blank OÜ and Contributors
# See license.txt

from datetime import datetime
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


def _make_log(**kwargs):
    """Insert a minimal PlatineLog doc and return it."""
    defaults = {
        "doctype": "Platine Log",
        "event_type": "Upload",
        "status": "Success",
        "user": frappe.session.user,
    }
    defaults.update(kwargs)
    doc = frappe.get_doc(defaults)
    doc.insert(ignore_permissions=True)
    return doc


class IntegrationTestPlatineLog(IntegrationTestCase):
    """
    Unit tests for PlatineLog DocType.

    Tests cover:
    - autoname(): generated name format and datetime accuracy
    - Field acceptance for every allowed select value
    - Optional fields round-trip through the DB
    - log_event() utility: creates entry, stores values, swallows exceptions
    """

    # ── autoname ─────────────────────────────────────────────────────────

    def test_autoname_matches_expected_pattern(self):
        doc = _make_log()
        self.assertRegex(doc.name, r"^LOG-\d{2}-\d{2}-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}$")
        frappe.delete_doc("Platine Log", doc.name, ignore_permissions=True)

    def test_autoname_reflects_mocked_datetime(self):
        fixed_dt = datetime(2026, 4, 12, 15, 30, 45)
        target = "platine.platine.doctype.platine_log.platine_log.now_datetime"
        with patch(target, return_value=fixed_dt):
            doc = _make_log()
        self.assertTrue(
            doc.name.startswith("LOG-12-04-2026-15-30-45-"),
            f"Unexpected name: {doc.name}",
        )
        frappe.delete_doc("Platine Log", doc.name, ignore_permissions=True)

    def test_autoname_sequential_suffix_differs(self):
        """Two logs created in the same second get distinct names."""
        fixed_dt = datetime(2026, 4, 12, 10, 0, 0)
        target = "platine.platine.doctype.platine_log.platine_log.now_datetime"
        with patch(target, return_value=fixed_dt):
            doc1 = _make_log()
            doc2 = _make_log()
        self.assertNotEqual(doc1.name, doc2.name)
        frappe.delete_doc("Platine Log", doc1.name, ignore_permissions=True)
        frappe.delete_doc("Platine Log", doc2.name, ignore_permissions=True)

    # ── select field values ───────────────────────────────────────────────

    def test_all_event_types_accepted(self):
        for event_type in ("Upload", "Download", "Delete", "Migration", "Rollback", "CORS", "Connection"):
            doc = _make_log(event_type=event_type)
            self.assertEqual(doc.event_type, event_type)
            frappe.delete_doc("Platine Log", doc.name, ignore_permissions=True)

    def test_all_status_values_accepted(self):
        for status in ("Success", "Error"):
            doc = _make_log(status=status)
            self.assertEqual(doc.status, status)
            frappe.delete_doc("Platine Log", doc.name, ignore_permissions=True)

    # ── optional field round-trip ─────────────────────────────────────────

    def test_optional_fields_stored_and_retrieved(self):
        doc = _make_log(
            event_type="Upload",
            status="Success",
            file_name="photo.jpg",
            s3_key="private/files/photo.jpg",
            is_private=1,
            message="Presigned upload confirmed",
            duration_ms=123,
        )
        saved = frappe.get_doc("Platine Log", doc.name)
        self.assertEqual(saved.file_name, "photo.jpg")
        self.assertEqual(saved.s3_key, "private/files/photo.jpg")
        self.assertEqual(saved.is_private, 1)
        self.assertEqual(saved.message, "Presigned upload confirmed")
        self.assertEqual(saved.duration_ms, 123)
        frappe.delete_doc("Platine Log", doc.name, ignore_permissions=True)

    def test_is_private_defaults_to_zero(self):
        doc = _make_log()
        self.assertEqual(doc.is_private, 0)
        frappe.delete_doc("Platine Log", doc.name, ignore_permissions=True)

    # ── log_event utility ─────────────────────────────────────────────────

    def test_log_event_creates_one_entry(self):
        from platine.utils.logger import log_event

        before = frappe.db.count("Platine Log")
        log_event(event_type="Upload", status="Success", file_name="doc.pdf", s3_key="public/files/doc.pdf")
        self.assertEqual(frappe.db.count("Platine Log"), before + 1)

    def test_log_event_stores_correct_values(self):
        from platine.utils.logger import log_event

        log_event(
            event_type="Delete",
            status="Error",
            message="Object not found on S3",
            file_name="gone.pdf",
            s3_key="public/files/gone.pdf",
            is_private=False,
            duration_ms=42,
        )
        entry = frappe.get_last_doc(
            "Platine Log", filters={"event_type": "Delete", "status": "Error"}
        )
        self.assertEqual(entry.message, "Object not found on S3")
        self.assertEqual(entry.file_name, "gone.pdf")
        self.assertEqual(entry.s3_key, "public/files/gone.pdf")
        self.assertEqual(entry.is_private, 0)
        self.assertEqual(entry.duration_ms, 42)

    def test_log_event_records_user(self):
        from platine.utils.logger import log_event

        log_event(event_type="Connection", status="Success")
        entry = frappe.get_last_doc("Platine Log", filters={"event_type": "Connection"})
        self.assertEqual(entry.user, frappe.session.user)

    def test_log_event_swallows_exceptions_on_invalid_data(self):
        from platine.utils.logger import log_event

        # Invalid event_type value — must be silently swallowed, never raise
        try:
            log_event(event_type="__invalid__", status="Success")
        except Exception as exc:
            self.fail(f"log_event raised unexpectedly: {exc}")
