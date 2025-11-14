import base64
import logging
from typing import Any, Dict

import requests

from .notification_service import NotificationService


class NtfyNotifier(NotificationService):
    def __init__(self, config: Dict[str, Any]) -> None:
        self.topic_url = config["topic_url"]

        # If an auth login was specified, generate auth string
        user = config["auth_user"]
        password = config["auth_password"]
        token = config["auth_token"]

        self.auth_header = ""
        if token != "":
            self.auth_header = "Bearer "+token
        elif (user != "") or (password != ""):
            auth_str = user+":"+password
            self.auth_header = "Basic "+base64.b64encode(auth_str.encode("ascii")).decode("ascii")

    def notify(self, notification_type: str, serial: str, sonde_type: str, distance: float) -> None:
        if notification_type.startswith("range_ring_"):
            notification_string = f"An {sonde_type} sonde has triggered range ring {notification_type.split('_')[-1]}. (Serial: {serial})"
        elif notification_type.startswith("prediction_range_ring_"):
            notification_string = f"A landing prediction for an {sonde_type} sonde has triggered range ring {notification_type.split('_')[-1]}. (Serial: {serial})"
        else:
            notification_string = "ERROR" # Not reachable ATM

        request = requests.post(
            self.topic_url,
            data=notification_string.encode(),
            headers={"Authorization": self.auth_header}
        )

        if request.status_code != 200:
            logging.error(f"Failed to send NTFY notification. Got status code {request.status_code}")
            if request.content:
                logging.debug(f"Erroneous NTFY request returned: {request.content}")
