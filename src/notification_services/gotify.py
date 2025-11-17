from typing import Any, Dict
from urllib.parse import urljoin

import requests

from ..notifier import RangeRing
from ..autorx import SondeFrame
from ..prediction import LandingPrediction

from .notification_service import NotificationService


class GotifyNotifier(NotificationService):
    def __init__(self, config: Dict[str, Any]) -> None:
        self.url = urljoin(config["url"], f"/message?{config['app_token']}")

    def _send_notification(self, title: str, message: str) -> None:
        requests.post(
            self.url,
            files={
                "title": title,
                "message": message
            }
        )

    def notify_rangering(
            self,
            latest_frame: SondeFrame,
            triggered_ring: RangeRing,
            distance: float # meters
        ) -> None:
        notification_text = f"An {latest_frame.model} sonde has triggered range ring {triggered_ring.name}. (Serial: {latest_frame.serial})"

        self._send_notification("Sonde Notification", notification_text)

    def notify_rangering_prediction(
            self,
            latest_frame: SondeFrame,
            landing_prediction: LandingPrediction,
            triggered_ring: RangeRing,
            prediction_distance: float, # meters
            latest_distance: float # meters
        ) -> None:
        notification_text = f"A landing prediction for an {latest_frame.model} sonde has triggered range ring {triggered_ring.name}. (Serial: {latest_frame.serial})"
        
        self._send_notification("Sonde Prediction Notification", notification_text)
