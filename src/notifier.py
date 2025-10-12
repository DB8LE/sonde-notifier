import logging
import time
import traceback
from collections import defaultdict
from threading import Lock
from typing import Any, Dict, List, Type

import geopy.distance

from . import autorx
from .notification_services import *

TRACKED_SONDES_MAX_SECONDS = 2*60*60

class Notifier:
    def __init__(self, config: Dict[str, Any]) -> None:
        logging.info("Initializing notifier")

        self.config = config
        self.notify_check_interval = config["notifier"]["check_interval"]
        self.station_position = (config["station"]["latitude"], config["station"]["longitude"])
        
        self.tracked_sondes = {}
        self.tracked_sondes_lock = Lock()

        self.notified_sondes = defaultdict(list)
        self.notified_sondes_lock = Lock()

        # Parse range rings
        self.range_rings = {}
        for key, value in config.items():
            if key.startswith("range_ring_"):
                self.range_rings[key] = (
                    value["radius"],
                    value["max_altitude"]
                )
        sorted_rings_items = sorted(self.range_rings.items(), key=lambda item: item[1][0])
        self.range_rings = {k: v for k, v in sorted_rings_items}

        # Prepare list of notification services from config
        logging.debug("Initializing notification services")
        self.notification_services: List[NotificationService] = []

        if config["ntfy"]["enabled"]:
            self.notification_services.append(NtfyNotifier(config["ntfy"]))

    def _handle_packet(self, packet: Dict[str, Any]):
        """Internal callback function to handle payload summaries from AutoRX"""

        logging.debug(f"Got packet #{packet['frame']} from sonde {packet['callsign']}")

        # Update internal list
        serial = packet["callsign"]
        with self.tracked_sondes_lock:
            self.tracked_sondes[serial] = [
                time.time(),
                packet["latitude"],
                packet["longitude"],
                packet["altitude"],
                packet["model"]
            ]
    
    def _purge_old_tracked(self):
        """Internal function to remove all old sondes from tracked_sondes dict"""

        logging.debug("Purging old sondes from tracked list")

        remove = []
        with self.tracked_sondes_lock:
            # Check which sondes are old
            for serial, values in self.tracked_sondes.items():
                if time.time()-values[0] >= TRACKED_SONDES_MAX_SECONDS:
                    remove.append(serial)

            # Remove old sondes
            for serial in remove:
                del self.tracked_sondes[serial]

                # Remove from notified_sondes list if present
                with self.notified_sondes_lock:
                    if serial in self.notified_sondes:
                        del self.notified_sondes[serial]

            # Log
            if len(remove) > 0:
                logging.debug("Removed old sondes from tracked list: "+str(remove))

    def _notify(self, notification_type: str, serial: str, sonde_type: str, distance: float):
        """Internal function to send notifications for a specific sonde"""

        logging.info(f"Sending notifications for {notification_type} of sonde {serial} ({sonde_type})")

        for service in self.notification_services:
            service.notify(notification_type, serial, sonde_type, distance)

    def _check_notifications(self):
        """Internal function to check if notifications need to be sent"""

        logging.debug("Checking notifications")

        with self.tracked_sondes_lock and self.notified_sondes_lock:
            for serial, values in self.tracked_sondes.items():
                # Calculate distance to sonde
                distance = geopy.distance.geodesic(
                    self.station_position,
                    (values[1], values[2])
                ).km
                altitude = values[3] / 1000

                # Check range rings
                for ring, filters in self.range_rings.items():
                    # Skip triggered rings
                    if ring in self.notified_sondes[serial]:
                        continue

                    # Check if ring should be triggered
                    if (distance <= filters[0]) and (altitude <= filters[1]):
                        self._notify(ring, serial, values[4], distance)

                        # Add this and larger rings to notified_sondes list
                        current_ring_id = int(ring[-1:])
                        for block_ring in self.range_rings.keys():
                            block_ring_id = int(block_ring[-1:])
                            if block_ring_id >= current_ring_id:
                                # TODO: so many indents...
                                self.notified_sondes[serial].append(block_ring)

                        break # Only notify for ring with smallest radius (range_rings list is sorted by asc. radius)

    def run(self):
        """Run notifier"""

        logging.info("Running notifier")
        try:
            # Start AutoRX listener
            self.autorx_listener = autorx.AutoRXListener(self.config["autorx"]["port"], self._handle_packet)
            self.autorx_listener.start()

            while True:
                self._purge_old_tracked()
                self._check_notifications()
                time.sleep(self.notify_check_interval*60)
        except KeyboardInterrupt:
            logging.info("Caught KeyboardInterrupt, shutting down")
        except Exception as e:
            logging.error(f"Got exception while running notifier: {e}")
            logging.info(traceback.format_exc())
        finally:
            # Close any open connections
            self.autorx_listener.close()
