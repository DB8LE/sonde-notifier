import base64
import logging
from typing import Any, Dict

import requests

from ..notifier import RangeRing, SondeFrame
from ..prediction import LandingPrediction

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

    def _send_notification(self, text: str) -> None:
        # Send request
        request = requests.post(
            self.topic_url,
            data=text.encode(),
            headers={"Authorization": self.auth_header}
        )

        # Check status code
        if request.status_code != 200:
            logging.error(f"Failed to send NTFY notification. Got status code {request.status_code}")
            if request.content:
                logging.debug(f"Erroneous NTFY request returned: {request.content}")

    def notify_rangering(
            self,
            latest_frame: SondeFrame,
            triggered_ring: RangeRing,
            distance: float # meters
        ) -> None:
        notification_text = f"An {latest_frame.model} sonde has triggered range ring {triggered_ring.name}. (Serial: {latest_frame.serial})"

        self._send_notification(notification_text)

    def notify_rangering_prediction(
            self,
            latest_frame: SondeFrame,
            landing_prediction: LandingPrediction,
            triggered_ring: RangeRing,
            prediction_distance: float # meters
        ) -> None:
        notification_text = f"A landing prediction for an {latest_frame.model} sonde has triggered range ring {triggered_ring.name}. (Serial: {latest_frame.serial})"
        
        self._send_notification(notification_text)

