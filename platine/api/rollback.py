import frappe


@frappe.whitelist()
def start_rollback():
    """Launch S3 → local rollback as a background job."""
    frappe.only_for("System Manager")
    frappe.enqueue(
        "platine.rollback.rollback_files",
        queue="long",
        timeout=3600,
        job_name="platine_s3_rollback",
        deduplicate=True,
    )
    return {"success": True, "message": "Rollback started in the background"}


@frappe.whitelist()
def get_rollback_status():
    """Return the current rollback status."""
    status = frappe.db.get_single_value("Platine Settings", "rollback_status")
    return {"status": status or "Not started"}
