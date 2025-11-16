import logging
import smtplib
import ssl
from typing import Any, Dict

from ..notifier import RangeRing
from ..autorx import SondeFrame
from ..prediction import LandingPrediction

from .notification_service import NotificationService


class EmailNotifier(NotificationService):
    def __init__(self, config: Dict[str, Any]) -> None:
        self.smtp_host = config["smtp_host"]
        self.smtp_port = config["smtp_port"]
        self.smtp_auth = config["smtp_auth"]
        self.smtp_login = config["smtp_login"]
        self.smtp_password = config["smtp_password"]
        self.sender = config["sender"]
        self.destinations = config["destinations"]

        # Verify that auth is one of the valid choices
        if (self.smtp_auth != "none") and (self.smtp_auth != "ssl") and (self.smtp_auth != "tls"):
            logging.error(f"Invalid SMTP authentication option '{self.smtp_auth}'")
            exit(1)

    def _send_notification(self, title: str, content: str) -> None:
        # Connect to server unencrypted to with SSL
        ssl_context = None
        if self.smtp_auth == "ssl":
            ssl_context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=ssl_context)
        else:
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
        
        # Log in and send emails
        try:
            server.login(self.smtp_login, self.smtp_password)
            
            for destination in self.destinations:
                logging.debug(f"Sending mail to {destination}")
                server.sendmail(self.sender, destination, "Subject: "+title+"\n\n"+content) 
        except Exception as e:
            logging.error("Encountered exception while connected to SMTP server: "+str(e))

    def notify_rangering(
            self,
            latest_frame: SondeFrame,
            triggered_ring: RangeRing,
            distance: float # meters
        ) -> None:
        title = f"{latest_frame.model} sonde triggered range ring {triggered_ring.name}"
        content = f"Serial: {latest_frame.serial}\nDistance: {distance}km\nhttps://sondehub.org/{latest_frame.serial}"

        self._send_notification(title, content)

    def notify_rangering_prediction(
            self,
            latest_frame: SondeFrame,
            landing_prediction: LandingPrediction,
            triggered_ring: RangeRing,
            prediction_distance: float # meters
        ) -> None:
        title = f"{latest_frame.model} sonde prediction triggered range ring {triggered_ring.name}"
        content = f"Serial: {latest_frame.serial}\nDistance: {prediction_distance}km\nhttps://sondehub.org/{latest_frame.serial}"

        self._send_notification(title, content)

