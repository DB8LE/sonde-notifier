import json
import logging

import requests
from datetime import datetime, timezone
from typing import Optional, Tuple

import geopy.distance

    
class LandingPrediction:
    def __init__(
            self,
            latitude: float,
            longitude: float,
            altitude: float,
            landing_time: datetime,
        ) -> None:
        self.latitude = latitude
        self.longitude = longitude
        self.altitude = altitude
        self.landing_time = landing_time

    def calculate_distance(self, observer: Tuple[float, float]) -> float:
        """
        Calculate distance from a certain observer point (lat, lon) to the landing prediction.
        Returns distance in meters.
        """
    
        return geopy.distance.geodesic(
            observer,
            (self.latitude, self.longitude)
        ).m

class PredictionEngine:
    def __init__(
            self,
            api_url: str,
            ascent_rate: float, # m/s
            burst_altitude: int, # meters
            descent_rate: float # m/s
        ) -> None:
        self.api_url = api_url
        self.ascent_rate = ascent_rate
        self.burst_altitude = burst_altitude
        self.descent_rate = descent_rate

    def run_landing_prediction(
            self,
            start_time: datetime,
            latitude: float,
            longitude: float,
            altitude: float, # meters
            descending: bool
        ) -> Optional[LandingPrediction]:
        """Predict the landing position of a sonde"""

        altitude = int(altitude)
        time_formatted = start_time.isoformat().split("+")[0]
        logging.debug(f"Running prediction for {latitude}, {longitude}, {altitude}m {'descending' if descending else 'rising'} at {time_formatted}")

        # If sonde is descending, set burst point to altitude to skip ascent
        if descending:
            burst_altitude = altitude+0.1
        else:
            burst_altitude = self.burst_altitude

        # Add URL parameters
        url = self.api_url+f"?launch_latitude={latitude}" \
                           f"&launch_longitude={longitude}" \
                           f"&launch_altitude={altitude}" \
                           f"&launch_datetime={time_formatted}Z" \
                           f"&ascent_rate={self.ascent_rate}" \
                           f"&burst_altitude={burst_altitude}" \
                           f"&descent_rate={self.descent_rate}"

        # Make request and load response json
        try:
            request = requests.get(url, timeout=3)
        except Exception as e:
            logging.error("Error while getting prediction from tawhiri API: "+str(e))
            return None

        if request.status_code != 200:
            logging.error(f"Tawhiri prediction API returned status code {request.status_code}: {request.text}")
            return None

        # Parse & process response
        try:
            prediction = json.loads(request.content)
        except json.JSONDecodeError as e:
            logging.error("Error while decoding JSON response from tawhiri API: "+str(e))
            return None

        landing_prediction = prediction["prediction"][1]["trajectory"][-1]
        landing_time = datetime.fromisoformat(landing_prediction["datetime"])

        return LandingPrediction(
            latitude=landing_prediction["latitude"],
            longitude=landing_prediction["longitude"],
            altitude=landing_prediction["altitude"],
            landing_time=landing_time
        )

