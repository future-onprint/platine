// Platine — intercept Frappe's FileUploader to use presigned PUT to S3.
//
// Uses Object.defineProperty on frappe.ui.FileUploader so the patch fires
// exactly when the file_uploader bundle assigns the class — regardless of
// bundle load order. Files with actual content are PUT directly from the
// browser to S3; URL-based entries fall back to the normal Frappe upload.

(function () {
	frappe.provide("frappe.ui");
	frappe.platine = frappe.platine || {};

	// ── Setting cache ────────────────────────────────────────────────────────
	let _presigned_promise = null;
	function _presigned_enabled() {
		if (!_presigned_promise) {
			_presigned_promise = frappe.db
				.get_single_value("Platine Settings", "presigned_upload_enabled")
				.then((val) => !!val)
				.catch(() => false);
		}
		return _presigned_promise;
	}

	// ── Public utility (kept for programmatic use) ───────────────────────────
	frappe.platine.upload_via_presigned = function (file, options) {
		const filename = file.name;
		const is_private = options.is_private ? 1 : 0;
		const content_type = file.type || "application/octet-stream";

		return frappe
			.call({
				method: "platine.api.upload.get_presigned_upload_url",
				args: { filename, is_private, content_type },
			})
			.then((r) => {
				const { upload_url, s3_key } = r.message;
				return fetch(upload_url, {
					method: "PUT",
					body: file,
					headers: { "Content-Type": content_type },
				}).then((resp) => {
					if (!resp.ok) throw new Error(`S3 upload failed: ${resp.status}`);
					return frappe.call({
						method: "platine.api.upload.confirm_upload",
						args: {
							s3_key,
							filename,
							is_private,
							doctype: options.doctype,
							docname: options.docname,
							folder: options.folder || "Home",
						},
					});
				});
			});
	};

	// ── Single-file presigned upload (XHR for progress tracking) ────────────
	function _upload_single(file, options) {
		return new Promise((resolve, reject) => {
			const filename = file.file_obj.name;
			const is_private = file.private ? 1 : 0;
			const content_type = file.file_obj.type || "application/octet-stream";

			file.uploading = true;

			frappe
				.call({
					method: "platine.api.upload.get_presigned_upload_url",
					args: { filename, is_private, content_type },
				})
				.then((r) => {
					const { upload_url, s3_key } = r.message;
					const xhr = new XMLHttpRequest();

					xhr.upload.addEventListener("progress", (e) => {
						if (e.lengthComputable) {
							file.progress = e.loaded;
							file.total = e.total;
						}
					});

					xhr.addEventListener("load", () => {
						file.uploading = false;
						if (xhr.status >= 200 && xhr.status < 300) {
							frappe
								.call({
									method: "platine.api.upload.confirm_upload",
									args: {
										s3_key,
										filename,
										is_private,
										file_size: file.file_obj.size,
										doctype: options.doctype,
										docname: options.docname,
										folder: options.folder || "Home",
									},
								})
								.then((cr) => {
									file.request_succeeded = true;
									file.doc = cr.message;
									options.on_success && options.on_success(cr.message, cr);
									resolve();
								})
								.catch((err) => {
									file.failed = true;
									file.error_message = __("Failed to register file.");
									reject(err);
								});
						} else {
							file.failed = true;
							file.error_message = __("S3 upload failed: {0}", [xhr.status]);
							reject(new Error(file.error_message));
						}
					});

					xhr.addEventListener("error", () => {
						file.uploading = false;
						file.failed = true;
						file.error_message = __("Upload error.");
						reject(new Error("XHR error"));
					});

					xhr.open("PUT", upload_url, true);
					xhr.setRequestHeader("Content-Type", content_type);
					xhr.send(file.file_obj);
				})
				.catch((err) => {
					file.uploading = false;
					file.failed = true;
					file.error_message = __("Failed to get upload URL.");
					reject(err);
				});
		});
	}

	// ── FileUploader class patch ─────────────────────────────────────────────
	// Build the patched subclass once we have the original.
	function _build_patched_class(Original) {
		class PlatineFileUploader extends Original {
			constructor(options = {}) {
				super(options);
				this._p = options;
			}

			upload_files() {
				_presigned_enabled().then((enabled) => {
					if (!enabled) {
						super.upload_files();
						return;
					}
					this._upload_files_presigned();
				});
			}

			_upload_files_presigned() {
				const files = this.uploader.files;
				const options = this._p;

				const queue = files
					.filter((f) => !f.request_succeeded)
					.map((file) => {
						// Web link / URL — fall back to Frappe's own XHR for this entry
						if (!file.file_obj) {
							return Promise.resolve(this.uploader.upload_file(file, 0));
						}
						return _upload_single(file, options);
					});

				Promise.all(queue)
					.then(() => {
						if (files.every((f) => f.request_succeeded)) {
							this.dialog && this.dialog.hide();
						}
					})
					.catch(() => {
						// Individual errors shown inline — nothing to do here
					});
			}
		}

		return PlatineFileUploader;
	}

	// Intercept the moment the file_uploader bundle assigns frappe.ui.FileUploader.
	// This fires regardless of when the bundle is lazy-loaded.
	let _original = undefined;
	let _patched = undefined;

	// If FileUploader already loaded before this script, capture it now.
	const _existing = frappe.ui.FileUploader;
	if (typeof _existing === "function") {
		_original = _existing;
		_patched = _build_patched_class(_existing);
	}

	Object.defineProperty(frappe.ui, "FileUploader", {
		configurable: true,
		enumerable: true,
		get() {
			return _patched;
		},
		set(val) {
			_original = val;
			_patched = _build_patched_class(val);
		},
	});
})();
