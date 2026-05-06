import os
import json
import numpy as np
import xarray as xr
from pyspark.sql import SparkSession
from pyspark.sql.functions import col

# On pointe vers le dossier où les stats d'entraînement sont sauvegardées
STATS_PATH = os.path.abspath("../backend/artifacts/normalization.npz")
READY_DIR = os.path.abspath("../data/ready_for_inference")
os.makedirs(READY_DIR, exist_ok=True)

def process_netcdf_batch(df, epoch_id):
    """
    Cette fonction est exécutée par Spark pour chaque nouveau message Kafka.
    Elle fait la transformation métier (Z-Score)
    """
    # Récupérer les messages Kafka du micro-batch
    messages = df.selectExpr("CAST(value AS STRING)").collect()
    
    for row in messages:
        payload = json.loads(row['value'])
        file_path_surface = payload.get('file_path_surface') or payload.get('file_path')
        file_path_pressure = payload.get('file_path_pressure')
        end_date = payload['end_date']
        
        print(f"🔥 Spark traite le fichier surface : {file_path_surface}")
        if file_path_pressure: print(f"🔥 Spark traite le fichier pressure : {file_path_pressure}")
        
        if not os.path.exists(file_path_surface):
            print(f"Erreur : Le fichier de surface {file_path_surface} est introuvable.")
            continue
        if file_path_pressure and not os.path.exists(file_path_pressure):
            print(f"Erreur : Le fichier de pression {file_path_pressure} est introuvable.")
            continue
        
        try:
            # 1. Charger les statistiques de l'entraînement (pour éviter le Data Leakage)
            stats = np.load(STATS_PATH)
            train_mean = stats['mean']
            train_std = stats['std']
            
            # 2. Ouvrir les données live brutes avec Xarray
            ds_surface = xr.open_dataset(file_path_surface, engine="netcdf4")
            ds_pressure = xr.open_dataset(file_path_pressure, engine="netcdf4") if file_path_pressure else None
            
            # Merge ds_surface et ds_pressure en prenant soin des temps si nécessaire (Optionnel)
            # ds_live = xr.merge([ds_surface, ds_pressure]) 
            # 
            # Exemple : si votre modèle attend surface_solar_radiation_downwards, geopotential, etc
            # Pour l'instant on se limite à `ds_surface` pour illustrer la compatibilité avec avant
            ds_live = ds_surface
            
            # (Optionnel) Si vous devez faire un resample journalier (Tmax/Tmin) comme dans l'entraînement
            # ds_daily = ds_live.resample(time="1D").max() 
            
            # 3. Extraction en Tenseur Numpy (doit correspondre à l'ordre des canaux de l'entraînement)
            channels = ["t2m", "d2m", "u10", "v10", "ssrd"] # A adapter selon vos variables
            live_tensor = np.stack([ds_live[c].values for c in channels], axis=-1).astype(np.float32)
            
            # 4. Appliquer le Z-Score avec les stats historiques !
            live_tensor_norm = (live_tensor - train_mean) / train_std
            
            # 5. Sauvegarder le tenseur prêt pour le modèle PyTorch
            output_tensor_path = os.path.join(READY_DIR, f"tensor_live_{end_date}.npy")
            np.save(output_tensor_path, live_tensor_norm)
            
            print(f"✅ Tenseur normalisé sauvegardé pour PyTorch : {output_tensor_path}")
            ds_live.close()
            
        except Exception as e:
            print(f"❌ Erreur lors du traitement du fichier NetCDF dans Spark : {e}")

def start_spark_streaming():
    """ Initialise Spark et écoute Kafka en permanence """
    
    # Nécessite le package Spark-Kafka (à télécharger automatiquement par Spark)
    spark = (SparkSession.builder
        .appName("ERA5-Weather-Processor")
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0")
        .getOrCreate())
        
    spark.sparkContext.setLogLevel("WARN")
    
    print("🚀 Spark Streaming démarré, en écoute sur Kafka...")

    # Se connecter au Topic Kafka
    df_kafka = (spark
        .readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", "localhost:9092")
        .option("subscribe", "era5-raw-data")
        .option("startingOffsets", "latest")
        .load())

    # Chaque fois qu'un message arrive, on lance process_netcdf_batch
    query = (df_kafka.writeStream
        .foreachBatch(process_netcdf_batch)
        .start())

    query.awaitTermination()

if __name__ == "__main__":
    start_spark_streaming()