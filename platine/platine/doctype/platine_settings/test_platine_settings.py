# Copyright (c) 2026, Underscore Blank OÜ and Contributors
# See license.txt

import json
import frappe
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestPlatineSettings(IntegrationTestCase):
    """
    Unit tests for PlatineSettings (Single DocType).

    Tests cover:
    - validate(): trailing slash rejection on URL fields
    - validate(): MIME type format validation for stream_mime_types
    - get_default_cors_config(): shape and content of the default CORS payload
    """

    def _doc(self, **kwargs):
        """Return the live Settings doc with the given fields overridden (not saved)."""
        doc = frappe.get_single("Platine Settings")
        doc.update(kwargs)
        return doc

    # ── URL trailing slash ────────────────────────────────────────────────

    def test_endpoint_url_trailing_slash_rejected(self):
        with self.assertRaises(frappe.exceptions.ValidationError):
            self._doc(endpoint_url="https://s3.example.com/").validate()

    def test_cdn_url_trailing_slash_rejected(self):
        with self.assertRaises(frappe.exceptions.ValidationError):
            self._doc(cdn_url="https://cdn.example.com/").validate()

    def test_endpoint_url_without_trailing_slash_accepted(self):
        self._doc(endpoint_url="https://s3.example.com").validate()

    def test_cdn_url_without_trailing_slash_accepted(self):
        self._doc(cdn_url="https://cdn.example.com").validate()

    def test_empty_url_fields_accepted(self):
        self._doc(endpoint_url="", cdn_url="").validate()

    # ── MIME type validation ──────────────────────────────────────────────

    def test_valid_mime_types_accepted(self):
        self._doc(stream_mime_types="application/pdf\nimage/png\ntext/plain").validate()

    def test_single_mime_type_accepted(self):
        self._doc(stream_mime_types="application/pdf").validate()

    def test_empty_mime_types_accepted(self):
        self._doc(stream_mime_types="").validate()

    def test_none_mime_types_accepted(self):
        self._doc(stream_mime_types=None).validate()

    def test_blank_lines_ignored(self):
        # blank lines between valid types must not trigger an error
        self._doc(stream_mime_types="application/pdf\n\nimage/png\n").validate()

    def test_invalid_mime_type_rejected(self):
        with self.assertRaises(frappe.exceptions.ValidationError):
            self._doc(stream_mime_types="not-a-mime").validate()

    def test_mime_type_without_subtype_rejected(self):
        with self.assertRaises(frappe.exceptions.ValidationError):
            self._doc(stream_mime_types="application").validate()

    def test_mixed_valid_and_invalid_mime_types_rejected(self):
        with self.assertRaises(frappe.exceptions.ValidationError):
            self._doc(stream_mime_types="application/pdf\nbad mime\nimage/png").validate()

    def test_mime_type_with_plus_suffix_accepted(self):
        # e.g. application/vnd.api+json
        self._doc(stream_mime_types="application/vnd.api+json").validate()

    # ── get_default_cors_config ───────────────────────────────────────────

    def test_default_cors_config_returns_valid_json(self):
        from platine.platine.doctype.platine_settings.platine_settings import (
            get_default_cors_config,
        )
        raw = get_default_cors_config()
        parsed = json.loads(raw)
        self.assertIn("CORSRules", parsed)
        self.assertIsInstance(parsed["CORSRules"], list)
        self.assertGreater(len(parsed["CORSRules"]), 0)

    def test_default_cors_config_allows_required_methods(self):
        from platine.platine.doctype.platine_settings.platine_settings import (
            get_default_cors_config,
        )
        rule = json.loads(get_default_cors_config())["CORSRules"][0]
        for method in ("GET", "PUT", "POST", "DELETE", "HEAD"):
            self.assertIn(method, rule["AllowedMethods"])

    def test_default_cors_config_allows_all_origins(self):
        from platine.platine.doctype.platine_settings.platine_settings import (
            get_default_cors_config,
        )
        rule = json.loads(get_default_cors_config())["CORSRules"][0]
        self.assertIn("*", rule["AllowedOrigins"])

    def test_default_cors_config_exposes_etag(self):
        from platine.platine.doctype.platine_settings.platine_settings import (
            get_default_cors_config,
        )
        rule = json.loads(get_default_cors_config())["CORSRules"][0]
        self.assertIn("ETag", rule["ExposeHeaders"])

    def test_default_cors_config_has_positive_max_age(self):
        from platine.platine.doctype.platine_settings.platine_settings import (
            get_default_cors_config,
        )
        rule = json.loads(get_default_cors_config())["CORSRules"][0]
        self.assertGreater(rule["MaxAgeSeconds"], 0)
