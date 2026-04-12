// Copyright (c) 2026, Underscore Blank OÜ and contributors
// For license information, please see license.txt

// Cloudflare note: if Cloudflare is enabled in proxy mode, create a Cache Rule to
// bypass the cache for requests whose query string contains X-Amz-Signature.
// (Cache Rules → Bypass cache if X-Amz-Signature is present in the query string).

frappe.ui.form.on("Platine Settings", {
	onload(frm) {
		frm._enabled_on_load = frm.doc.enabled;

		if (!frm.doc.cors_config) {
			frappe.confirm(
				__("The CORS Configuration field is empty. Load the default configuration?"),
				() => {
					frappe.call({
						method: "platine.platine.doctype.platine_settings.platine_settings.get_default_cors_config",
						callback(r) {
							if (r.message) {
								frm.set_value("cors_config", r.message);
								frm.dirty();
							}
						},
					});
				}
			);
		}
	},

	enabled(frm) {
		if (!frm.doc.enabled && frm._enabled_on_load) {
			const d = new frappe.ui.Dialog({
				title: __("Disable S3 Integration"),
				indicator: "orange",
				fields: [
					{
						fieldtype: "HTML",
						options: `
							<div style="padding:4px 0 12px">
								<p>${__("All file URLs stored in the database point to S3 or your CDN. Disabling the integration <strong>will break every file link</strong> across your site.")}</p>
								<p>${__("It is strongly recommended to run a <strong>Rollback</strong> first (Migration tab) to download all files back to the Frappe server before disabling.")}</p>
							</div>
						`,
					},
				],
				primary_action_label: __("Run Rollback first"),
				primary_action() {
					d.hide();
					frm.set_value("enabled", 1);
					frappe.call({
						method: "platine.api.rollback.start_rollback",
						freeze: true,
						freeze_message: __("Starting rollback..."),
						callback(r) {
							if (r.message?.success) {
								frappe.show_alert({
									message: __("Rollback started. The integration will remain active until it completes."),
									indicator: "blue",
								});
								frm.reload_doc().then(() => {
									frm.set_active_tab && frm.set_active_tab("Migration");
									_start_rollback_polling(frm);
								});
							} else {
								frappe.msgprint({
									title: __("Rollback"),
									indicator: "red",
									message: r.message?.message || __("Could not start rollback."),
								});
							}
						},
					});
				},
				secondary_action_label: __("Disable anyway"),
				secondary_action() {
					d.hide();
					frm._enabled_on_load = 0;
				},
			});
			d.show();
			// Style "Disable anyway" as a destructive action
			d.get_secondary_btn().addClass("btn-danger").removeClass("btn-default");
		} else {
			frm._enabled_on_load = frm.doc.enabled;
		}
	},

	refresh(frm) {
		// ── Test Connection (standalone primary) ─────────────────────────
		frm.add_custom_button(
			__("Test Connection"),
			() => {
				frappe.call({
					method: "platine.api.s3.test_connection",
					freeze: true,
					freeze_message: __("Testing S3 connection..."),
					callback(r) {
						frappe.msgprint({
							title: __("Connection Test"),
							indicator: r.message?.success ? "green" : "red",
							message: r.message?.message || __("No response"),
						});
					},
				});
			},
			null,
			"primary"
		);

		// ── CORS dropdown ─────────────────────────────────────────────────
		frm.add_custom_button(
			__("Load Default"),
			() => {
				frappe.call({
					method: "platine.platine.doctype.platine_settings.platine_settings.get_default_cors_config",
					callback(r) {
						if (r.message) {
							frm.set_value("cors_config", r.message);
							frm.dirty();
						}
					},
				});
			},
			__("CORS")
		);

		frm.add_custom_button(
			__("Apply"),
			() => {
				frappe.call({
					method: "platine.api.cors.set_cors_config",
					args: { cors_config: frm.doc.cors_config },
					freeze: true,
					freeze_message: __("Applying CORS configuration..."),
					callback(r) {
						frappe.msgprint({
							title: __("Apply CORS"),
							indicator: r.message?.success ? "green" : "red",
							message: r.message?.message || __("No response"),
						});
					},
				});
			},
			__("CORS")
		);

		frm.add_custom_button(
			__("Sync from Bucket"),
			() => {
				frappe.call({
					method: "platine.api.cors.get_cors_config",
					freeze: true,
					freeze_message: __("Fetching CORS configuration from bucket..."),
					callback(r) {
						if (!r.message?.success) {
							frappe.msgprint({
								title: __("Sync CORS"),
								indicator: "red",
								message: r.message?.message || __("No response"),
							});
							return;
						}
						const config = JSON.stringify(
							{ CORSRules: r.message.config },
							null,
							2
						);
						frappe.call({
							method: "frappe.client.set_value",
							args: {
								doctype: "Platine Settings",
								name: "Platine Settings",
								fieldname: "cors_config",
								value: config,
							},
							callback() {
								frm.reload_doc();
							},
						});
					},
				});
			},
			__("CORS")
		);

		// ── Storage dropdown (Migration + Rollback) ───────────────────────
		frm.add_custom_button(
			__("Migrate to S3"),
			() => {
				frappe.confirm(
					__("Migrate all local files to S3?"),
					() => {
						frappe.call({
							method: "platine.api.migration.start_migration",
							freeze: true,
							freeze_message: __("Starting migration..."),
							callback(r) {
								if (r.message?.success) {
									frm.reload_doc().then(() => {
										_start_migration_polling(frm);
									});
								} else {
									frappe.msgprint(r.message?.message || __("Could not start migration."));
								}
							},
						});
					}
				);
			},
			__("Storage")
		);

		frm.add_custom_button(
			__("Rollback to Local"),
			() => {
				frappe.confirm(
					__("Download all S3 files back to local storage? This will restore local file URLs."),
					() => {
						frappe.call({
							method: "platine.api.rollback.start_rollback",
							freeze: true,
							freeze_message: __("Starting rollback..."),
							callback(r) {
								if (r.message?.success) {
									frm.reload_doc().then(() => {
										_start_rollback_polling(frm);
									});
								} else {
									frappe.msgprint(r.message?.message || __("Could not start rollback."));
								}
							},
						});
					}
				);
			},
			__("Storage")
		);

		// ── Logs buttons ──────────────────────────────────────────────────
		frm.add_custom_button(
			__("View Logs"),
			() => {
				frappe.set_route("List", "Platine Log", "List");
			},
			__("Logs")
		);

		frm.add_custom_button(
			__("Clear All Logs"),
			() => {
				frappe.confirm(
					__("Permanently delete all Platine Log entries?"),
					() => {
						frappe.call({
							method: "platine.api.logs.clear_all_logs",
							freeze: true,
							freeze_message: __("Deleting logs..."),
							callback(r) {
								frappe.show_alert({
									message: r.message?.message || __("Logs cleared."),
									indicator: "green",
								});
							},
						});
					}
				);
			},
			__("Logs")
		);

		// Auto-resume polling if a job was already running
		const migration_status = frm.doc.migration_status || "";
		if (
			migration_status &&
			!migration_status.startsWith("Completed") &&
			migration_status !== "Not started"
		) {
			_start_migration_polling(frm);
		}

		const rollback_status = frm.doc.rollback_status || "";
		if (
			rollback_status &&
			!rollback_status.startsWith("Rollback completed") &&
			rollback_status !== "Not started"
		) {
			_start_rollback_polling(frm);
		}
	},
});

function _start_migration_polling(frm) {
	if (frm._migration_poll_id) clearInterval(frm._migration_poll_id);

	frm._migration_poll_id = setInterval(() => {
		frappe.call({
			method: "platine.api.migration.get_migration_status",
			callback(r) {
				const status = r.message?.status || "";
				frm.set_value("migration_status", status);
				frm.refresh_field("migration_status");

				if (status.startsWith("Completed")) {
					clearInterval(frm._migration_poll_id);
					frm._migration_poll_id = null;
					frm.reload_doc();
					frappe.show_alert({ message: __("Migration complete."), indicator: "green" });
				}
			},
		});
	}, 3000);
}

function _start_rollback_polling(frm) {
	if (frm._rollback_poll_id) clearInterval(frm._rollback_poll_id);

	frm._rollback_poll_id = setInterval(() => {
		frappe.call({
			method: "platine.api.rollback.get_rollback_status",
			callback(r) {
				const status = r.message?.status || "";
				frm.set_value("rollback_status", status);
				frm.refresh_field("rollback_status");

				if (status.startsWith("Rollback completed")) {
					clearInterval(frm._rollback_poll_id);
					frm._rollback_poll_id = null;
					frm.reload_doc();
					frappe.show_alert({ message: __("Rollback complete."), indicator: "green" });
				}
			},
		});
	}, 3000);
}
