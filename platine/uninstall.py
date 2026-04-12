import click
import frappe


def before_uninstall():
    """
    Warn the user if files are still stored on S3 before uninstalling Platine.
    Requires explicit terminal confirmation to proceed.
    """
    try:
        settings = frappe.get_single("Platine Settings")
        cdn_base = (settings.cdn_url or "").rstrip("/")
    except Exception:
        return  # Settings don't exist yet, safe to uninstall

    s3_count = 0

    if cdn_base:
        s3_count += frappe.db.count(
            "File",
            filters=[["file_url", "like", f"{cdn_base}/%"]],
        )

    # Also count private files whose local copy is absent (likely on S3)
    import os

    site_path = frappe.get_site_path()
    private_files = frappe.get_all(
        "File",
        filters=[["file_url", "like", "/private/files/%"]],
        fields=["file_name", "file_url"],
    )
    for f in private_files:
        filename = f["file_name"] or os.path.basename(f["file_url"])
        local_path = os.path.join(site_path, "private", "files", filename)
        if not os.path.exists(local_path):
            s3_count += 1

    if s3_count == 0:
        return  # No S3 files, safe to proceed

    click.echo("")
    click.echo(click.style("  ⚠️  WARNING — Platine S3 files detected", fg="yellow", bold=True))
    click.echo("")
    click.echo(f"  {s3_count} file(s) are currently stored on S3.")
    click.echo("  Uninstalling Platine without a rollback will permanently break")
    click.echo("  all links to these files in your Frappe database.")
    click.echo("")
    click.echo("  Recommended: run a Rollback from Platine Settings first")
    click.echo("  (Migration tab → Start Rollback) to restore files locally.")
    click.echo("")

    if not click.confirm(
        click.style("  Uninstall anyway and accept broken file links?", fg="red"),
        default=False,
    ):
        click.echo("")
        click.echo("  Uninstall cancelled. Run a Rollback first to preserve your files.")
        click.echo("")
        raise click.Abort()
