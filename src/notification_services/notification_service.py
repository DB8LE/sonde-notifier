from abc import ABC, abstractmethod
from typing import Any, Dict


class NotificationService(ABC):
    @abstractmethod
    def __init__(self, config: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def notify(self, notification_type: str, serial: str, sonde_type: str, distance: float) -> None:
        """Send a notification using this notification service"""
        pass
