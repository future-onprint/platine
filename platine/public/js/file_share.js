frappe.ui.form.on("File", {
	refresh(frm) {
		frm.add_custom_button(
			__("Generate share link"),
			() => {
				if (!frm.doc.is_private) {
					frappe.call({
						method: "platine.api.share.generate_share_link",
						args: { file_name: frm.doc.name },
						callback(r) {
							if (r.message) {
								_show_share_dialog(r.message.url, null);
							}
						},
					});
				} else {
					_show_expiry_dialog(frm);
				}
			},
			__("Platine")
		);
	},
});

function _show_expiry_dialog(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Private share link"),
		fields: [
			{
				fieldtype: "Select",
				fieldname: "expiry",
				label: __("Expiry duration"),
				options: [
					{ value: "900", label: __("15 minutes") },
					{ value: "3600", label: __("1 hour") },
					{ value: "86400", label: __("24 hours") },
					{ value: "604800", label: __("7 days") },
				],
				default: "3600",
			},
		],
		primary_action_label: __("Generate"),
		primary_action(values) {
			d.hide();
			frappe.call({
				method: "platine.api.share.generate_share_link",
				args: {
					file_name: frm.doc.name,
					expiry_seconds: values.expiry,
				},
				callback(r) {
					if (r.message) {
						const expiry_label =
							d.fields_dict.expiry.df.options.find(
								(o) => o.value === values.expiry
							)?.label || "";
						_show_share_dialog(r.message.url, expiry_label);
					}
				},
			});
		},
	});
	d.show();
}

function _show_share_dialog(url, expiry_label) {
	const fields = [
		{
			fieldtype: "Data",
			fieldname: "share_url",
			label: __("Link"),
			default: url,
			read_only: 1,
		},
	];

	if (expiry_label) {
		fields.push({
			fieldtype: "HTML",
			fieldname: "expiry_info",
			options: `<p class="text-muted small">${__("Expires in")} ${expiry_label}</p>`,
		});
	}

	const d = new frappe.ui.Dialog({
		title: __("Share link"),
		fields: fields,
		primary_action_label: __("Copy"),
		primary_action() {
			frappe.utils.copy_to_clipboard(url);
			frappe.show_alert({
				message: __("Link copied!"),
				indicator: "green",
			});
			d.hide();
		},
	});
	d.show();
}
