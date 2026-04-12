import time
import frappe


def log_event(
    event_type: str,
    status: str,
    message: str = "",
    file_name: str = "",
    s3_key: str = "",
    is_private: bool = False,
    duration_ms: int = None,
) -> None:
    """
    Insert a Platine Log entry.
    Silently swallows exceptions so logging never breaks the main operation.
    """
    try:
        frappe.get_doc({
            "doctype": "Platine Log",
            "event_type": event_type,
            "status": status,
            "message": message or "",
            "file_name": file_name or "",
            "s3_key": s3_key or "",
            "is_private": 1 if is_private else 0,
            "user": frappe.session.user if frappe.session else "system",
            "duration_ms": duration_ms,
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        pass  # Never let logging crash the caller


class Timer:
    """Context manager to measure elapsed milliseconds."""

    def __init__(self):
        self._start = None
        self.elapsed_ms = None

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, *_):
        self.elapsed_ms = int((time.monotonic() - self._start) * 1000)
