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


def get_cdn_client():
    """Client for presigned GET URLs — CDN endpoint (Cloudflare in front of S3)."""
    s = get_settings()
    return boto3.client(
        "s3",
        aws_access_key_id=s.access_key,
        aws_secret_access_key=s.get_password("secret_key"),
        region_name=s.region,
        endpoint_url=s.cdn_url,
    )


def upload_file(local_path: str, s3_key: str, is_private: bool = True) -> str:
    """
    Upload a local file to S3.
    Returns the CDN URL if public, the s3_key if private.
    """
    client = get_s3_client()
    s = get_settings()

    extra_args = {"ACL": "private" if is_private else "public-read"}

    client.upload_file(
        Filename=local_path,
        Bucket=s.bucket_name,
        Key=s3_key,
        ExtraArgs=extra_args,
    )

    if is_private:
        return s3_key

    cdn_base = (s.cdn_url or s.endpoint_url).rstrip("/")
    return f"{cdn_base}/{s.bucket_name}/{s3_key}"


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


def generate_presigned_get(s3_key: str, expiry_seconds: int = None) -> str:
    """
    Generate a presigned GET URL via the CDN client.
    expiry_seconds defaults to Platine Settings.presigned_url_expiry * 60.
    """
    client = get_cdn_client()
    s = get_settings()

    if expiry_seconds is None:
        expiry_seconds = (s.presigned_url_expiry or 60) * 60

    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": s.bucket_name, "Key": s3_key},
        ExpiresIn=expiry_seconds,
    )


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
            "ACL": "private" if is_private else "public-read",
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


def get_s3_key_from_file_url(file_url: str) -> str:
    """
    Extract the s3_key from a Frappe file_url.
    /private/files/doc.pdf  -> private/doc.pdf
    /files/image.jpg        -> public/image.jpg
    """
    if file_url.startswith("/private/files/"):
        filename = file_url[len("/private/files/"):]
        return f"private/{filename}"

    if file_url.startswith("/files/"):
        filename = file_url[len("/files/"):]
        return f"public/{filename}"

    frappe.throw(f"Unrecognized Frappe file URL format: {file_url}")
