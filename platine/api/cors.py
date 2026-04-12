import frappe
import json

from platine.utils.s3 import get_s3_client
from platine.utils.logger import log_event, Timer


@frappe.whitelist()
def get_cors_config():
	"""Read the current CORS configuration of the S3 bucket."""
	try:
		client = get_s3_client()
		s = frappe.get_single("Platine Settings")
		response = client.get_bucket_cors(Bucket=s.bucket_name)
		return {"success": True, "config": response.get("CORSRules", [])}
	except client.exceptions.NoSuchCORSConfiguration:
		return {"success": True, "config": []}
	except Exception as e:
		log_event(event_type="CORS", status="Error", message=str(e))
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def set_cors_config(cors_config=None):
	"""
	Apply the CORS JSON configuration to the bucket.
	cors_config: JSON string with "CORSRules" key or a direct array.
	"""
	try:
		client = get_s3_client()
		s = frappe.get_single("Platine Settings")

		if not cors_config:
			cors_config = s.cors_config

		config = json.loads(cors_config) if isinstance(cors_config, str) else cors_config

		# Accept {"CORSRules": [...]} or a bare array
		if isinstance(config, list):
			cors_rules = config
		else:
			cors_rules = config.get("CORSRules", config)

		client.put_bucket_cors(
			Bucket=s.bucket_name,
			CORSConfiguration={"CORSRules": cors_rules},
		)
		log_event(event_type="CORS", status="Success", message="CORS configuration applied")
		return {"success": True, "message": "CORS configuration applied successfully"}
	except Exception as e:
		log_event(event_type="CORS", status="Error", message=str(e))
		return {"success": False, "message": str(e)}
