from typing import Any, Dict

import requests

from .notification_service import NotificationService


class DiscordWebhookNotifier(NotificationService):
    def __init__(self, config: Dict[str, Any]) -> None:
        self.url = config["url"]
        self.mentions = config["mentions"]

    def notify(self, notification_type: str, serial: str, sonde_type: str, distance: float) -> None:
        if notification_type.startswith("range_ring_"):
            text = f"An {sonde_type} sonde has triggered range ring {notification_type.split("_")[-1]}. (Serial: {serial})"
        elif notification_type.startswith("prediction_range_ring_"):
            text = f"A landing prediction for an {sonde_type} sonde has triggered range ring {notification_type.split("_")[-1]}. (Serial: {serial})"
        else:  # Not reachable ATM
            text = "ERROR"

        text = text + "\n" + self.mentions

        requests.post(
            self.url,
            json={
                "content": text
            }
        )    
