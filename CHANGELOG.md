# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] — 2026-04-12

### Added

- **Unique S3 keys** — a random 8-character hex suffix is appended before the file extension on every upload (`photo.jpg` → `photo-a3f9bc12.jpg`), preventing collisions when two files share the same name.

### Fixed

- **`platine_s3_key` column missing during migration** — moved the custom field definition from `hooks.py` (`custom_fields`) to a Frappe fixture (`fixtures/custom_field.json`). The fixture is applied during `bench migrate` before any app code runs, so the column is guaranteed to exist when `migrate_files()` writes to it.
- **Privacy change with random-suffix keys** — `_handle_s3_privacy_change` now derives the new S3 key by flipping the `public`/`private` segment in the stored key instead of reconstructing it from the filename (reconstruction is impossible once a random suffix is in play).
- **`validate_file_on_disk` with random-suffix keys** — reads `platine_s3_key` directly from the File doc instead of reconstructing the key.

---

## [1.0.0] — 2026-04-12

First production release.

### Added

- **S3 integration** — upload, download, delete for public and private files via any S3-compatible store (AWS, Scaleway, Cloudflare R2, MinIO).
- **Presigned PUT upload** — browser uploads directly to S3; Frappe server handles only signing and confirmation. Progress tracked in the upload dialog.
- **Presigned GET download** — all downloads redirect to a short-lived signed S3 URL; file content never transits through Frappe.
- **`platine_s3_key` custom field** — exact S3 object key stored on every `File` document for reliable deletion without URL parsing.
- **Privacy change** — moving a file between public and private copies the S3 object with the correct ACL, deletes the original, and updates `file_url` and `platine_s3_key`.
- **Background migration** — scans all local `File` documents and uploads them to S3.
- **Background rollback** — downloads all S3 files back to local storage; run before disabling the integration.
- **Folder prefix change** — changing `Folder Prefix` in Settings automatically starts a background reprefix job (copy → delete → update URLs).
- **CDN support** — public files served through a configurable CDN URL; presigned URLs point directly to the S3 endpoint (CDN cannot proxy signed requests).
- **Safari streaming fix** — configurable MIME type list for streaming private files through Frappe instead of redirecting (fixes embedded PDF preview in Safari).
- **Share links** — Share button on the File form; public files return the CDN URL, private files generate a presigned URL with selectable expiry (15 min / 1 h / 24 h / 7 days).
- **CORS management** — view and apply bucket CORS configuration directly from Settings.
- **Relink** — re-computes `file_url` for all public S3 files after a CDN or prefix change without re-uploading.
- **Audit log** — `Platine Log` doctype records every upload, download, delete, migration, rollback, CORS, and connection event with user, duration, and S3 key.
- **Daily log cleanup** — scheduled job purges log entries older than the configured retention period.
- **French translations** — full `fr.csv` covering all UI labels and error messages.
- **Unit tests** — `IntegrationTestCase` suites for `Platine Settings` (URL validation, MIME type validation, default CORS config) and `Platine Log` (autoname, field round-trip, `log_event` utility).

### Security

- Admin-only endpoints (`test_connection`, `get_cors_config`, `set_cors_config`) restricted to System Manager via `frappe.only_for`.
- `confirm_upload` validates ownership via a short-lived Redis token issued by `get_presigned_upload_url`; cross-user key injection is rejected.
- Share link generation returns a clear error if the file is not on S3 (no silent null key passed to boto3).

### Changed

- `PlatineSettings.validate()` enforces all required credentials and URLs when the integration is enabled. `cdn_url` is optional — `endpoint_url` is used as fallback for public file URLs when no CDN is configured.
- Presigned upload path now falls back to `endpoint_url` when `cdn_url` is empty, consistent with the standard upload path.
