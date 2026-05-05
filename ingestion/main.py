import os
import sys
import logging
import logging.config
import schedule
import time
from concurrent.futures import ThreadPoolExecutor

# Make sure we can load our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.config import settings
from ingestion.fetchers.gefs_fetcher import GEFSFetcher
from ingestion.fetchers.ecmwf_fetcher import ECMWFFetcher
from ingestion.producer import WeatherKafkaProducer

# Minimalistic structred logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("ingestion_main")

def run_job(fetcher_instance):
    """
    A unified runner function for fetchers executed in a thread pool.
    """
    try:
        fetcher_instance.run()
    except Exception as e:
        logger.error(f"Job failed for {fetcher_instance.__class__.__name__}: {e}")

def main():
    logger.info("Initializing Ingestion Layer Services...")
    
    # Init Kafka Producer Singleton
    producer = WeatherKafkaProducer()
    
    # Instances of Fetchers
    gefs_worker = GEFSFetcher()
    ecmwf_worker = ECMWFFetcher()

    # Create thread pool to allow parallel independent fetching
    executor = ThreadPoolExecutor(max_workers=5)

    # Schedule regular collections based on configuration
    schedule.every(settings.POLL_INTERVAL_GEFS).minutes.do(executor.submit, run_job, gefs_worker)
    schedule.every(settings.POLL_INTERVAL_ECMWF).minutes.do(executor.submit, run_job, ecmwf_worker)
    
    logger.info(f"Schedulers running:\n"
                f" - GEFS: every {settings.POLL_INTERVAL_GEFS} min\n"
                f" - ECMWF: every {settings.POLL_INTERVAL_ECMWF} min")

    # Initial Run immediately on startup instead of waiting for first trigger
    executor.submit(run_job, gefs_worker)
    executor.submit(run_job, ecmwf_worker)
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
            
            # Periodically poll kafka producer to serve delivery callbacks
            producer.producer.poll(0)
    except KeyboardInterrupt:
        logger.info("Service stopping gracefully...")
    finally:
        # Prevent Zombie Threads and Flush queues.
        schedule.clear()
        executor.shutdown(wait=True)
        producer.flush()

if __name__ == "__main__":
    main()
