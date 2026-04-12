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
| **Upload (presigned)** | Browser generates a presigned `PUT` URL → uploads directly to S3, bypassing the Frappe server entirely |
| **Download** | Frappe checks permissions → generates a short-lived presigned `GET` URL → `302` redirect → client downloads directly from S3 / CDN |
| **Delete** | `on_trash` hook removes the corresponding object from S3 |
| **Thumbnails** | Generated locally before the original is uploaded, then both are pushed to S3 together |

### Access control

- **Public files** — uploaded with `public-read` ACL; `file_url` is set to the CDN URL directly.
- **Private files** — uploaded with `private` ACL; served exclusively via time-limited presigned URLs. Even if the bucket is misconfigured as public by default, the explicit per-object ACL prevents unauthorised access.

### Presigned upload (optional)

When enabled, the desk intercepts file uploads and routes them directly from the browser to S3 using a short-lived presigned `PUT` URL. The Frappe server only signs the request and creates the `File` document after confirmation — no file content ever touches it.

### Share links

A **"Generate share link"** button is added to every `File` form:

- **Public file** — returns the direct CDN URL immediately.
- **Private file** — opens a dialog to choose an expiry (15 min / 1 h / 24 h / 7 days), then generates a presigned CDN URL valid for that duration.

### Migration

A background job scans all `File` documents still pointing to local paths (`/files/` or `/private/files/`) and migrates them to S3 one by one. Progress is tracked in real time in the Settings form. Errors are logged per file without interrupting the job.

### CORS management

The CORS configuration of your bucket can be viewed and updated directly from the Settings form, with a sane default pre-filled on install.

---

## Architecture

```
platine/
├── hooks.py                          — doc_events, overrides, app_include_js, after_install
├── install.py                        — seeds default CORS config on first install
├── migration.py                      — migrate_files() background job
├── requirements.txt                  — boto3
├── utils/
│   └── s3.py                         — get_s3_client, get_cdn_client, upload_file,
│                                       delete_file, generate_presigned_get/put,
│                                       file_exists_on_s3, get_s3_key_from_file_url
├── overrides/
│   └── file.py                       — after_insert, on_trash, download_file (302 redirect)
├── api/
│   ├── s3.py                         — test_connection
│   ├── cors.py                       — get_cors_config, set_cors_config
│   ├── upload.py                     — get_presigned_upload_url, confirm_upload
│   ├── share.py                      — generate_share_link
│   └── migration.py                  — start_migration, get_migration_status
├── platine/doctype/platine_settings/
│   ├── platine_settings.json         — Single DocType
│   ├── platine_settings.py           — validate, get_default_cors_config
│   └── platine_settings.js           — Test Connection, Apply CORS, Start Migration, polling
└── public/js/
    ├── file_share.js                 — share link button on File DocType
    └── upload_override.js            — frappe.platine.upload_via_presigned helper
```

### Request flow

```
# Standard download (public or private)
Client → nginx → Frappe (permission check)
       → generate presigned GET URL (CDN endpoint)
       → 302 redirect
       → Client ↔ Cloudflare / S3   (Frappe never streams file content)

# Presigned upload
Frappe signs PUT URL → Client uploads directly to S3
       → confirm_upload() creates the File document
```

---

## DocTypes

```
Platine Settings   — S3 credentials, CDN URL, upload/download settings, CORS editor, migration status
```

---

## Configuration

### 1. Install the app

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch main
bench --site your.site install-app platine
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
| CDN URL | Public CDN hostname used for presigned URLs (e.g. `https://cdn.example.com`) |
| Bucket Name | Target bucket |
| Enable Presigned Upload | Route browser uploads directly to S3 |
| Presigned URL Expiry | Default expiry for download presigned URLs (minutes, default 60) |

Click **Test Connection** to verify credentials and bucket access before enabling the integration.

### 3. Apply CORS

The **CORS Configuration** field is pre-filled with a permissive default on install. Adjust the origins to match your Frappe site URL, then click **Apply CORS** to push the configuration to the bucket.

> **Cloudflare users:** if your CDN URL is proxied through Cloudflare, create a Cache Rule to bypass the cache for requests whose query string contains `X-Amz-Signature`. Without this, Cloudflare may serve a cached response to a different client using an expired signature.

### 4. Migrate existing files (optional)

If installing on an existing site with local files, click **Start Migration** in the Settings form. The job runs in the background — progress updates every 10 files directly in the form.

---

## Requirements

- [Frappe Bench](https://github.com/frappe/bench) installed and configured
- Frappe Framework **v16**
- Python **≥ 3.14**
- Redis (required by Frappe for the job queue)
- An S3-compatible object store with bucket-level ACL support

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
