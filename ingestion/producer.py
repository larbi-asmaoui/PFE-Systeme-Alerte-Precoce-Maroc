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
    """ Télécharge les 14 derniers jours d'ERA5 """
    client = cdsapi.Client()
    
    # ERA5 a un décalage d'environ 5 jours. On calcule la fenêtre de 14 jours.
    end_date = datetime.now() - timedelta(days=5)
    start_date = end_date - timedelta(days=13) # Fenêtre de 14 jours
    
    # Formatage des dates pour l'API
    days_list = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(14)]
    
    # Dossier de destination
    raw_dir = os.path.abspath("../data/raw/live")
    os.makedirs(raw_dir, exist_ok=True)
    
    file_name = f"era5_live_{end_date.strftime('%Y%m%d')}.nc"
    file_path = os.path.join(raw_dir, file_name)
    
    if not os.path.exists(file_path):
        logger.info(f"⬇️ Téléchargement des données du {start_date.date()} au {end_date.date()}...")
        # Exemple de requête (à ajuster selon vos variables d'entraînement)
        client.retrieve("reanalysis-era5-land", {
            "variable": ["2m_temperature", "2m_dewpoint_temperature", "10m_u_component_of_wind", "10m_v_component_of_wind", "surface_solar_radiation_downwards"],
            "year": list(set([d.split('-')[0] for d in days_list])),
            "month": list(set([d.split('-')[1] for d in days_list])),
            "day": list(set([d.split('-')[2] for d in days_list])),
            "time": [f"{h:02d}:00" for h in range(24)],
            "area": [36, -17, 27, -1], # Maroc
            "format": "netcdf"
        }, file_path)
    
    return file_path, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

def main():
    logger.info("Démarrage du Job d'Ingestion ERA5...")
    try:
        # 1. Télécharger la donnée
        file_path, start_date, end_date = fetch_recent_era5()
        
        # 2. Créer le message pour Spark
        message = {
            "event": "new_weather_data",
            "file_path": file_path,
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