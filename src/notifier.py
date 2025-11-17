import copy
import logging
import time
import traceback
from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Literal, Optional, Self, Tuple

from . import autorx, prediction

TRACKED_SONDES_MAX_SECONDS = 5*60*60

class RangeRing:
    def __init__(self, id: int, name: str, range: int, max_altitude: int, only_descending: bool, prefix: str = "") -> None:
        self.id = id
        self.name = name
        self.range = range # meters
        self.max_altitude = max_altitude # meters
        self.only_descending = only_descending
        self.prefix = prefix

    def as_string(self, type: Literal["name", "id"], prefix_overwrite: str = "") -> str:
        """Get the current range ring as a string in the format {prefix|prefix_overwrite_}range_ring_{name|id}"""

        prefix = prefix_overwrite if prefix_overwrite != "" else self.prefix # Check wether to use prefix overwrite
        prefix = prefix + "_" if prefix != "" else prefix # Add _ if prefix is set

        suffix = self.name if type == "name" else self.id # Set suffix to either name or id

        return f"{prefix}range_ring_{suffix}"

class Notifier:
    def __init__(self, config: Dict[str, Any]) -> None:
        logging.info("Initializing notifier")

        self.config = config
        self.notify_check_interval = config["notifier"]["check_interval"] * 60 # Convert to seconds
        self.only_predict_descending = config["prediction"]["only_predict_descending"]
        self.station_position = (config["station"]["latitude"], config["station"]["longitude"])

        self.prediction_engine = None
        self.prediction_min_cycles = config["prediction"]["prediction_cycles"]
        self.notification_check_cycles = 1

        self.sondes_altitudes = defaultdict(lambda: deque(maxlen=5))
        self.sondes_altitudes_lock = Lock()

        self.tracked_sondes: Dict[str, autorx.SondeFrame] = {}
        self.tracked_sondes_lock = Lock()

        self.notified_sondes = defaultdict(list)
        self.notified_sondes_lock = Lock()

        # Set prediction engine
        if config["prediction"]["enabled"]:
            self.prediction_engine = prediction.PredictionEngine(
                config["prediction"]["api_url"],
                config["prediction"]["ascent_rate"],
                config["prediction"]["burst_altitude"],
                config["prediction"]["descent_rate"]
            )

        # Parse range rings
        self.range_rings: List[RangeRing] = []
        try:
            for id, range_ring in enumerate(config["notifier"]["range_rings"]):
                self.range_rings.append(
                    RangeRing(
                        id=id,
                        name=str(range_ring["name"]).replace("_", "-"),
                        range=int(range_ring["radius"]*1000),
                        max_altitude=int(range_ring["max_altitude"]*1000),
                        only_descending=range_ring["only_descending"]
                    )
                )
        except KeyError as e:
            logging.error("Invalid key in range rings: "+str(e))
            exit(1)

        if len(self.range_rings) == 0:
            logging.error("Define at least one range ring!")
            exit(1)

        # Prepare list of notification services from config
        logging.debug("Initializing notification services")
        from .notification_services import NotificationService
        self.notification_services: List[NotificationService] = []

        if config["email"]["enabled"]:
            from .notification_services import EmailNotifier
            self.notification_services.append(EmailNotifier(config["email"]))

        if config["ntfy"]["enabled"]:
            from .notification_services import NtfyNotifier
            self.notification_services.append(NtfyNotifier(config["ntfy"]))

        if config["gotify"]["enabled"]:
            from .notification_services import GotifyNotifier
            self.notification_services.append(GotifyNotifier(config["gotify"]))

        if config["discord_webhook"]["enabled"]:
            from .notification_services import DiscordWebhookNotifier
            self.notification_services.append(DiscordWebhookNotifier(config["discord_webhook"]))

        if len(self.notification_services) == 0:
            logging.warning("No notification services enabled")

    def _handle_packet(self, frame: autorx.SondeFrame):
        """Internal callback function to handle payload summaries from AutoRX"""

        logging.debug(f"Got packet #{frame.frame} from sonde {frame.serial}")

        # Update internal list
        with self.tracked_sondes_lock:
            # Log message if sonde is new
            if frame.serial not in self.tracked_sondes:
                logging.info(f"Got new {frame.model} sonde: {frame.serial}")

            self.tracked_sondes[frame.serial] = frame

        with self.sondes_altitudes_lock:
            self.sondes_altitudes[frame.serial].append(frame.altitude)
    
    def _purge_old_tracked(self):
        """Internal function to remove all old sondes from tracked_sondes dict"""

        logging.debug("Purging old sondes from tracked list")

        remove = []
        with self.tracked_sondes_lock:
            # Check which sondes are old
            for serial, frame in self.tracked_sondes.items():
                assert frame.time is not None # impossible, just to make typechecker happy
                frame_age = (datetime.now(timezone.utc) - frame.time).total_seconds()
                if frame_age >= TRACKED_SONDES_MAX_SECONDS:
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

    def _notify_rangering(
            self,
            latest_frame: autorx.SondeFrame,
            triggered_ring: RangeRing,
            distance: float
        ):
        """Internal function to send range ring notifications for a specific sonde"""

        logging.info(f"Sending notifications for sonde {latest_frame.serial} triggering range ring {triggered_ring.name}")

        for service in self.notification_services:
            service.notify_rangering(latest_frame, triggered_ring, distance)

    def _notify_rangering_prediction(
            self,
            latest_frame: autorx.SondeFrame,
            landing_prediction: prediction.LandingPrediction,
            triggered_ring: RangeRing,
            prediction_distance: float
        ):
        """Internal function to send range ring notifications for a specific sonde"""

        logging.info(f"Sending notifications for prediction of sonde {latest_frame.serial} triggering range ring {triggered_ring.name}")

        for service in self.notification_services:
            service.notify_rangering_prediction(latest_frame, landing_prediction, triggered_ring, prediction_distance)

    def _check_range_rings(
            self,
            serial: str,
            distance: float,
            altitude: float,
            descending: bool,
            ring_prefix: str = ""
        ) -> RangeRing | None:
        """Internal function to check for range ring hits for a specified sonde"""

        for ring in self.range_rings:
            # Skip already triggered rings
            if ring.as_string("id", ring_prefix) in self.notified_sondes[serial]:
                continue

            # Skip if ring only allows descending sondes and sonde is not descending
            if ring.only_descending and not descending:
                continue

            # Check if ring should be triggered
            if (int(distance) <= ring.range) and (int(altitude) <= ring.max_altitude):
                # Return ring with correct prefix
                ring = copy.deepcopy(ring)
                ring.prefix = ring_prefix

                return ring # Only return ring with smallest radius (range_rings list is sorted by asc. radius)

        return None
    
    def _set_ring_notified(self, serial: str, notified_ring: RangeRing):
        """Internal function to add a ring and all larger rings to the notified list of a sondes"""

        for ring in self.range_rings:
            if ring.id >= notified_ring.id:
                self.notified_sondes[serial].append(ring.as_string("id", notified_ring.prefix))

    def _check_notifications(self):
        """Internal function to check if notifications need to be sent"""

        logging.debug("Checking notifications")

        # Check if enough notification check cycles have been completed to run a prediction
        run_prediction = False
        if self.prediction_engine is not None:
            if self.notification_check_cycles < self.prediction_min_cycles:
                status = f"{self.notification_check_cycles}/{self.prediction_min_cycles}"
                logging.debug(status+" check cycles for prediction")
            else:
                self.notification_check_cycles = 0
                run_prediction = True

        with self.tracked_sondes_lock and self.notified_sondes_lock and self.sondes_altitudes_lock:
            for serial, frame in self.tracked_sondes.items():
                # Determine wether sonde is descending or not
                altitudes = self.sondes_altitudes[serial]
                if len(altitudes) < 3:
                    is_descending = False # Assume sonde is rising if there are less than 3 received frames
                else:
                    is_descending = all(altitudes[i] > altitudes[i+1] for i in range(len(altitudes) - 1))

                # Calculate distance to sonde
                sonde_distance = frame.calculate_distance(self.station_position)

                triggered_ring = self._check_range_rings(serial, sonde_distance, frame.altitude, is_descending)
                if triggered_ring is not None:
                    self._notify_rangering(frame, triggered_ring, sonde_distance)
                    self._set_ring_notified(serial, triggered_ring)

                if run_prediction:
                    assert self.prediction_engine is not None # impossible, just to make typechecker happy

                    # Only run if 3 frames have been received already
                    if len(altitudes) < 3:
                        logging.debug(f"Skipping prediciton for sonde {serial} because not enought frames have been received")
                        continue

                    # Only run if a packet has been received since the last notification check cycle
                    assert frame.time is not None # impossible, just to make typechecker happy
                    frame_age = (datetime.now(timezone.utc) - frame.time).total_seconds()
                    if round(frame_age) > self.notify_check_interval:
                        logging.debug(f"Skipping prediciton for sonde {serial} as last receive was too long ago")
                        continue

                    # If option to only predict for descending sondes is set and sonde is not descending, skip
                    if self.only_predict_descending and (not is_descending):
                        logging.debug(f"Skipping prediction for sonde {serial} as it is not descending")
                        continue

                    # TODO: only run prediction if there are still notifications left for this sonde (?)

                    # Run prediction
                    now = datetime.now(timezone.utc)
                    landing_prediction = self.prediction_engine.run_landing_prediction(
                        now,
                        frame.latitude,
                        frame.longitude,
                        frame.altitude,
                        is_descending
                    )

                    if landing_prediction is None: # Error while predicting, skip
                        logging.warning(f"Prediction for sonde {serial} failed due to error while ")
                        continue

                    # Calculate distance
                    prediction_distance = landing_prediction.calculate_distance(self.station_position)

                    # Check for range ring hits
                    triggered_ring = self._check_range_rings(
                        serial,
                        prediction_distance,
                        landing_prediction.altitude,
                        is_descending,
                        "prediction"
                    )
                    if triggered_ring is not None:
                        self._notify_rangering_prediction(frame, landing_prediction, triggered_ring, prediction_distance)
                        self._set_ring_notified(serial, triggered_ring)

        self.notification_check_cycles += 1

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
