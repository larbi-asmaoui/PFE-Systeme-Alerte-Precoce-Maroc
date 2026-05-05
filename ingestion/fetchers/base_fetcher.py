import logging
from abc import ABC, abstractmethod
from typing import Dict, Any
from ..producer import WeatherKafkaProducer
from ..config import settings

logger = logging.getLogger(__name__)

class BaseWeatherFetcher(ABC):
    """
    Abstract base class for all weather data fetchers.
    Forces all concrete sources to implement standard fetch and publish routines.
    """
    def __init__(self, target_topic: str):
        self.target_topic = target_topic
        self.producer = WeatherKafkaProducer()
    
    @abstractmethod
    def fetch_data(self) -> list[Dict[str, Any]]:
        """
        Connects to an external API (NOAA, ECMWF) and yields the raw responses.
        Return list of message payloads expected to hit Kafka.
        """
        pass

    def run(self):
        """
        Orchestrates fetching data and pushing arrays to Kafka topics.
        """
        try:
            logger.info(f"Starting fetch cycle for {self.__class__.__name__}")
            data_points = self.fetch_data()
            
            if not data_points:
                logger.info(f"No new data returned from {self.__class__.__name__}")
                return
                
            for point in data_points:
                # Optionally use a model hash or timestamp as partition key
                key = point.get('forecast_time', None)
                self.producer.publish_message(
                    topic=self.target_topic, 
                    payload=point,
                    key=key
                )
            
            # Optionally flush here if low volume, or let background thread do it if high volume.
            # self.producer.flush() 
            logger.info(f"Successfully published {len(data_points)} records to {self.target_topic}")
            
        except Exception as e:
            logger.error(f"Error during fetch/publish in {self.__class__.__name__}: {e}", exc_info=True)
