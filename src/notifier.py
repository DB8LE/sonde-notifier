import json
import logging
import requests
import time
import traceback
from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List

import geopy.distance

from . import autorx
from .notification_services import *

TRACKED_SONDES_MAX_SECONDS = 5*60*60

class Notifier:
    def __init__(self, config: Dict[str, Any]) -> None:
        logging.info("Initializing notifier")

        self.config = config
        self.notify_check_interval = config["notifier"]["check_interval"] * 60 # Convert to seconds
        self.only_predict_descending = config["prediction"]["only_predict_descending"]
        self.station_position = (config["station"]["latitude"], config["station"]["longitude"])

        self.prediction_enabled = config["prediction"]["enabled"]
        self.tawhiri_api_url = config["prediction"]["api_url"]

        self.sondes_altitudes = defaultdict(lambda: deque(maxlen=5))
        self.sondes_altitudes_lock = Lock()

        self.tracked_sondes = {}
        self.tracked_sondes_lock = Lock()

        self.notified_sondes = defaultdict(list)
        self.notified_sondes_lock = Lock()

        # Parse range rings
        self.range_rings = []
        try:
            for id, range_ring in enumerate(config["notifier"]["range_rings"]):
                self.range_rings.append(
                    {
                        "id": id,
                        "name": range_ring["name"],
                        "range": range_ring["radius"]*1000,
                        "max_altitude": range_ring["max_altitude"]*1000
                    }
                )
        except KeyError as e:
            logging.error("Invalid key in range rings: "+str(e))
            exit(1)

        if len(self.range_rings) == 0:
            logging.error("Define at least one range ring!")
            exit(1)

        # Prepare list of notification services from config
        logging.debug("Initializing notification services")
        self.notification_services: List[NotificationService] = []

        if config["ntfy"]["enabled"]:
            self.notification_services.append(NtfyNotifier(config["ntfy"]))

        if config["gotify"]["enabled"]:
            self.notification_services.append(GotifyNotifier(config["gotify"]))

        if config["discord_webhook"]["enabled"]:
            self.notification_services.append(DiscordWebhookNotifier(config["discord_webhook"]))

    def _handle_packet(self, packet: Dict[str, Any]):
        """Internal callback function to handle payload summaries from AutoRX"""

        logging.debug(f"Got packet #{packet['frame']} from sonde {packet['callsign']}")

        # Update internal list
        serial = packet["callsign"]
        with self.tracked_sondes_lock:
            # Log message if sonde is new
            if serial not in self.tracked_sondes:
                logging.info(f"Got new {packet['model']} sonde: {serial}")

            self.tracked_sondes[serial] = [
                time.time(),
                packet["latitude"],
                packet["longitude"],
                packet["altitude"],
                packet["model"]
            ]

        with self.sondes_altitudes_lock:
            self.sondes_altitudes[serial].append(packet["altitude"])
    
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

                # Remove from sondes_altitudes
                with self.sondes_altitudes_lock:
                    del self.sondes_altitudes[serial]

            # Log
            if len(remove) > 0:
                for serial in remove:
                    logging.info("Removed old sonde from tracked list: "+str(serial))

    def _notify(self, notification_type: str, serial: str, sonde_type: str, distance: float):
        """Internal function to send notifications for a specific sonde"""

        logging.info(f"Sending notifications for {notification_type} of sonde {serial} ({sonde_type})")

        for service in self.notification_services:
            service.notify(notification_type, serial, sonde_type, distance)

    def _check_range_rings(
            self,
            serial: str,
            distance: float,
            altitude: float,
            ring_prefix: str = ""
        ) -> Dict[str, Any] | None:
        """Internal function to check for range ring hits for a specified sonde"""

        for ring in self.range_rings:
            # Skip already triggered rings
            if ring_prefix+"range_ring_"+str(ring["id"]) in self.notified_sondes[serial]:
                continue

            # Check if ring should be triggered
            if (int(distance) <= ring["range"]) and (int(altitude) <= ring["max_altitude"]):
                return ring # Only return ring with smallest radius (range_rings list is sorted by asc. radius)

        return None
    
    def _set_ring_notified(self, serial: str, notified_ring_id: int, ring_prefix: str = ""):
        """Internal function to add a ring and all larger rings to the notified list of a sondes"""

        for ring in self.range_rings:
            if ring["id"] >= notified_ring_id:
                self.notified_sondes[serial].append(ring_prefix+"range_ring_"+str(ring["id"]))

    def _landing_prediction(
            self,
            start_time: datetime,
            latitude: float,
            longitude: float,
            altitude: float,
            descending: bool
        ) -> Dict[str, float | datetime] | None:
        """Internal function to predict the landing position of a sonde"""

        altitude = int(altitude)
        time_formatted = start_time.isoformat().split("+")[0]
        logging.debug(f"Running prediction for {latitude}, {longitude}, {altitude}m {'descending' if descending else 'rising'} at {time_formatted}")

        # If sonde is descending, set burst point to altitude to skip ascent
        if descending:
            burst_altitude = altitude+0.1
        else:
            burst_altitude = self.config["prediction"]["burst_altitude"]

        # Add URL parameters
        url = self.tawhiri_api_url+f"?launch_latitude={latitude}" \
                                   f"&launch_longitude={longitude}" \
                                   f"&launch_altitude={altitude}" \
                                   f"&launch_datetime={time_formatted}Z" \
                                   f"&ascent_rate={self.config['prediction']['ascent_rate']}" \
                                   f"&burst_altitude={burst_altitude}" \
                                   f"&descent_rate={self.config['prediction']['descent_rate']}"

        # Make request and load response json
        request = requests.get(url)

        if request.status_code != 200:
            logging.error(f"Tawhiri prediction API returned status code {request.status_code}: {request.text}")
            return None

        prediction = json.loads(request.content)
        landing = prediction["prediction"][1]["trajectory"][-1]
        landing["datetime"] = datetime.fromisoformat(landing["datetime"])

        return landing

    def _check_notifications(self):
        """Internal function to check if notifications need to be sent"""

        logging.debug("Checking notifications")

        with self.tracked_sondes_lock and self.notified_sondes_lock and self.sondes_altitudes_lock:
            for serial, values in self.tracked_sondes.items():
                # Calculate distance to sonde
                distance = geopy.distance.geodesic(
                    self.station_position,
                    (values[1], values[2])
                ).m
                altitude = values[3]

                triggered_ring = self._check_range_rings(serial, distance, altitude)
                if triggered_ring is not None:
                    self._notify("range_ring_"+triggered_ring["name"], serial, values[4], distance)
                    self._set_ring_notified(serial, triggered_ring["id"])

                if self.prediction_enabled:
                    # Only run if 3 frames have been received yet
                    alts = self.sondes_altitudes[serial]
                    if len(alts) < 3:
                        logging.debug(f"Skipping prediciton for sonde {serial} because not enought frames have been received")
                        continue

                    # Only run if a packet has been received since the last notification check cycle
                    if round(time.time() - values[0]) > self.notify_check_interval:
                        logging.debug(f"Skipping prediciton for sonde {serial} as last receive was too long ago")
                        continue

                    # Determine wether sonde is descending or not
                    is_descending = all(alts[i] > alts[i+1] for i in range(len(alts) - 1))

                    # If option to only predict for descending sondes is set and sonde is not descending, skip
                    if self.only_predict_descending and (not is_descending):
                        logging.debug(f"Skipping prediction for sonde {serial} as it is not descending")
                        continue

                    # Run prediction
                    now = datetime.now(timezone.utc)
                    prediction = self._landing_prediction(now, values[1], values[2], values[3], is_descending)

                    if prediction is None: # Error while predicting, skip
                        continue

                    # Calculate distance
                    prediction_distance = distance = geopy.distance.geodesic(
                        self.station_position,
                        (prediction["latitude"], prediction["longitude"])
                    ).m

                    # Check for range ring hits
                    triggered_ring = self._check_range_rings(serial, prediction_distance, prediction["altitude"], "prediction_") # type: ignore
                    if triggered_ring is not None:
                        self._notify("prediction_"+"range_ring_"+triggered_ring["name"], serial, values[4], prediction_distance)
                        self._set_ring_notified(serial, triggered_ring["id"], "prediction_")

    def run(self):
        """Run notifier"""

        logging.info("Running notifier")
        try:
            # Start AutoRX listener
            self.autorx_listener = autorx.AutoRXListener(
                self.config["autorx"]["host"],
                self.config["autorx"]["port"],
                self._handle_packet
            )
            self.autorx_listener.start()

            while True:
                self._purge_old_tracked()
                self._check_notifications()
                time.sleep(self.notify_check_interval)
        except KeyboardInterrupt:
            logging.info("Caught KeyboardInterrupt, shutting down")
        except Exception as e:
            logging.error(f"Got exception while running notifier: {e}")
            logging.info(traceback.format_exc())
        finally:
            # Close any open connections
            self.autorx_listener.close()
