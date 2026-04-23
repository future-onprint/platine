import os
from urllib.parse import unquote
import frappe


def intercept_private_file_request():
    """
    before_request hook: intercept /private/files/{filename} requests.
    If Platine is enabled and the file does not exist locally (i.e. it's on S3),
    generate a presigned GET URL and redirect the client directly to S3.
    Unauthenticated (Guest) requests are rejected early for private files.
    """
    request_path = frappe.local.request.path

    if not request_path.startswith("/private/files/"):
        return

    try:
        enabled = frappe.db.get_single_value("Platine Settings", "enabled")
        if not enabled:
            return
    except Exception:
        return

    # Require authenticated user for private files
    if frappe.session.user == "Guest":
        return

    # URL-decode so spaces/special chars match the actual S3 key
    filename = unquote(request_path[len("/private/files/"):])
    # Reject path traversal attempts
    if not filename or "/" in filename or ".." in filename:
        return

    # Only intercept if the file is NOT present on disk
    local_path = os.path.join(frappe.get_site_path(), "private", "files", filename)
    if os.path.exists(local_path):
        return

    from platine.utils.s3 import generate_presigned_get

    file_url = f"/private/files/{filename}"
    s3_key = frappe.db.get_value("File", {"file_url": file_url}, "platine_s3_key")
    if not s3_key:
        return

    presigned_url = generate_presigned_get(s3_key)

    from werkzeug.exceptions import HTTPException

    # Stream the S3 content directly when the file's MIME type is listed in
    # stream_mime_types (Advanced settings). This fixes Safari's PDF viewer
    # which does not follow 302 redirects in embedded contexts. Only private
    # files are affected.
    import mimetypes

    content_type, _ = mimetypes.guess_type(filename)
    should_stream = False
    if content_type:
        raw = frappe.db.get_single_value("Platine Settings", "stream_mime_types") or ""
        configured = {line.strip().lower() for line in raw.splitlines() if line.strip()}
        should_stream = content_type.lower() in configured

    if not should_stream:
        from werkzeug.utils import redirect
        response = redirect(presigned_url, 302)
        response.headers["Cache-Control"] = "no-store"
        raise HTTPException(response=response)

    import requests as http_requests
    from werkzeug.wrappers import Response as WerkzeugResponse

    upstream_headers = {}
    range_header = frappe.local.request.headers.get("Range")
    if range_header:
        upstream_headers["Range"] = range_header

    s3_resp = http_requests.get(presigned_url, headers=upstream_headers, stream=True)

    forward_headers = {}
    for h in [
        "Content-Type", "Content-Length", "Content-Disposition",
        "Accept-Ranges", "Content-Range", "ETag", "Last-Modified",
    ]:
        if h in s3_resp.headers:
            forward_headers[h] = s3_resp.headers[h]
    forward_headers["Cache-Control"] = "no-store"

    response = WerkzeugResponse(
        s3_resp.iter_content(chunk_size=65536),
        status=s3_resp.status_code,
        headers=forward_headers,
        direct_passthrough=True,
    )
    raise HTTPException(response=response)
