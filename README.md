<div align="center">

# 🪣 Platine

**S3-compatible object storage bridge for the Frappe ecosystem.**

[![Python](https://img.shields.io/badge/python-3.14+-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Frappe](https://img.shields.io/badge/frappe-v16-0089ff?style=flat-square)](https://frappeframework.com)
[![License](https://img.shields.io/badge/license-AGPL--3.0-green?style=flat-square)](license.txt)

*A project by [Underscore Blank OÜ](mailto:contact@underscore-blank.io)*

</div>

---

## About

**Platine** is a standalone Frappe app that offloads all file storage to any S3-compatible object store (AWS S3, Scaleway Object Storage, Cloudflare R2, MinIO, etc.). It has **no ERPNext dependency** and works with any Frappe v16 installation.

Files are transparently stored on S3 with proper ACLs, served through your CDN via time-limited presigned URLs, and never transit through the Frappe server on download. A built-in migration tool handles existing installations with local files.

---

## Features

### File lifecycle

| Operation | Behaviour |
|---|---|
| **Upload (standard)** | File written locally by Frappe → `after_insert` hook uploads to S3, removes local copy |
| **Upload (presigned)** | `PlatineFileUploader` intercepts Frappe's upload dialog → browser PUTs directly to S3 via a presigned URL → `confirm_upload` creates the `File` doc with correct size and S3 key |
| **Download** | Frappe checks permissions → generates a short-lived presigned `GET` URL → `302` redirect → client downloads directly from S3 / CDN |
| **Delete** | `on_trash` reads `platine_s3_key` from the `File` doc (falls back to URL parsing for legacy docs) → deletes main object and any orphaned thumbnail from S3 |
| **Privacy change** | Moving a file between public and private copies the S3 object to the correct prefix with the new ACL, deletes the original, and updates `file_url` and `platine_s3_key` |
| **Thumbnails** | Generated locally before the original is uploaded, then both are pushed to S3 together |

### S3 key tracking

Every `File` document gains a `platine_s3_key` custom field that stores the exact S3 object key. This field is written by every code path that puts a file on S3 (standard upload, presigned upload, migration, reprefix, privacy change) and read by `on_trash` for reliable deletion — no URL parsing required.

### Access control

- **Public files** — uploaded with `public-read` ACL; `file_url` is set to the CDN URL directly.
- **Private files** — uploaded with `private` ACL; served exclusively via time-limited presigned URLs.
- **Presigned upload ACL** — the presigned `PUT` URL does not include an ACL (avoids 403 on buckets with ACL enforcement disabled). The correct ACL is applied server-side via `put_object_acl` after the browser confirms the upload.

### Presigned upload

When enabled, `PlatineFileUploader` extends `frappe.ui.FileUploader` and is patched in at load time via `Object.defineProperty`. Files with actual content are PUT directly from the browser to S3; URL-based entries fall back to the standard Frappe upload. Progress is tracked and displayed normally in the upload dialog.

### Private file streaming (Safari fix)

Safari's PDF viewer does not follow HTTP `302` redirects inside embedded contexts (`iframe`, `embed`, `object`). Platine can stream private file content directly through the Frappe server for configurable MIME types, bypassing the redirect entirely.

Configure under **Platine Settings → Advanced → Private File Streaming**. Only affects private files; public files continue to be served from the CDN URL. This setting only applies to private files.

### Share links

A **Share** button is added to every `File` form:

- **Public file** — returns the CDN `file_url` immediately.
- **Private file** — opens a dialog to choose an expiry (15 min / 1 h / 24 h / 7 days), then generates a presigned URL valid for that duration.

### Migration

A background job scans all `File` documents still pointing to local paths (`/files/` or `/private/files/`) and migrates them to S3 one by one. `platine_s3_key` is written for each migrated file. Progress is tracked in real time in the Settings form.

### CORS management

The CORS configuration of your bucket can be viewed and updated directly from the Settings form, with a sane default pre-filled on install.

---

## Architecture

```
platine/
├── hooks.py                          — doc_events, overrides, custom_fields, app_include_js
├── install.py                        — seeds default CORS config on first install
├── migration.py                      — migrate_files() background job
├── rollback.py                       — rollback_files() background job
├── reprefix.py                       — reprefix_files() background job (on folder_prefix change)
├── requirements.txt                  — boto3
├── translations/
│   └── fr.csv                        — French translations
├── utils/
│   └── s3.py                         — get_s3_client, upload_file, delete_file, copy_object,
│                                       set_object_acl, generate_presigned_get/put,
│                                       build_s3_key, file_exists_on_s3, get_s3_key_from_file_url
├── overrides/
│   ├── file.py                       — after_insert (upload + set platine_s3_key),
│   │                                   on_trash (delete main + thumbnail),
│   │                                   download_file (302 redirect or stream)
│   ├── file_doc.py                   — PlatineFile: before_insert (skip save_file for presigned),
│   │                                   validate_file_on_disk (check S3),
│   │                                   handle_is_private_changed (move S3 object)
│   └── request.py                    — before_request: intercept /private/files/ → stream or 302
├── api/
│   ├── s3.py                         — test_connection
│   ├── cors.py                       — get_cors_config, set_cors_config
│   ├── upload.py                     — get_presigned_upload_url, confirm_upload
│   ├── share.py                      — generate_share_link
│   ├── relink.py                     — relink_files
│   ├── logs.py                       — clear_all_logs
│   └── migration.py                  — start_migration, get_migration_status
├── platine/doctype/
│   ├── platine_settings/             — Single DocType: credentials, transfer, CORS,
│   │                                   migration, advanced (streaming), logs tabs
│   └── platine_log/                  — Upload / Download / Delete / Migration event log
└── public/js/
    ├── file_share.js                 — Share button on File DocType
    └── upload_override.js            — PlatineFileUploader (extends frappe.ui.FileUploader),
                                        frappe.platine.upload_via_presigned helper
```

### Request flows

```
# Standard download (public or private)
Client → Frappe (permission check)
       → generate presigned GET URL
       → 302 redirect to S3 / CDN

# Private file — embedded preview (Safari streaming)
Client (Referer: Frappe) → Frappe → stream S3 bytes directly (no redirect)
  └── only for MIME types listed in Advanced → Private File Streaming

# Presigned upload
Browser → get_presigned_upload_url (Frappe signs) → PUT directly to S3
       → confirm_upload (set_object_acl + create File doc)
```

---

## DocTypes

| DocType | Type | Purpose |
|---|---|---|
| `Platine Settings` | Single | S3 credentials, transfer settings, CORS, migration, advanced streaming config, logs |
| `Platine Log` | Standard | Per-event audit log for uploads, downloads, deletes, migrations |

---

## Custom Fields

Platine adds one custom field to the built-in `File` doctype:

| Field | Type | Purpose |
|---|---|---|
| `platine_s3_key` | Data (hidden, read-only) | Exact S3 object key. Written by every upload path; read by `on_trash` for reliable deletion without URL parsing. |

---

## Configuration

### 1. Install the app

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch main
bench --site your.site install-app platine
bench --site your.site migrate
```

### 2. Configure credentials

Open **Platine Settings** in the Frappe desk and fill in:

| Field | Description |
|---|---|
| Enable S3 Integration | Master on/off switch |
| Access Key | S3 access key ID |
| Secret Key | S3 secret access key |
| Region | Bucket region (e.g. `fr-par`) |
| Endpoint URL | S3 API endpoint (e.g. `https://s3.fr-par.scw.cloud`) |
| CDN URL | Public CDN hostname for public file URLs (e.g. `https://cdn.example.com`) |
| Bucket Name | Target bucket |
| Enable Presigned Upload | Route browser uploads directly to S3 |
| Presigned URL Expiry | Default expiry for presigned URLs (minutes, default 60) |

Click **Test Connection** to verify credentials before enabling.

### 3. Apply CORS

Go to the **CORS** tab. Click **Load Default** to pre-fill a permissive configuration, adjust origins if needed, then click **Apply** to push the configuration to the bucket.

> **Cloudflare users:** create a Cache Rule to bypass the cache for requests whose query string contains `X-Amz-Signature`. Without this, Cloudflare may serve a stale cached response with an expired signature to a different client.

### 4. Configure streaming (optional — Safari fix)

Go to **Advanced → Private File Streaming**. Add MIME types (one per line) that should be streamed directly instead of redirected:

```
application/pdf
```

This fixes Safari's embedded PDF viewer (`iframe`, `embed`) which does not follow `302` redirects. **Only affects private files.**

Browse [common MIME types on MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/MIME_types/Common_types) for reference.

### 5. Migrate existing files (optional)

If installing on an existing site with local files, click **Storage → Migrate to S3** in the Settings form. The job runs in the background — progress updates every 10 files directly in the form.

---

## Requirements

- [Frappe Bench](https://github.com/frappe/bench) installed and configured
- Frappe Framework **v16**
- Python **≥ 3.14**
- Redis (required by Frappe for the job queue)
- An S3-compatible object store (bucket-level ACL support optional — ACL is applied via `put_object_acl` after upload, not during)

---

## Development

This project uses `pre-commit` to enforce code quality:

```bash
cd apps/platine
pre-commit install
```

| Tool | Role |
|---|---|
| `ruff` | Python linting and formatting |
| `eslint` | JavaScript linting |
| `prettier` | JavaScript / CSS formatting |
| `pyupgrade` | Python syntax modernization |

Run the test suite against a local bench site:

```bash
bench --site your.site run-tests --app platine
```

---

## CI / CD

| Workflow | Trigger |
|---|---|
| **CI** | Push to `develop` — installs app and runs unit tests |
| **Linters** | Pull request — runs Frappe Semgrep Rules and `pip-audit` |

---

## License

Distributed under the **AGPL-3.0** License. See [`license.txt`](license.txt) for details.

---

<div align="center">
  <sub>Maintained by <a href="mailto:contact@underscore-blank.io">Underscore Blank OÜ</a></sub>
</div>
