"""
Verify MinIO storage has expected files.
List objects in 'sieis-archive' and check if they match today's date.
"""
from minio import Minio
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("MinIO-Verify")

# Config matches docker-compose
MINIO_ENDPOINT = "localhost:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin123"
BUCKET_NAME = "sieis-archive"

def main():
    logger.info(f"Connecting to MinIO at {MINIO_ENDPOINT}...")
    
    try:
        client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False
        )
        
        if not client.bucket_exists(BUCKET_NAME):
            logger.error(f"❌ Bucket '{BUCKET_NAME}' does not exist!")
            return

        logger.info(f"Checking bucket '{BUCKET_NAME}'...")
        objects = list(client.list_objects(BUCKET_NAME, recursive=True))
        
        count = len(objects)
        logger.info(f"✅ Found {count} objects in bucket.")
        
        if count == 0:
            logger.warning("   Bucket is empty. Consumer might not have written data yet.")
            return

        # Check for files matching today's date (formatted as YYYYMMDD in our parquet script)
        today_str = datetime.now().strftime("%Y%m%d")
        today_files = [o for o in objects if today_str in o.object_name]
        
        if today_files:
            logger.info(f"✅ Found {len(today_files)} files matching today's date pattern ({today_str}).")
            logger.info("Sample files:")
            for o in today_files[:3]:
                logger.info(f"   - {o.object_name} ({o.size} bytes)")
        else:
            logger.warning(f"⚠️  No files found matching today's date pattern ({today_str}).")
            logger.info("Sample of existing files:")
            for o in objects[:3]:
                logger.info(f"   - {o.object_name}")

    except Exception as e:
        logger.error(f"❌ Error verifying MinIO: {e}")

if __name__ == "__main__":
    main()
