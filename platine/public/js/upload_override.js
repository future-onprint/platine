// Platine — override Frappe upload to use presigned PUT to S3
//
// This script exposes frappe.platine.upload_via_presigned for programmatic use.
// Deep integration with frappe.ui.FileUploader varies by Frappe version and is
// left to the integrator. This utility handles: presigned URL generation,
// direct S3 PUT upload, and File doc confirmation in Frappe.

(function() {
    frappe.platine = frappe.platine || {};

    frappe.platine.check_presigned_enabled = function(callback) {
        frappe.db.get_single_value("Platine Settings", "presigned_upload_enabled")
            .then(val => callback(!!val));
    };

    frappe.platine.upload_via_presigned = function(file, options) {
        const filename = file.name;
        const is_private = options.is_private ? 1 : 0;
        const content_type = file.type || "application/octet-stream";

        return frappe.call({
            method: "platine.api.upload.get_presigned_upload_url",
            args: { filename, is_private, content_type },
        }).then(r => {
            const { upload_url, s3_key } = r.message;

            // Direct upload to S3 via PUT
            return fetch(upload_url, {
                method: "PUT",
                body: file,
                headers: { "Content-Type": content_type },
            }).then(resp => {
                if (!resp.ok) throw new Error(`S3 upload failed: ${resp.status}`);

                // Confirm upload with Frappe
                return frappe.call({
                    method: "platine.api.upload.confirm_upload",
                    args: {
                        s3_key,
                        filename,
                        is_private,
                        doctype: options.doctype,
                        docname: options.docname,
                        folder: options.folder || "Home/Attachments",
                    },
                });
            });
        });
    };
})();
