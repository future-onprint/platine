import frappe


@frappe.whitelist()
def clear_all_logs():
    """Delete all Platine Log entries."""
    frappe.only_for("System Manager")
    count = frappe.db.count("Platine Log")
    frappe.db.delete("Platine Log")
    frappe.db.commit()
    return {"success": True, "message": f"{count} log entries deleted"}
