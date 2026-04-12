import frappe


def daily_log_cleanup():
    """Purge Platine Log entries older than log_retention_days (default 30)."""
    try:
        retention_days = (
            frappe.db.get_single_value("Platine Settings", "log_retention_days") or 30
        )
        cutoff = frappe.utils.add_days(frappe.utils.nowdate(), -int(retention_days))
        frappe.db.delete("Platine Log", {"creation": ["<", cutoff]})
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Platine log cleanup failed: {e}", "Platine Log Cleanup")
