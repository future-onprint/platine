import frappe
import boto3
from botocore.exceptions import ClientError


def get_settings():
    """Return the Platine Settings singleton document."""
    return frappe.get_single("Platine Settings")


def get_s3_client():
    """Client for write operations (upload, delete, CORS) — real S3 endpoint."""
    s = get_settings()
    return boto3.client(
        "s3",
        aws_access_key_id=s.access_key,
        aws_secret_access_key=s.get_password("secret_key"),
        region_name=s.region,
        endpoint_url=s.endpoint_url,
    )




def upload_file(local_path: str, s3_key: str, is_private: bool = True) -> str:
    """
    Upload a local file to S3.
    Returns the CDN URL if public, the s3_key if private.
    """
    import mimetypes

    client = get_s3_client()
    s = get_settings()

    content_type, _ = mimetypes.guess_type(local_path)
    extra_args = {
        "ACL": "private" if is_private else "public-read",
        "ContentType": content_type or "application/octet-stream",
    }

    client.upload_file(
        Filename=local_path,
        Bucket=s.bucket_name,
        Key=s3_key,
        ExtraArgs=extra_args,
    )

    if is_private:
        return s3_key

    cdn_base = (s.cdn_url or s.endpoint_url).rstrip("/")
    return f"{cdn_base}/{s3_key}"


def delete_file(s3_key: str) -> None:
    """Delete an S3 object. Does not raise if the object does not exist."""
    client = get_s3_client()
    s = get_settings()

    try:
        client.delete_object(Bucket=s.bucket_name, Key=s3_key)
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return
        raise


def copy_object(src_key: str, dst_key: str, is_private: bool) -> None:
    """Copy an S3 object within the same bucket, preserving ACL."""
    client = get_s3_client()
    s = get_settings()
    client.copy_object(
        CopySource={"Bucket": s.bucket_name, "Key": src_key},
        Bucket=s.bucket_name,
        Key=dst_key,
        ACL="private" if is_private else "public-read",
    )


def generate_presigned_get(
    s3_key: str,
    expiry_seconds: int = None,
    filename: str = None,
) -> str:
    """
    Generate a presigned GET URL pointing directly at the S3 endpoint.

    Presigned URLs for private files must NOT go through a Cloudflare CDN
    proxy: Cloudflare rewrites or preserves the Host header in ways that
    prevent SigV4 canonical-host validation from matching, regardless of
    whether you sign against the CDN domain or the S3 endpoint.

    Routing presigned URLs through a CDN also provides no benefit — the
    content is unique per request (expiring signature) and must not be cached.

    filename: when provided, adds ResponseContentDisposition=attachment so the
              browser downloads the file instead of opening it inline.

    expiry_seconds defaults to Platine Settings.presigned_url_expiry * 60.
    """
    client = get_s3_client()
    s = get_settings()

    if expiry_seconds is None:
        expiry_seconds = (s.presigned_url_expiry or 60) * 60

    import mimetypes

    params = {"Bucket": s.bucket_name, "Key": s3_key}

    # Override Content-Type from the key extension — S3 objects uploaded without
    # an explicit ContentType are stored as application/octet-stream, which prevents
    # browsers from rendering PDFs and images inline.
    content_type, _ = mimetypes.guess_type(s3_key)
    if content_type:
        params["ResponseContentType"] = content_type

    if filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

    return client.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expiry_seconds,
    )


def set_object_acl(s3_key: str, is_private: bool = True) -> None:
    """Set the ACL on an existing S3 object (called after presigned PUT)."""
    client = get_s3_client()
    s = get_settings()
    acl = "private" if is_private else "public-read"
    client.put_object_acl(Bucket=s.bucket_name, Key=s3_key, ACL=acl)


def generate_presigned_put(s3_key: str, content_type: str, is_private: bool = True) -> str:
    """
    Generate a presigned PUT URL via S3 client (direct browser -> S3 upload).
    """
    client = get_s3_client()
    s = get_settings()

    expiry_seconds = (s.presigned_url_expiry or 60) * 60

    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": s.bucket_name,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=expiry_seconds,
    )


def file_exists_on_s3(s3_key: str) -> bool:
    """Check whether an object exists on S3 (head_object)."""
    client = get_s3_client()
    s = get_settings()

    try:
        client.head_object(Bucket=s.bucket_name, Key=s3_key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise


def download_file(s3_key: str, local_path: str) -> None:
    """Download an S3 object to a local path."""
    client = get_s3_client()
    s = get_settings()
    client.download_file(Bucket=s.bucket_name, Key=s3_key, Filename=local_path)


def build_s3_key(filename: str, is_private: bool) -> str:
    """
    Build a unique S3 key for a new upload.

    A random 8-character hex suffix is injected before the extension to
    prevent collisions when two files share the same name.

    prefix='prod', private=True  → prod/private/photo-a3f9bc12.jpg
    prefix='',     private=False → public/photo-a3f9bc12.jpg
    """
    import secrets
    import os as _os

    s = get_settings()
    prefix = (s.folder_prefix or "").strip("/")

    stem, ext = _os.path.splitext(filename)
    unique_filename = f"{stem}-{secrets.token_hex(4)}{ext}"

    base = f"{'private' if is_private else 'public'}/{unique_filename}"
    return f"{prefix}/{base}" if prefix else base


def get_s3_key_from_file_url(file_url: str) -> str:
    """
    Derive the S3 key from a Frappe file_url (local path or CDN URL).
    /private/files/doc.pdf              -> {prefix}/private/doc.pdf
    /files/image.jpg                    -> {prefix}/public/image.jpg
    https://cdn.example.com/bucket/...  -> everything after bucket_name/
    """
    if file_url.startswith("/private/files/"):
        filename = file_url[len("/private/files/"):]
        return build_s3_key(filename, is_private=True)

    if file_url.startswith("/files/"):
        filename = file_url[len("/files/"):]
        return build_s3_key(filename, is_private=False)

    # CDN URL — the key is everything after {cdn_base}/
    s = get_settings()
    cdn_base = (s.cdn_url or s.endpoint_url or "").rstrip("/")
    if cdn_base and file_url.startswith(cdn_base):
        return file_url[len(cdn_base):].lstrip("/")

    # Unrecognised format (external URL, folder, etc.) — skip silently
    return None
