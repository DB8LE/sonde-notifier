from typing import Any, Dict

import requests

from ..notifier import RangeRing, SondeFrame
from ..prediction import LandingPrediction

from .notification_service import NotificationService


class DiscordWebhookNotifier(NotificationService):
    def __init__(self, config: Dict[str, Any]) -> None:
        self.url = config["url"]
        self.mentions = config["mentions"]

    def _send_notification(self, text: str) -> None:
        text = text + "\n" + self.mentions

        requests.post(
            self.url,
            json={
                "content": text
            }
        )

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
