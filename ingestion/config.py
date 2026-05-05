import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Kafka Configuration
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    KAFKA_CLIENT_ID: str = os.getenv("KAFKA_CLIENT_ID", "weather_ingestion_service")
    KAFKA_COMPRESSION_TYPE: str = os.getenv("KAFKA_COMPRESSION_TYPE", "snappy")
    
    # Topics
    TOPIC_GEFS_RAW: str = os.getenv("TOPIC_GEFS_RAW", "weather.forecast.gefs.raw")
    TOPIC_ECMWF_RAW: str = os.getenv("TOPIC_ECMWF_RAW", "weather.forecast.ecmwf.raw")
    TOPIC_ERA5_RAW: str = os.getenv("TOPIC_ERA5_RAW", "weather.historical.era5.raw")
    
    # External APIs
    ECMWF_API_URL: str = os.getenv("ECMWF_API_URL", "https://api.ecmwf.int/v1")
    ECMWF_API_KEY: str = os.getenv("ECMWF_API_KEY", "")
    NOAA_API_URL: str = os.getenv("NOAA_API_URL", "https://nomads.ncep.noaa.gov/cgi-bin/")
    
    # Polling intervals (minutes)
    POLL_INTERVAL_GEFS: int = int(os.getenv("POLL_INTERVAL_GEFS", "360"))  # GEFS updates every 6 hours
    POLL_INTERVAL_ECMWF: int = int(os.getenv("POLL_INTERVAL_ECMWF", "720")) # ECMWF updates every 12 hours
    POLL_INTERVAL_ERA5: int = int(os.getenv("POLL_INTERVAL_ERA5", "1440"))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
