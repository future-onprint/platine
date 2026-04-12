import frappe
from platine.utils.s3 import get_s3_client
from platine.utils.logger import log_event, Timer


@frappe.whitelist()
def test_connection():
    frappe.only_for("System Manager")
    """Test S3 connectivity. Returns dict {success, message}."""
    try:
        client = get_s3_client()
        s = frappe.get_single("Platine Settings")
        client.head_bucket(Bucket=s.bucket_name)
        log_event(event_type="Connection", status="Success", message=f"Bucket '{s.bucket_name}' accessible")
        return {"success": True, "message": f"Connection OK — bucket '{s.bucket_name}' is accessible"}
    except Exception as e:
        log_event(event_type="Connection", status="Error", message=str(e))
        return {"success": False, "message": str(e)}
