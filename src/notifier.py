import logging
import traceback
from typing import Any, Dict

from . import autorx

class Notifier:
    def __init__(self, config: Dict[str, Any]) -> None:
        logging.info("Initializing notifier")

        self.config = config

    def _handle_packet(self, packet: Dict[str, Any]):
        """Internal callback function to handle payload summaries from AutoRX"""

        logging.debug(f"Got packet #{packet["frame"]} from sonde {packet["callsign"]}")

    def run(self):
        """Run notifier"""

        logging.info("Running notifier")
        try:
            # Start AutoRX listener
            self.autorx_listener = autorx.AutoRXListener(self.config["autorx"]["port"], self._handle_packet)
            self.autorx_listener.start()

            while True:
                pass
        except KeyboardInterrupt:
            logging.info("Caught KeyboardInterrupt, shutting down")
        except Exception as e:
            logging.error(f"Got exception while running notifier: {e}")
            logging.info(traceback.format_exc())
        finally:
            # Close any open connections
            self.autorx_listener.close()
