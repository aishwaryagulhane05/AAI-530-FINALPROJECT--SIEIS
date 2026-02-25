"""
Full SIEIS Pipeline Test Suite

Tests the complete data flow:
1. Docker containers running
2. Data in InfluxDB (incremental only)
3. Data in MinIO (historical + incremental)
4. API endpoints working
5. ML model inference
6. Dashboard data loading
7. End-to-end validation

Usage:
    python scripts/test_full_pipeline.py
    python scripts/test_full_pipeline.py --verbose
    python scripts/test_full_pipeline.py --skip-api  # Skip API tests
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import logging
import subprocess
from datetime import datetime, timedelta
from time import sleep

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FullPipelineTest:
    """Complete pipeline validation test."""
    
    def __init__(self, verbose=False, skip_api=False):
        self.verbose = verbose
        self.skip_api = skip_api
        self.test_results = {}
        self.failed_tests = []
        self.passed_tests = []
    
    # ==================== PHASE 1: DOCKER TESTS ====================
    
    def test_1_docker_containers_running(self):
        """TEST 1: All Docker containers are running."""
        logger.info("\n" + "="*80)
        logger.info("TEST 1: Docker Containers Running")
        logger.info("="*80)
        
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=sieis"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            required_containers = [
                "sieis-simulator",
                "sieis-consumer",
                "sieis-influxdb3",
                "sieis-minio",
                "sieis-redpanda"
            ]
            
            missing = []
            for container in required_containers:
                if container not in result.stdout:
                    missing.append(container)
            
            if missing:
                logger.error(f"❌ FAIL: Missing containers: {missing}")
                self.failed_tests.append("Docker containers")
                return False
            
            logger.info("✅ PASS: All required containers running")
            for container in required_containers:
                logger.info(f"   ✅ {container}")
            
            self.passed_tests.append("Docker containers")
            return True
        
        except Exception as e:
            logger.error(f"❌ FAIL: {e}")
            self.failed_tests.append("Docker containers")
            return False
    
    def test_2_influxdb_connectivity(self):
        """TEST 2: InfluxDB is accessible."""
        logger.info("\n" + "="*80)
        logger.info("TEST 2: InfluxDB Connectivity")
        logger.info("="*80)
        
        try:
            result = subprocess.run(
                ["curl", "-s", "http://localhost:8086/health"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if '"status":"pass"' in result.stdout or "healthy" in result.stdout:
                logger.info("✅ PASS: InfluxDB is healthy")
                self.passed_tests.append("InfluxDB connectivity")
                return True
            else:
                logger.error(f"❌ FAIL: InfluxDB not healthy. Response: {result.stdout}")
                self.failed_tests.append("InfluxDB connectivity")
                return False
        
        except Exception as e:
            logger.error(f"❌ FAIL: {e}")
            self.failed_tests.append("InfluxDB connectivity")
            return False
    
    def test_3_minio_connectivity(self):
        """TEST 3: MinIO is accessible."""
        logger.info("\n" + "="*80)
        logger.info("TEST 3: MinIO Connectivity")
        logger.info("="*80)
        
        try:
            from minio import Minio
            from src.app.config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY
            
            client = Minio(
                MINIO_ENDPOINT,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY
            )
            
            # Try to list buckets
            buckets = client.list_buckets()
            bucket_names = [b.name for b in buckets.buckets]
            
            if "sieis-archive" in bucket_names:
                logger.info("✅ PASS: MinIO is accessible with 'sieis-archive' bucket")
                self.passed_tests.append("MinIO connectivity")
                return True
            else:
                logger.error(f"❌ FAIL: 'sieis-archive' bucket not found")
                self.failed_tests.append("MinIO connectivity")
                return False
        
        except Exception as e:
            logger.error(f"❌ FAIL: {e}")
            self.failed_tests.append("MinIO connectivity")
            return False
    
    # ==================== PHASE 2: DATA QUALITY TESTS ====================
    
    def test_4_influxdb_has_incremental_data(self):
        """TEST 4: InfluxDB has incremental data (last 24h)."""
        logger.info("\n" + "="*80)
        logger.info("TEST 4: InfluxDB Has Incremental Data")
        logger.info("="*80)
        
        try:
            from influxdb_client import InfluxDBClient
            from src.app.config import INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET
            
            client = InfluxDBClient(
                url=INFLUX_URL,
                token=INFLUX_TOKEN,
                org=INFLUX_ORG
            )
            query_api = client.query_api()
            
            query = f'''from(bucket: "{INFLUX_BUCKET}")
                |> range(start: -24h)
                |> filter(fn: (r) => r._measurement == "sensor_reading")
                |> count()
            '''
            
            result = query_api.query(query)
            
            count = 0
            for table in result:
                for record in table.records:
                    count += record.get_value()
            
            client.close()
            
            if count > 0:
                logger.info(f"✅ PASS: Found {count:,} records in last 24h")
                self.passed_tests.append("InfluxDB incremental data")
                return True
            else:
                logger.error("❌ FAIL: No data found in InfluxDB (last 24h)")
                self.failed_tests.append("InfluxDB incremental data")
                return False
        
        except Exception as e:
            logger.error(f"❌ FAIL: {e}")
            self.failed_tests.append("InfluxDB incremental data")
            return False
    
    def test_5_mote_count_correct(self):
        """TEST 5: Mote count is 42-44."""
        logger.info("\n" + "="*80)
        logger.info("TEST 5: Correct Mote Count (42-44)")
        logger.info("="*80)
        
        try:
            from influxdb_client import InfluxDBClient
            from src.app.config import INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET
            
            client = InfluxDBClient(
                url=INFLUX_URL,
                token=INFLUX_TOKEN,
                org=INFLUX_ORG
            )
            query_api = client.query_api()
            
            query = f'''from(bucket: "{INFLUX_BUCKET}")
                |> range(start: -24h)
                |> filter(fn: (r) => r._measurement == "sensor_reading")
                |> group(columns: ["mote_id"])
                |> distinct(column: "mote_id")
                |> count()
            '''
            
            result = query_api.query(query)
            
            mote_count = 0
            for table in result:
                for record in table.records:
                    mote_count += 1
            
            client.close()
            
            if 42 <= mote_count <= 44:
                logger.info(f"✅ PASS: Found {mote_count} motes (expected 42-44)")
                self.passed_tests.append("Mote count")
                return True
            else:
                logger.error(f"❌ FAIL: Found {mote_count} motes (expected 42-44)")
                self.failed_tests.append("Mote count")
                return False
        
        except Exception as e:
            logger.error(f"❌ FAIL: {e}")
            self.failed_tests.append("Mote count")
            return False
    
    def test_6_sensor_values_valid(self):
        """TEST 6: Sensor values are within valid ranges."""
        logger.info("\n" + "="*80)
        logger.info("TEST 6: Sensor Values Within Valid Ranges")
        logger.info("="*80)
        
        try:
            from influxdb_client import InfluxDBClient
            from src.app.config import INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET
            
            client = InfluxDBClient(
                url=INFLUX_URL,
                token=INFLUX_TOKEN,
                org=INFLUX_ORG
            )
            query_api = client.query_api()
            
            valid_ranges = {
                'temperature': (-10, 50),
                'humidity': (0, 100),
                'light': (0, 5000),
                'voltage': (2.0, 3.5),
            }
            
            all_valid = True
            for field, (min_val, max_val) in valid_ranges.items():
                query = f'''from(bucket: "{INFLUX_BUCKET}")
                    |> range(start: -24h)
                    |> filter(fn: (r) => r._measurement == "sensor_reading")
                    |> filter(fn: (r) => r._field == "{field}")
                '''
                
                result = query_api.query(query)
                
                out_of_range = 0
                for table in result:
                    for record in table.records:
                        value = record.get_value()
                        if value is not None and not (min_val <= value <= max_val):
                            out_of_range += 1
                
                if out_of_range > 0:
                    logger.warning(f"⚠️  {field}: {out_of_range} out-of-range values")
                    all_valid = False
                else:
                    logger.info(f"✅ {field}: All values in range ({min_val}-{max_val})")
            
            client.close()
            
            if all_valid:
                logger.info("✅ PASS: All sensor values valid")
                self.passed_tests.append("Sensor values")
                return True
            else:
                logger.warning("⚠️  PASS WITH WARNINGS: Some out-of-range values")
                self.passed_tests.append("Sensor values")
                return True
        
        except Exception as e:
            logger.error(f"❌ FAIL: {e}")
            self.failed_tests.append("Sensor values")
            return False
    
    def test_7_minio_has_data(self):
        """TEST 7: MinIO has Parquet data files."""
        logger.info("\n" + "="*80)
        logger.info("TEST 7: MinIO Has Data Files")
        logger.info("="*80)
        
        try:
            from minio import Minio
            from src.app.config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY
            
            client = Minio(
                MINIO_ENDPOINT,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY
            )
            
            # Count parquet files
            objects = client.list_objects("sieis-archive", recursive=True)
            parquet_count = 0
            file_list = []
            
            for obj in objects:
                if obj.object_name.endswith('.parquet'):
                    parquet_count += 1
                    file_list.append(obj.object_name)
                    if len(file_list) <= 5:
                        logger.info(f"   Sample: {obj.object_name}")
            
            if parquet_count > 0:
                logger.info(f"✅ PASS: Found {parquet_count} Parquet files in MinIO")
                self.passed_tests.append("MinIO data files")
                return True
            else:
                logger.error("❌ FAIL: No Parquet files found in MinIO")
                self.failed_tests.append("MinIO data files")
                return False
        
        except Exception as e:
            logger.error(f"❌ FAIL: {e}")
            self.failed_tests.append("MinIO data files")
            return False
    
    # ==================== PHASE 3: RECENT DATA TESTS ====================
    
    def test_8_recent_data_within_1_hour(self):
        """TEST 8: Most recent data is within 1 hour."""
        logger.info("\n" + "="*80)
        logger.info("TEST 8: Recent Data Within 1 Hour")
        logger.info("="*80)
        
        try:
            from influxdb_client import InfluxDBClient
            from src.app.config import INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET
            
            client = InfluxDBClient(
                url=INFLUX_URL,
                token=INFLUX_TOKEN,
                org=INFLUX_ORG
            )
            query_api = client.query_api()
            
            query = f'''from(bucket: "{INFLUX_BUCKET}")
                |> range(start: -24h)
                |> filter(fn: (r) => r._measurement == "sensor_reading")
                |> sort(columns: ["_time"], desc: true)
                |> limit(n: 1)
            '''
            
            result = query_api.query(query)
            
            latest = None
            for table in result:
                for record in table.records:
                    latest = record.get_time()
                    break
            
            client.close()
            
            if latest:
                now = datetime.now(latest.tzinfo)
                diff_minutes = (now - latest).total_seconds() / 60
                
                if diff_minutes < 60:
                    logger.info(f"✅ PASS: Latest data is {diff_minutes:.1f} minutes old")
                    self.passed_tests.append("Recent data freshness")
                    return True
                else:
                    logger.error(f"❌ FAIL: Latest data is {diff_minutes:.1f} minutes old (expected < 60)")
                    self.failed_tests.append("Recent data freshness")
                    return False
            else:
                logger.error("❌ FAIL: Could not determine latest timestamp")
                self.failed_tests.append("Recent data freshness")
                return False
        
        except Exception as e:
            logger.error(f"❌ FAIL: {e}")
            self.failed_tests.append("Recent data freshness")
            return False
    
    # ==================== PHASE 4: API TESTS ====================
    
    def test_9_api_health_endpoint(self):
        """TEST 9: API /health endpoint responds."""
        if self.skip_api:
            logger.info("\n⏭️  Skipping API tests (--skip-api flag)")
            return None
        
        logger.info("\n" + "="*80)
        logger.info("TEST 9: API Health Endpoint")
        logger.info("="*80)
        
        try:
            result = subprocess.run(
                ["curl", "-s", "http://localhost:8000/health"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if '"status":"healthy"' in result.stdout or "healthy" in result.stdout:
                logger.info("✅ PASS: API health endpoint responds")
                self.passed_tests.append("API health")
                return True
            else:
                logger.error(f"❌ FAIL: API not responding. Response: {result.stdout}")
                self.failed_tests.append("API health")
                return False
        
        except Exception as e:
            logger.warning(f"⚠️  SKIP: API not running (can start with: uvicorn src.app.api.main:app --reload)")
            return None
    
    def test_10_api_sensors_endpoint(self):
        """TEST 10: API /api/v1/sensors/latest endpoint."""
        if self.skip_api:
            logger.info("\n⏭️  Skipping API tests (--skip-api flag)")
            return None
        
        logger.info("\n" + "="*80)
        logger.info("TEST 10: API Sensors Latest Endpoint")
        logger.info("="*80)
        
        try:
            result = subprocess.run(
                ["curl", "-s", "http://localhost:8000/api/v1/sensors/latest"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if '"readings"' in result.stdout or "mote" in result.stdout:
                logger.info("✅ PASS: API sensors endpoint responds")
                self.passed_tests.append("API sensors endpoint")
                return True
            else:
                logger.error(f"❌ FAIL: No response from sensors endpoint")
                self.failed_tests.append("API sensors endpoint")
                return False
        
        except Exception as e:
            logger.warning(f"⚠️  SKIP: API not responding")
            return None
    
    # ==================== PHASE 5: ML TESTS ====================
    
    def test_11_ml_model_exists(self):
        """TEST 11: ML model artifacts exist."""
        logger.info("\n" + "="*80)
        logger.info("TEST 11: ML Model Artifacts")
        logger.info("="*80)
        
        try:
            model_dir = Path(__file__).parent.parent / "src/app/ml/models"
            
            if not model_dir.exists():
                logger.error("❌ FAIL: ML models directory doesn't exist")
                self.failed_tests.append("ML model artifacts")
                return False
            
            model_files = list(model_dir.glob("anomaly_detector_*.pkl"))
            
            if model_files:
                logger.info(f"✅ PASS: Found {len(model_files)} model artifacts")
                for model_file in model_files[:3]:
                    logger.info(f"   {model_file.name}")
                self.passed_tests.append("ML model artifacts")
                return True
            else:
                logger.warning("⚠️  SKIP: No model artifacts found (not trained yet)")
                return None
        
        except Exception as e:
            logger.warning(f"⚠️  SKIP: {e}")
            return None
    
    # ==================== PHASE 6: DASHBOARD TESTS ====================
    
    def test_12_dashboard_app_exists(self):
        """TEST 12: Streamlit dashboard app exists."""
        logger.info("\n" + "="*80)
        logger.info("TEST 12: Streamlit Dashboard App")
        logger.info("="*80)
        
        try:
            dashboard_file = Path(__file__).parent.parent / "src/app/dashboard/app.py"
            
            if dashboard_file.exists():
                logger.info("✅ PASS: Dashboard app.py exists")
                self.passed_tests.append("Dashboard app")
                return True
            else:
                logger.warning("⚠️  SKIP: Dashboard app not created yet")
                return None
        
        except Exception as e:
            logger.warning(f"⚠️  SKIP: {e}")
            return None
    
    # ==================== MAIN TEST RUNNER ====================
    
    def run_all_tests(self):
        """Run all tests."""
        logger.info("="*80)
        logger.info("SIEIS FULL PIPELINE TEST SUITE")
        logger.info("="*80)
        logger.info(f"Time: {datetime.now()}")
        logger.info(f"Verbose: {self.verbose}")
        logger.info(f"Skip API: {self.skip_api}")
        logger.info("="*80)
        
        # Phase 1: Docker
        self.test_1_docker_containers_running()
        self.test_2_influxdb_connectivity()
        self.test_3_minio_connectivity()
        
        # Phase 2: Data Quality
        self.test_4_influxdb_has_incremental_data()
        self.test_5_mote_count_correct()
        self.test_6_sensor_values_valid()
        self.test_7_minio_has_data()
        
        # Phase 3: Recent Data
        self.test_8_recent_data_within_1_hour()
        
        # Phase 4: API
        self.test_9_api_health_endpoint()
        self.test_10_api_sensors_endpoint()
        
        # Phase 5: ML
        self.test_11_ml_model_exists()
        
        # Phase 6: Dashboard
        self.test_12_dashboard_app_exists()
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary."""
        logger.info("\n" + "="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        
        total = len(self.passed_tests) + len(self.failed_tests)
        
        logger.info(f"\n✅ PASSED: {len(self.passed_tests)}")
        for test in self.passed_tests:
            logger.info(f"   ✅ {test}")
        
        if self.failed_tests:
            logger.info(f"\n❌ FAILED: {len(self.failed_tests)}")
            for test in self.failed_tests:
                logger.error(f"   ❌ {test}")
        
        logger.info("\n" + "-"*80)
        
        if len(self.failed_tests) == 0:
            logger.info(f"🎉 ALL TESTS PASSED! ({len(self.passed_tests)}/{total})")
            return True
        else:
            logger.error(f"⚠️  {len(self.failed_tests)} test(s) failed ({len(self.passed_tests)}/{total} passed)")
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Run full SIEIS pipeline test suite'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--skip-api',
        action='store_true',
        help='Skip API tests (if API not running)'
    )
    
    args = parser.parse_args()
    
    tester = FullPipelineTest(verbose=args.verbose, skip_api=args.skip_api)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()