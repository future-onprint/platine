import frappe


@frappe.whitelist()
def start_migration():
    """Launch file migration as a background job."""
    frappe.only_for("System Manager")
    frappe.enqueue(
        "platine.migration.migrate_files",
        queue="long",
        timeout=3600,
        job_id="platine_s3_migration",
        deduplicate=True,
    )
    return {"success": True, "message": "Migration started in the background"}


@frappe.whitelist()
def get_migration_status():
    """Return the current migration status."""
    status = frappe.db.get_single_value("Platine Settings", "migration_status")
    return {"status": status or "Not started"}
