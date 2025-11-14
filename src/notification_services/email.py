import logging
import smtplib
import ssl
from typing import Any, Dict

import requests

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

    def notify(self, notification_type: str, serial: str, sonde_type: str, distance: float) -> None:
        # Prepare email title and content
        if notification_type.startswith("range_ring_"):
            title = f"{sonde_type} sonde triggered range ring {notification_type.split('_')[-1]}"
            content = f"Serial: {serial}\nDistance: {distance}km\nhttps://sondehub.org/{serial}"
        elif notification_type.startswith("prediction_range_ring_"):
            title = f"{sonde_type} sonde prediction triggered range ring {notification_type.split('_')[-1]}"
            content = f"Serial: {serial}\nDistance: {distance}km\nhttps://sondehub.org/{serial}"
        else:
            title = "ERROR" # Not reachable ATM
            content = ""

        # Connect to server
        ssl_context = None
        if self.smtp_auth == "ssl":
            ssl_context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=ssl_context)
        else:
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
        
        try:
            server.login(self.smtp_login, self.smtp_password)
            
            for destination in self.destinations:
                logging.debug(f"Sending mail to {destination}")
                server.sendmail(self.sender, destination, "Subject: "+title+"\n\n"+content) 
        except Exception as e:
            logging.error("Encountered exception while connected to SMTP server: "+str(e))
