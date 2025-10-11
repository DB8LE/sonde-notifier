import logging
import traceback
from typing import Any, Dict

class Notifier:
    def __init__(self, config: Dict[str, Any]) -> None:
        logging.info("Initializing notifier")

    def run(self):
        """Run notifier"""

        logging.info("Running notifier")

        try:
            logging.info("Hello World!")
        except KeyboardInterrupt:
            logging.info("Caught KeyboardInterrupt, shutting down")
        except Exception as e:
            logging.error(f"Got exception while running notifier: {e}")
            logging.info(traceback.format_exc())
        finally:
            # Close any open connections
            pass
