import json
import logging
import socket
import traceback
from collections.abc import Callable
from datetime import datetime, timezone
from threading import Thread
from typing import Any, Dict, Optional, Self, Tuple

import geopy.distance


class SondeFrame:
    def __init__(
            self,
            serial: str,
            frame_num: int,
            latitude: float,
            longitude: float,
            altitude: int,
            model: str,
            frequency: float,
            rx_time: Optional[datetime] = None,
        ) -> None:
        self.serial = serial
        self.frame = frame_num
        self.latitude = latitude
        self.longitude = longitude
        self.altitude = altitude # meters
        self.model = model
        self.frequency = frequency # MHz
        self.time = rx_time

    def calculate_distance(self, observer: Tuple[float, float]) -> float:
        """
        Calculate distance from a certain observer point (lat, lon) to the sondeh.
        Returns distance in meters.
        """
    
        return geopy.distance.geodesic(
            observer,
            (self.latitude, self.longitude)
        ).m

    @classmethod
    def from_autorx(cls, payload_summary: Dict[str, Any]) -> Self:
        """Initialize a SondeFrame from an AutoRX UDP payload summary"""

        return cls(
            serial=payload_summary["callsign"],
            frame_num=payload_summary["frame"],
            latitude=payload_summary["latitude"],
            longitude=payload_summary["longitude"],
            altitude=payload_summary["altitude"],
            model=payload_summary["model"],
            frequency=float(payload_summary["freq"][:-4])
            # Can't set RX time from the payload summary due to leap seconds and missing date
        )

class AutoRXListener():
    def __init__(self, autorx_host: str, autorx_port: int, callback: Callable[[SondeFrame], None]):

        self.autorx_host = autorx_host
        self.autorx_port = autorx_port
        self.callback = callback

        self._run_listener = False
        self._listener_thread = None
        self._socket = None

    def _listen(self):
        """Listen for payload summaries from autorx"""

        # Configure socket
        self._socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self._socket.settimeout(1)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except:
            pass
        
        try:
            # Bind socket
            self._socket.bind((self.autorx_host, self.autorx_port))

            # Start listening for packets
            logging.info(f"Started AutoRX listener on {self.autorx_host}:{self.autorx_port}")
            self._run_listener = True
            while self._run_listener:
                # Try to receive a packet
                try:
                    packet = json.loads(self._socket.recvfrom(1024)[0])
                    if packet["type"] == "PAYLOAD_SUMMARY":
                        # Parse payload summary and set time
                        try:
                            sonde_frame = SondeFrame.from_autorx(packet)
                            sonde_frame.time = datetime.now(timezone.utc)
                        except Exception as e:
                            logging.error("Error while parsing AutoRX UDP payload summary: "+str(e))
                        else:
                            self.callback(sonde_frame)
                except socket.timeout:
                    pass
        except (KeyboardInterrupt, Exception) as e:
            logging.error("Caught exception while running AutoRX listener: "+str(e))
            logging.info(traceback.format_exc())
            self.close()

    def start(self):
        """Start the AutoRX listener thread"""

        if self._listener_thread is None:
            self._listener_thread = Thread(target=self._listen)
            self._listener_thread.start()

    def close(self):
        """Stop the AutoRX listener thread"""

        if self._listener_thread is not None:
            self._run_listener = False

            # This won't work if this thread is calling the function
            try:
                self._listener_thread.join(timeout=3)
            except RuntimeError:
                pass

            self._listener_thread = None