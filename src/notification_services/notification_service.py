from abc import ABC, abstractmethod
from typing import Any, Dict

from ..notifier import RangeRing, SondeFrame
from ..prediction import LandingPrediction

class NotificationService(ABC):
    @abstractmethod
    def __init__(self, config: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def _send_notification(self, *args, **kwargs) -> None:
        """Internal function to send a notification using this service"""
        pass

    @abstractmethod
    def notify_rangering(
            self,
            latest_frame: SondeFrame,
            triggered_ring: RangeRing,
            distance: float # meters
        ) -> None:
        """Send a range ring notification using this notification service"""
        pass

    @abstractmethod
    def notify_rangering_prediction(
            self,
            latest_frame: SondeFrame,
            landing_prediction: LandingPrediction,
            triggered_ring: RangeRing,
            prediction_distance: float # meters
        ) -> None:
        """Send a prediction range ring notification using this notification service"""
        pass
