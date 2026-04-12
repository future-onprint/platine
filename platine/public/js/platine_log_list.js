frappe.listview_settings["Platine Log"] = {
	onload(listview) {
		listview.page.add_action_item(__("Clear All Logs"), () => {
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
							listview.refresh();
						},
					});
				}
			);
		});
	},
};
