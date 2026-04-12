app_name = "platine"
app_title = "Platine"
app_publisher = "Underscore Blank OÜ"
app_description = "S3 Compatible bridge for working with files in Frappe."
app_email = "contact@underscore-blank.io"
app_license = "agpl-3.0"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "platine",
# 		"logo": "/assets/platine/logo.png",
# 		"title": "Platine",
# 		"route": "/platine",
# 		"has_permission": "platine.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/platine/css/platine.css"
app_include_js = "/assets/platine/js/upload_override.js"
# app_include_js = "/assets/platine/js/platine.js"

# include js, css files in header of web template
# web_include_css = "/assets/platine/css/platine.css"
# web_include_js = "/assets/platine/js/platine.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "platine/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
doctype_js = {
	"File": "public/js/file_share.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "platine/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "platine.utils.jinja_methods",
# 	"filters": "platine.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "platine.install.before_install"
after_install = "platine.install.after_install"

# Uninstallation
# ------------

before_uninstall = "platine.uninstall.before_uninstall"
# after_uninstall = "platine.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "platine.utils.before_app_install"
# after_app_install = "platine.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "platine.utils.before_app_uninstall"
# after_app_uninstall = "platine.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "platine.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

override_doctype_class = {
	"File": "platine.overrides.file_doc.PlatineFile"
}

fixtures = [
	{
		"doctype": "Custom Field",
		"filters": [["name", "=", "File-platine_s3_key"]],
	}
]

doc_events = {
	"File": {
		"after_insert": "platine.overrides.file.after_insert",
		"on_trash": "platine.overrides.file.on_trash",
	}
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"platine.tasks.daily_log_cleanup"
	],
}

# Testing
# -------

# before_tests = "platine.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "platine.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "platine.event.get_events"
# }

override_whitelisted_methods = {
	"frappe.core.doctype.file.file.download_file": "platine.overrides.file.download_file"
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "platine.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
before_request = ["platine.overrides.request.intercept_private_file_request"]
# after_request = ["platine.utils.after_request"]

# Job Events
# ----------
# before_job = ["platine.utils.before_job"]
# after_job = ["platine.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"platine.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

