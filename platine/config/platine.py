from frappe import _


def get_data():
    return [
        {
            "label": _("Settings"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Platine Settings",
                    "label": _("Platine Settings"),
                    "onboard": 1,
                },
                {
                    "type": "doctype",
                    "name": "Platine Log",
                    "label": _("Platine Log"),
                },
            ],
        }
    ]
