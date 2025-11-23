import logging
from typing import Any, Dict, List, Optional

import requests

from ..autorx import SondeFrame
from ..notifier import RangeRing
from ..prediction import LandingPrediction
from .notification_service import NotificationService


class DiscordWebhookNotifier(NotificationService):
    def __init__(self, config: Dict[str, Any]) -> None:
        self.url = config["url"]
        self.mentions = config["mentions"]

    def _send_notification(
            self,
            message: str,
            embed_title: str,
            embed_fields: List[Dict[str, str]],
            embed_url: Optional[str] = None
        ) -> None:
        # Prepare message
        embed = {
            "content": message+"   "+self.mentions,
            "embeds": [
                {
                    "title": embed_title,
                    "fields": embed_fields,
                    "url": embed_url
                },
            ]
        }

        # Send message
        request = requests.post(
            self.url,
            json=embed
        )

        # Check status code
        if request.status_code not in [200, 204]:
            logging.error(f"Failed to send discord webhook notification. Got status code {request.status_code}")
            if request.content:
                logging.debug(f"Erroneous discord webhook request returned: {request.content}")

    def notify_rangering(
            self,
            latest_frame: SondeFrame,
            triggered_ring: RangeRing,
            distance: float # meters
        ) -> None:
        title = f"{latest_frame.model} sonde triggered range ring {triggered_ring.name}"
        fields = [
            {
                "name": "Info",
                "value": f"""
Serial:    {latest_frame.serial}
Type:      {latest_frame.model}
Frequency: {round(latest_frame.frequency, 2)} MHz
"""
            },
            {
                "name": "Position",
                "value": f"""
Distance:  {round(distance/1000, 1)}km (treshold: {round(triggered_ring.range, 1)}km)
Altitude:  {round(latest_frame.altitude, 0)}m (treshold: {round(triggered_ring.max_altitude, 1)}m)
Position:  {round(latest_frame.latitude, 5)} {round(latest_frame.longitude, 5)}
"""
            }
        ]
        sondehub_link = "https://sondehub.org/"+latest_frame.serial

        self._send_notification(title, "Track on Sondehub", fields, embed_url=sondehub_link)

    def notify_rangering_prediction(
            self,
            latest_frame: SondeFrame,
            landing_prediction: LandingPrediction,
            triggered_ring: RangeRing,
            prediction_distance: float, # meters
            latest_distance: float # meters
        ) -> None:
        title = f"{latest_frame.model} sonde landing prediction triggered range ring {triggered_ring.name}"        
        fields = [
            {
                "name": "Info",
                "value": f"""
Serial:    {latest_frame.serial}
Type:      {latest_frame.model}
Frequency: {round(latest_frame.frequency, 2)} MHz
"""
            },
            {
                "name": "Predicted Position",
                "value": f"""
Landing Time:      {landing_prediction.landing_time.strftime("%Y-%m-%d %H:%M:%SZ")}
Landing Distance:  {round(prediction_distance/1000, 1)}km (treshold: {round(triggered_ring.range, 1)}km)
Landing Altitude:  {round(landing_prediction.altitude, 0)}m (treshold: {round(triggered_ring.max_altitude, 1)}m)
Landing Position:  {round(landing_prediction.latitude, 5)} {round(landing_prediction.longitude, 5)}
"""
            },
            {
                "name": "Current Position",
                "value": f"""
Distance:  {round(latest_distance/1000, 1)}km (treshold: {round(triggered_ring.range, 1)}km)
Altitude:  {round(latest_frame.altitude, 0)}m (treshold: {round(triggered_ring.max_altitude, 1)}m)
Position:  {round(latest_frame.latitude, 5)} {round(latest_frame.longitude, 5)}
"""
            }
        ]

        sondehub_link = "https://sondehub.org/"+latest_frame.serial

        self._send_notification(title, "Track on Sondehub", fields, embed_url=sondehub_link)
