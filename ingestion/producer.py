import os
import json
import time
from datetime import datetime, timedelta
from confluent_kafka import Producer
import cdsapi
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ERA5-Producer")

# Configuration Kafka (à adapter selon votre docker-compose)
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = "era5-raw-data"

# Initialisation du producteur Kafka
producer = Producer({'bootstrap.servers': KAFKA_BROKER})

def delivery_report(err, msg):
    """ Callback pour confirmer que Kafka a bien reçu le message """
    if err is not None:
        logger.error(f"Échec de livraison Kafka : {err}")
    else:
        logger.info(f"✅ Message envoyé à Kafka sur {msg.topic()} [{msg.partition()}]")

def fetch_recent_era5():
    """ Télécharge les 7 derniers jours d'ERA5 (Surface et Pressure) """
    client = cdsapi.Client()
    
    # ERA5 a un décalage d'environ 5 jours. On calcule la fenêtre de 7 jours.
    end_date = datetime.now() - timedelta(days=5)
    start_date = end_date - timedelta(days=6) # Fenêtre de 7 jours
    
    # Formatage des dates pour l'API
    days_list = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    
    # Dossier de destination
    raw_dir = os.path.abspath("../data/raw/live")
    os.makedirs(raw_dir, exist_ok=True)
    
    file_name_surface = f"era5_live_surface_{end_date.strftime('%Y%m%d')}.nc"
    file_name_pressure = f"era5_live_pressure_{end_date.strftime('%Y%m%d')}.nc"
    
    file_path_surface = os.path.join(raw_dir, file_name_surface)
    file_path_pressure = os.path.join(raw_dir, file_name_pressure)
    
    # 1. Download Surface
    if not os.path.exists(file_path_surface):
        logger.info(f"⬇️ Téléchargement des données de surface du {start_date.date()} au {end_date.date()}...")
        client.retrieve("reanalysis-era5-land", {
            "variable": ["2m_temperature", "2m_dewpoint_temperature", "10m_u_component_of_wind", "10m_v_component_of_wind", "surface_solar_radiation_downwards"],
            "year": list(set([d.split('-')[0] for d in days_list])),
            "month": list(set([d.split('-')[1] for d in days_list])),
            "day": list(set([d.split('-')[2] for d in days_list])),
            "time": [f"{h:02d}:00" for h in range(24)], # 24h for surface usually
            "area": [36, -17, 27, -1], # Maroc
            "format": "netcdf"
        }, file_path_surface)
        
    # 2. Download Pressure
    if not os.path.exists(file_path_pressure):
        logger.info(f"⬇️ Téléchargement des données de pression (z500/t850) du {start_date.date()} au {end_date.date()}...")
        client.retrieve("reanalysis-era5-pressure-levels", {
            "product_type": "reanalysis",
            "variable": ["geopotential", "temperature"],
            "pressure_level": ["500", "850"],
            "year": list(set([d.split('-')[0] for d in days_list])),
            "month": list(set([d.split('-')[1] for d in days_list])),
            "day": list(set([d.split('-')[2] for d in days_list])),
            "time": ["00:00", "06:00", "12:00", "18:00"], # Often only 4 times/day needed for synoptic, adjust if needed
            "area": [36, -17, 27, -1],
            "format": "netcdf"
        }, file_path_pressure)

    return file_path_surface, file_path_pressure, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

def main():
    logger.info("Démarrage du Job d'Ingestion ERA5...")
    try:
        # 1. Télécharger la donnée
        file_path_surface, file_path_pressure, start_date, end_date = fetch_recent_era5()
        
        # 2. Créer le message pour Spark
        message = {
            "event": "new_weather_data",
            "file_path_surface": file_path_surface,
            "file_path_pressure": file_path_pressure,
            "start_date": start_date,
            "end_date": end_date,
            "timestamp": datetime.now().isoformat()
        }
        
        # 3. Envoyer à Kafka
        producer.produce(
            KAFKA_TOPIC, 
            key="morocco_live", 
            value=json.dumps(message), 
            callback=delivery_report
        )
        producer.flush() # S'assure que le message est parti
        
    except Exception as e:
        logger.error(f"Erreur critique lors de l'ingestion : {e}")

if __name__ == "__main__":
    main()