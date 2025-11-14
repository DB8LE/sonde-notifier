from typing import Any, Dict
from urllib.parse import urljoin

import requests

from .notification_service import NotificationService


class GotifyNotifier(NotificationService):
    def __init__(self, config: Dict[str, Any]) -> None:
        self.url = urljoin(config["url"], f"/message?{config['app_token']}")

    def notify(self, notification_type: str, serial: str, sonde_type: str, distance: float) -> None:
        title = "Sonde Notifier"
        if notification_type.startswith("range_ring_"):
            text = f"An {sonde_type} sonde has triggered range ring {nnotification_type.split("_")[-1]}. (Serial: {serial})"
        elif notification_type.startswith("prediction_range_ring_"):
            text = f"A landing prediction for an {sonde_type} sonde has triggered range ring {notification_type.split("_")[-1]}. (Serial: {serial})"
        else:  # Not reachable ATM
            text = "ERROR"

        requests.post(
            self.url,
            files={
                "title": title,
                "message": text
            }
        )    
