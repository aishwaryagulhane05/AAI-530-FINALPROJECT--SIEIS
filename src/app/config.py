import os
from pathlib import Path

# ============================================================================
# PROJECT PATHS
# ============================================================================
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
MODELS_DIR = PROJECT_ROOT / "src/app/ml/models"

# ============================================================================
# INFLUXDB CONFIGURATION
# ============================================================================
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "my-super-secret-token")
INFLUX_ORG = os.getenv("INFLUX_ORG", "sieis")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "sensor_data")

# ============================================================================
# MINIO CONFIGURATION (S3-COMPATIBLE OBJECT STORAGE)
# ============================================================================
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "sieis-archive")

# ============================================================================
# REDPANDA/KAFKA CONFIGURATION
# ============================================================================
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:19092")  # 29092 was wrong; Redpanda external port is 19092
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "sensor_readings")
KAFKA_GROUP = os.getenv("KAFKA_GROUP", "sieis-consumer-group")

# ============================================================================
# SIMULATOR CONFIGURATION
# ============================================================================
SPEED_FACTOR = float(os.getenv("SPEED_FACTOR", "100.0"))
DATA_PATH = os.getenv("DATA_PATH", str(DATA_DIR / "processed/incremental_data.txt"))
MOTE_LOCS_PATH = os.getenv("MOTE_LOCS_PATH", str(DATA_DIR / "raw/mote_locs.txt"))
FILTER_TODAY_ONLY = os.getenv("FILTER_TODAY_ONLY", "true").lower() == "true"
# YEAR_OFFSET: shifts legacy 2004 timestamps to current year (fallback when updated_timestamp absent)
import datetime as _dt
YEAR_OFFSET = int(os.getenv("YEAR_OFFSET", str(_dt.datetime.now().year - 2004)))

# ============================================================================
# API CONFIGURATION
# ============================================================================
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_TITLE = "SIEIS API"
API_VERSION = "1.0.0"

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = LOGS_DIR / "sieis.log"

# ============================================================================
# APPLICATION CONFIGURATION
# ============================================================================
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# ============================================================================
# VALIDATION
# ============================================================================
def validate_config():
    """Validate all required configuration is set."""
    required = [
        ("INFLUX_URL", INFLUX_URL),
        ("MINIO_ENDPOINT", MINIO_ENDPOINT),
        ("MINIO_ACCESS_KEY", MINIO_ACCESS_KEY),
        ("MINIO_SECRET_KEY", MINIO_SECRET_KEY),
    ]
    
    missing = [name for name, value in required if not value]
    
    if missing:
        raise ValueError(f"Missing required configuration: {', '.join(missing)}")

if __name__ == "__main__":
    validate_config()
    print("✅ Config validation passed!")