import os
from dotenv import load_dotenv

load_dotenv()

# Kafka
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "sensor_readings")

# InfluxDB
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "my-super-secret-token")
INFLUX_ORG = os.getenv("INFLUX_ORG", "sieis")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "sensor_data")

# Simulator
SPEED_FACTOR = int(os.getenv("SPEED_FACTOR", 100))
DATA_PATH = os.getenv("DATA_PATH", "data/raw/data.txt")
MOTE_LOCS_PATH = os.getenv("MOTE_LOCS_PATH", "data/raw/mote_locs.txt")
