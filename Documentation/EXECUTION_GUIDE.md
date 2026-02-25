# SIEIS Project - Complete Execution Guide

**Total Estimated Time: 6-12 hours** (includes historical data loading)

This guide provides step-by-step instructions to run the entire SIEIS project from scratch, including data loading, validation, ML training, and dashboard creation.

---

## Table of Contents

1. [Prerequisites & Setup](#prerequisites--setup)
2. [Start Docker Infrastructure](#start-docker-infrastructure)
3. [Load Historical Data](#load-historical-data)
4. [Verify Incremental Data Pipeline](#verify-incremental-pipeline)
5. [Data Validation](#data-validation)
6. [ML Model Training](#ml-model-training)
7. [Create Dashboards](#create-dashboards)
8. [Create API Layer](#create-api-layer)
9. [Testing & Verification](#testing--verification)

---

## Phase 1: Prerequisites & Setup

**Time: 15 minutes**

### 1.1 System Requirements

```powershell
# Verify Windows version
[System.Environment]::OSVersion

# Required versions:
# - Windows 10/11
# - Docker Desktop 4.10+
# - Python 3.11.5+
# - PowerShell 5.1+
```

### 1.2 Install Python Dependencies

```powershell
# Navigate to project root
cd c:\Users\aishw\SIEIS

# Install all required packages
pip install -r requirements.txt

# Verify key packages
pip list | grep -E "influxdb|minio|kafka|streamlit|fastapi|scikit-learn"
```

Expected packages:
- `influxdb-client` (latest)
- `minio` (7.1+)
- `kafka-python` (2.0+)
- `streamlit` (1.28+)
- `fastapi` (0.104+)
- `uvicorn` (0.24+)
- `scikit-learn` (1.3+)
- `pandas` (2.0+)
- `numpy` (1.24+)

### 1.3 Verify System Time Synchronization

```powershell
# Critical: InfluxDB and MinIO require synchronized system time
# Windows time sync
w32tm /resync

# Verify time
Get-Date

# Expected: Current UTC time within ±30 seconds
```

### 1.4 Pre-Execution Checklist

- [ ] Docker Desktop running
- [ ] Python 3.11.5+ installed
- [ ] All dependencies installed (`pip list`)
- [ ] System time synchronized (w32tm results)
- [ ] Port 8086 (InfluxDB), 9000 (MinIO), 9092 (Kafka), 8000 (API), 8501 (Streamlit) available

---

## Phase 2: Start Docker Infrastructure

**Time: 10 minutes**

### 2.1 Start All Containers

```powershell
cd c:\Users\aishw\SIEIS

# Bring up all services
docker-compose up -d

# Wait 30 seconds for containers to initialize
Start-Sleep -Seconds 30

# Verify all containers are running
docker-compose ps

# Expected output:
# NAME                COMMAND                  SERVICE      STATUS      PORTS
# sieis-simulator     "python /app/src/..."   simulator    running     
# sieis-consumer      "python /app/src/..."   consumer     running     
# sieis-redpanda      "redpanda start ..."    redpanda     running     0.0.0.0:9092->9092/tcp
# sieis-influxdb3     "influx"                influxdb     running     0.0.0.0:8086->8086/tcp
# sieis-minio         "minio server /data"    minio        running     0.0.0.0:9000->9000/tcp
```

### 2.2 Verify Container Health

```powershell
# Check logs for errors
docker-compose logs --tail=20 sieis-simulator
docker-compose logs --tail=20 sieis-consumer
docker-compose logs --tail=20 sieis-influxdb3

# Expected simulator output:
# "Filtered X records for today"
# "Published X messages to Kafka"

# Expected consumer output:
# "Successfully wrote X points to InfluxDB"
# "Successfully wrote X points to MinIO"
```

### 2.3 Verify Service Connectivity

```powershell
# Test InfluxDB
curl -I http://localhost:8086/health

# Test MinIO
curl -I http://localhost:9000/minio/health/live

# Expected: HTTP 200 responses
```

---

## Phase 3: Load Historical Data

**Time: 4-8 hours** (depends on data volume and disk speed)

> **Note:** Historical data loads into MinIO only (cold path). InfluxDB will receive only incremental daily data.

### 3.1 Start Historical Data Loading

```powershell
cd c:\Users\aishw\SIEIS

# Start loading historical data
# This reads data/raw/data.txt and writes to MinIO in date-partitioned Parquet format
python scripts/load_historical_data.py

# Expected first message:
# "Loading historical data from data/raw/data.txt"
# "Total records to process: 2,182,280"
```

### 3.2 Monitor Loading Progress

```powershell
# In a new terminal, monitor MinIO storage
while ($true) {
    $records = (docker-compose exec minio mc ls minio/sieis-sensor-history --recursive | Measure-Object -Line).Lines
    Write-Host "MinIO files written: $records"
    Start-Sleep -Seconds 30
}

# Expected progression:
# MinIO files written: 100 (at ~5% complete)
# MinIO files written: 500 (at ~50% complete)
# MinIO files written: 1000 (at ~100% complete - one file per mote per day)
```

### 3.3 Verify Historical Load Completion

```powershell
# Check final record count
python -c "
import os, json
import pandas as pd
from minio import Minio

client = Minio(
    'localhost:9000',
    access_key=os.environ.get('MINIO_ROOT_USER', 'minioadmin'),
    secret_key=os.environ.get('MINIO_ROOT_PASSWORD', 'minioadmin'),
    secure=False
)

total_records = 0
for obj in client.list_objects('sieis-sensor-history', recursive=True):
    if obj.name.endswith('.parquet'):
        print(f'{obj.name}: {obj.size} bytes')
        # In production, read and count rows
        total_records += 1

print(f'Total Parquet files: {total_records}')
print(f'Expected: ~1,000 files (365 days × 42-50 motes)')
"
```

### 3.4 If Load Stalls or Fails

```powershell
# Resume from where it stopped
python scripts/load_historical_data.py --resume

# Or restart completely
docker-compose down
docker volume rm sieis_minio_data
docker-compose up -d
Start-Sleep -Seconds 60
python scripts/load_historical_data.py
```

---

## Phase 4: Verify Incremental Data Pipeline

**Time: 5 minutes**

The incremental pipeline (simulator → Kafka → consumer → InfluxDB + MinIO) should be continuously running.

### 4.1 Check Simulator is Emitting

```powershell
# View simulator logs - should show daily data filtering
docker-compose logs sieis-simulator --tail=50

# Expected output:
# "Filtered 44 records for today (2026-02-23)"
# "Published 44 messages to Kafka topic: sensor-data"
```

### 4.2 Check Consumer is Writing

```powershell
# View consumer logs - should show InfluxDB and MinIO writes
docker-compose logs sieis-consumer --tail=50

# Expected output:
# "Consumer starting..."
# "Successfully wrote 44 points to InfluxDB"
# "Successfully wrote 44 points to MinIO (incremental)"
# "Batch complete. Sleeping for X seconds..."
```

### 4.3 Verify Data in InfluxDB

```powershell
# Query InfluxDB for latest data
curl -X POST http://localhost:8086/api/v2/query `
  -H "Authorization: Token YWJjZA==" `
  -H "Content-Type: application/vnd.flux" `
  -d 'from(bucket:"sieis") 
      |> range(start:-24h) 
      |> group(columns:["_measurement"]) 
      |> count()'

# Expected: 40-100+ points from last 24 hours

# Or use Python for clearer output
python -c "
from influxdb_client import InfluxDBClient
from datetime import datetime, timedelta

client = InfluxDBClient(url='http://localhost:8086', token='abc123==')
query_api = client.query_api()

query = '''
from(bucket: \"sieis\")
  |> range(start: -24h)
  |> group(columns: [\"_measurement\", \"mote_id\"])
  |> count()
'''

result = query_api.query(query)
print(f'Records in last 24h: {len(result)}')
print(f'Sample: {result[0] if result else \"No data\"}')
"
```

### 4.4 Verify Data in MinIO (Incremental)

```powershell
# Check incremental partition
python -c "
from minio import Minio
from datetime import datetime

client = Minio('localhost:9000', access_key='minioadmin', secret_key='minioadmin', secure=False)

today = datetime.now().strftime('%Y/%m/%d')
prefix = f'incremental/{today}/'

count = 0
for obj in client.list_objects('sieis-sensor-data', prefix=prefix, recursive=True):
    print(f'Found: {obj.name}')
    count += 1

print(f'Total incremental files for today: {count}')
print(f'Expected: 1-5 files (batched by consumer)')
"
```

---

## Phase 5: Data Validation

**Time: 10 minutes**

Run the validation script to ensure InfluxDB contains ONLY incremental data from the last 30 days.

### 5.1 Clean InfluxDB (if needed)

If InfluxDB has contaminated data from previous runs:

```powershell
# Stop containers
docker-compose down

# Remove InfluxDB volume
docker volume rm sieis_influxdb_data

# Restart
docker-compose up -d

# Wait for data accumulation
Start-Sleep -Seconds 120
```

### 5.2 Run Validation Tests

```powershell
cd c:\Users\aishw\SIEIS

# Run comprehensive validation
python scripts/validate_incremental_data.py

# Expected output:
# ✓ TEST 1: No data older than 30 days
# ✓ TEST 2: Data exists within last 30 days
# ✓ TEST 3: Today's data is most recent
# ✓ TEST 4: Correct mote count (42-50)
# ✓ TEST 5: Valid sensor values
# ✓ TEST 6: Date range is consistent
# ✓ TEST 7: No duplicate readings
# ✓ TEST 8: Correct measurement name
#
# ✅ ALL TESTS PASSED
```

### 5.3 Check MinIO Historical Data

```powershell
# Verify historical data structure
python scripts/verify_minio_storage.py

# Expected output:
# MinIO Storage Verification
# ============================
# Bucket: sieis-sensor-history
# - Parquet files: ~1,000
# - Date range: 2020-01-01 to 2026-02-23
# - Total size: ~500 MB
#
# Bucket: sieis-sensor-data
# - Incremental batches: 50-100
# - Date range: last 30 days
# - Total size: ~50 MB
```

---

## Phase 6: ML Model Training

**Time: 1-2 hours**

Train the Isolation Forest anomaly detection model on historical and recent data.

### 6.1 Create Training Script Directory

```powershell
# Create directory structure
mkdir -p src\app\ml\models
mkdir -p src\app\ml\training
mkdir -p src\app\ml\serving
mkdir -p src\app\ml\monitoring
```

### 6.2 Create Training Script

**File: `src/app/ml/training/train_anomaly_detector.py`**

```python
#!/usr/bin/env python3
"""
Anomaly Detector Training Script
Trains Isolation Forest model on historical and recent sensor data
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from influxdb_client import InfluxDBClient
from joblib import dump
from minio import Minio
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


class AnomalyDetectorTrainer:
    """Train anomaly detection models for sensor data"""

    def __init__(self, influx_url="http://localhost:8086", 
                 minio_url="localhost:9000",
                 influx_token="abc123=="):
        self.influx_client = InfluxDBClient(url=influx_url, token=influx_token)
        self.minio_client = Minio(
            minio_url,
            access_key=os.environ.get("MINIO_ROOT_USER", "minioadmin"),
            secret_key=os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin"),
            secure=False
        )
        self.query_api = self.influx_client.query_api()
        self.model_dir = Path("src/app/ml/models")
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def load_training_data(self, days=30) -> pd.DataFrame:
        """
        Load training data from InfluxDB (recent incremental data)
        Falls back to MinIO for historical data if available
        """
        print(f"Loading training data from last {days} days...")
        
        # Load from InfluxDB
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        query = f'''
        from(bucket: "sieis")
          |> range(start: {start_date.isoformat()}Z, stop: {end_date.isoformat()}Z)
          |> filter(fn: (r) => r._measurement == "sensor_reading")
          |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")
        '''
        
        try:
            result = self.query_api.query(query)
            records = []
            
            for table in result:
                for record in table.records:
                    records.append({
                        "timestamp": record.get_time(),
                        "mote_id": record.values.get("mote_id"),
                        "temperature": record.values.get("temperature"),
                        "humidity": record.values.get("humidity"),
                        "light": record.values.get("light")
                    })
            
            df = pd.DataFrame(records)
            print(f"Loaded {len(df)} records from InfluxDB")
            return df
            
        except Exception as e:
            print(f"Error loading from InfluxDB: {e}")
            return pd.DataFrame()

    def engineer_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, list]:
        """
        Engineer features for anomaly detection
        Returns: (feature_df, feature_names)
        """
        print("Engineering features...")
        
        # Drop rows with missing values
        df = df.dropna(subset=["temperature", "humidity", "light"])
        
        features = []
        feature_names = []
        
        # Raw values
        features.append(df["temperature"].values)
        feature_names.append("temperature")
        
        features.append(df["humidity"].values)
        feature_names.append("humidity")
        
        features.append(df["light"].values)
        feature_names.append("light")
        
        # Rolling statistics (7-point window)
        if len(df) > 7:
            features.append(df["temperature"].rolling(7).mean().fillna(0).values)
            feature_names.append("temp_rolling_7")
            
            features.append(df["humidity"].rolling(7).mean().fillna(0).values)
            feature_names.append("humidity_rolling_7")
        
        # Rate of change
        features.append(df["temperature"].diff().fillna(0).values)
        feature_names.append("temp_change")
        
        features.append(df["humidity"].diff().fillna(0).values)
        feature_names.append("humidity_change")
        
        # Stack features
        X = np.column_stack(features)
        
        print(f"Feature matrix shape: {X.shape}")
        print(f"Features: {feature_names}")
        
        return X, feature_names

    def train(self, X: np.ndarray, feature_names: list) -> Tuple[IsolationForest, StandardScaler]:
        """Train Isolation Forest model"""
        print("Training Isolation Forest model...")
        
        # Normalize features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Train model
        model = IsolationForest(
            contamination=0.05,  # Assume 5% anomalies
            n_estimators=100,
            random_state=42,
            n_jobs=-1
        )
        
        model.fit(X_scaled)
        
        # Calculate anomaly scores
        scores = model.score_samples(X_scaled)
        anomaly_rate = (model.predict(X_scaled) == -1).mean()
        
        print(f"Model trained:")
        print(f"  - Anomaly rate: {anomaly_rate*100:.2f}%")
        print(f"  - Mean anomaly score: {scores.mean():.4f}")
        print(f"  - Min/Max score: {scores.min():.4f} / {scores.max():.4f}")
        
        return model, scaler

    def save_model(self, model: IsolationForest, scaler: StandardScaler, 
                   feature_names: list) -> str:
        """Save model and metadata"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_name = f"isolation_forest_{timestamp}"
        model_path = self.model_dir / model_name
        model_path.mkdir(parents=True, exist_ok=True)
        
        # Save model
        dump(model, str(model_path / "model.joblib"))
        
        # Save scaler
        dump(scaler, str(model_path / "scaler.joblib"))
        
        # Save metadata
        metadata = {
            "model_type": "IsolationForest",
            "timestamp": timestamp,
            "features": feature_names,
            "contamination": 0.05,
            "n_estimators": 100,
            "created_at": datetime.now().isoformat()
        }
        
        with open(model_path / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
        
        print(f"Model saved to: {model_path}")
        print(f"Files: model.joblib, scaler.joblib, metadata.json")
        
        return str(model_path)

    def run(self):
        """Execute full training pipeline"""
        print("=" * 60)
        print("ANOMALY DETECTOR TRAINING PIPELINE")
        print("=" * 60)
        
        # Load data
        df = self.load_training_data(days=30)
        
        if len(df) == 0:
            print("ERROR: No training data loaded")
            return
        
        # Engineer features
        X, feature_names = self.engineer_features(df)
        
        if len(X) == 0:
            print("ERROR: No features engineered")
            return
        
        # Train
        model, scaler = self.train(X, feature_names)
        
        # Save
        model_path = self.save_model(model, scaler, feature_names)
        
        print("=" * 60)
        print("✅ TRAINING COMPLETE")
        print("=" * 60)
        
        return model_path


if __name__ == "__main__":
    trainer = AnomalyDetectorTrainer()
    trainer.run()
```

### 6.3 Run Training

```powershell
cd c:\Users\aishw\SIEIS

# Execute training script
python src\app\ml\training\train_anomaly_detector.py

# Expected output:
# ============================================================
# ANOMALY DETECTOR TRAINING PIPELINE
# ============================================================
# Loading training data from last 30 days...
# Loaded 10,000+ records from InfluxDB
# Engineering features...
# Feature matrix shape: (10000, 8)
# Features: ['temperature', 'humidity', 'light', 'temp_rolling_7', ...]
# Training Isolation Forest model...
# Model trained:
#   - Anomaly rate: 5.23%
#   - Mean anomaly score: -0.1234
#   - Min/Max score: -1.0000 / 0.8765
# Model saved to: src/app/ml/models/isolation_forest_20260223_143022
# Files: model.joblib, scaler.joblib, metadata.json
# ============================================================
# ✅ TRAINING COMPLETE
# ============================================================

# Verify model files exist
ls -Path src\app\ml\models\isolation_forest_* -Recurse
```

---

## Phase 7: Create Dashboards

**Time: 1-2 hours**

Create interactive Streamlit dashboards for data visualization.

### 7.1 Create Dashboard Main App

**File: `src/app/dashboard/app.py`**

```python
#!/usr/bin/env python3
"""
SIEIS Sensor Data Dashboard
Main Streamlit application with multi-page support
"""

import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="SIEIS Sensor Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🌍 SIEIS Sensor Data Dashboard")

st.markdown("""
### Real-time Environmental Monitoring System

Dashboard for monitoring sensor data from distributed motes with:
- **Real-time Data**: Temperature, humidity, light from last 24 hours
- **Historical Analysis**: Trends and patterns from historical data
- **Anomaly Detection**: ML-based anomaly detection and alerts

---
""")

st.info("""
**Navigation**: Use the sidebar to select different dashboard pages.
- **Active Sensors**: Real-time monitoring (last 24 hours)
- **Historical Trends**: Long-term analysis (last 30+ days)
- **Anomaly Detection**: ML anomaly insights
""")

st.write("Select a page from the sidebar to begin.")
```

### 7.2 Create Active Sensors Page

**File: `src/app/dashboard/pages/1_active_sensors.py`**

```python
#!/usr/bin/env python3
"""
Active Sensors Dashboard Page
Real-time monitoring of current sensor values
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from influxdb_client import InfluxDBClient


def get_influx_client() -> InfluxDBClient:
    """Initialize InfluxDB client"""
    return InfluxDBClient(
        url="http://localhost:8086",
        token=os.environ.get("INFLUX_TOKEN", "abc123==")
    )


@st.cache_data(ttl=300)
def load_latest_data() -> pd.DataFrame:
    """Load latest sensor readings from last 24 hours"""
    client = get_influx_client()
    query_api = client.query_api()
    
    query = '''
    from(bucket: "sieis")
      |> range(start: -24h)
      |> filter(fn: (r) => r._measurement == "sensor_reading")
      |> sort(columns: ["_time"], desc: true)
      |> limit(n: 10000)
    '''
    
    result = query_api.query(query)
    records = []
    
    for table in result:
        for record in table.records:
            records.append({
                "timestamp": record.get_time(),
                "mote_id": record.values.get("mote_id"),
                "field": record.values.get("_field"),
                "value": record.values.get("_value")
            })
    
    df = pd.DataFrame(records)
    
    # Pivot to get readings per mote
    if not df.empty:
        df_pivot = df.pivot_table(
            index=["timestamp", "mote_id"],
            columns="field",
            values="value",
            aggfunc="last"
        ).reset_index()
        return df_pivot
    
    return pd.DataFrame()


st.title("📊 Active Sensors")

st.markdown("Real-time monitoring of all active sensor motes (last 24 hours)")

# Load data
data = load_latest_data()

if data.empty:
    st.warning("No sensor data available. Check if containers are running.")
    st.stop()

# KPIs
col1, col2, col3, col4 = st.columns(4)

with col1:
    active_motes = data["mote_id"].nunique()
    st.metric("Active Motes", active_motes)

with col2:
    latest_reading = data["timestamp"].max()
    time_ago = (datetime.utcnow().replace(tzinfo=latest_reading.tzinfo) - latest_reading).total_seconds()
    st.metric("Latest Update", f"{int(time_ago)} seconds ago")

with col3:
    avg_temp = data["temperature"].mean()
    st.metric("Avg Temperature", f"{avg_temp:.1f}°C")

with col4:
    avg_humidity = data["humidity"].mean()
    st.metric("Avg Humidity", f"{avg_humidity:.1f}%")

st.divider()

# Charts
col1, col2 = st.columns(2)

with col1:
    # Temperature over time
    fig_temp = px.line(
        data,
        x="timestamp",
        y="temperature",
        color="mote_id",
        title="Temperature Trend (24h)",
        labels={"temperature": "Temp (°C)", "timestamp": "Time"}
    )
    fig_temp.update_layout(height=400, hovermode="x unified")
    st.plotly_chart(fig_temp, use_container_width=True)

with col2:
    # Humidity over time
    fig_humidity = px.line(
        data,
        x="timestamp",
        y="humidity",
        color="mote_id",
        title="Humidity Trend (24h)",
        labels={"humidity": "Humidity (%)", "timestamp": "Time"}
    )
    fig_humidity.update_layout(height=400, hovermode="x unified")
    st.plotly_chart(fig_humidity, use_container_width=True)

st.divider()

# Data table
st.subheader("Latest Readings by Mote")
latest_per_mote = data.sort_values("timestamp", ascending=False).drop_duplicates("mote_id")
display_cols = ["mote_id", "timestamp", "temperature", "humidity", "light"]
st.dataframe(
    latest_per_mote[display_cols].round(2),
    use_container_width=True,
    hide_index=True
)

# Refresh info
st.caption("💡 Data refreshes every 5 minutes. Dashboard reloads on parameter change.")
```

### 7.3 Run Dashboard

```powershell
cd c:\Users\aishw\SIEIS

# Start Streamlit dashboard
streamlit run src\app\dashboard\app.py

# Expected output:
# You can now view your Streamlit app in your browser.
# URL: http://localhost:8501

# Open browser and navigate to http://localhost:8501
```

---

## Phase 8: Create API Layer

**Time: 1-2 hours**

Create FastAPI application for programmatic data access.

### 8.1 Create API Main Application

**File: `src/app/api/main.py`**

```python
#!/usr/bin/env python3
"""
SIEIS Sensor Data API
FastAPI application for sensor data queries and ML inference
"""

import json
import os
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient
from pydantic import BaseModel
from uvicorn import run as uvicorn_run


# Pydantic models
class SensorReading(BaseModel):
    """Single sensor reading"""
    timestamp: str
    mote_id: str
    temperature: float
    humidity: float
    light: float


class DailyStats(BaseModel):
    """Daily statistics for a mote"""
    mote_id: str
    date: str
    avg_temperature: float
    max_temperature: float
    min_temperature: float
    avg_humidity: float
    max_humidity: float
    min_humidity: float
    reading_count: int


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str


# FastAPI app
app = FastAPI(
    title="SIEIS Sensor API",
    description="Real-time sensor data and analytics API",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# InfluxDB client
def get_influx_client() -> InfluxDBClient:
    """Get InfluxDB client"""
    return InfluxDBClient(
        url="http://localhost:8086",
        token=os.environ.get("INFLUX_TOKEN", "abc123==")
    )


# Routes

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/v1/sensors/latest", response_model=List[SensorReading])
def get_latest_readings(
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(1000, ge=1, le=100000)
):
    """Get latest sensor readings"""
    client = get_influx_client()
    query_api = client.query_api()
    
    query = f'''
    from(bucket: "sieis")
      |> range(start: -{hours}h)
      |> filter(fn: (r) => r._measurement == "sensor_reading")
      |> sort(columns: ["_time"], desc: true)
      |> limit(n: {limit})
    '''
    
    try:
        result = query_api.query(query)
        readings = []
        
        for table in result:
            for record in table.records:
                readings.append({
                    "timestamp": record.get_time().isoformat(),
                    "mote_id": record.values.get("mote_id", "unknown"),
                    "temperature": record.values.get("temperature", 0.0),
                    "humidity": record.values.get("humidity", 0.0),
                    "light": record.values.get("light", 0.0)
                })
        
        return readings
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/sensors/{mote_id}/daily-stats", response_model=List[DailyStats])
def get_daily_stats(
    mote_id: str,
    days: int = Query(7, ge=1, le=365)
):
    """Get daily statistics for a mote"""
    client = get_influx_client()
    query_api = client.query_api()
    
    query = f'''
    from(bucket: "sieis")
      |> range(start: -{days}d)
      |> filter(fn: (r) => r._measurement == "sensor_reading")
      |> filter(fn: (r) => r.mote_id == "{mote_id}")
      |> group(columns: ["_time", "_field"])
      |> aggregateWindow(every: 24h, fn: mean, createEmpty: false)
    '''
    
    try:
        result = query_api.query(query)
        
        # Process results into daily stats
        daily_data = {}
        
        for table in result:
            for record in table.records:
                date = record.get_time().date().isoformat()
                field = record.values.get("_field")
                value = record.values.get("_value", 0.0)
                
                if date not in daily_data:
                    daily_data[date] = {"mote_id": mote_id}
                
                daily_data[date][field] = value
        
        # Convert to response format
        stats = [DailyStats(
            mote_id=mote_id,
            date=date,
            avg_temperature=data.get("temperature", 0.0),
            max_temperature=data.get("temperature", 0.0),  # Simplified
            min_temperature=data.get("temperature", 0.0),
            avg_humidity=data.get("humidity", 0.0),
            max_humidity=data.get("humidity", 0.0),
            min_humidity=data.get("humidity", 0.0),
            reading_count=0
        ) for date, data in daily_data.items()]
        
        return sorted(stats, key=lambda x: x.date, reverse=True)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/summary")
def get_summary():
    """Get system summary"""
    client = get_influx_client()
    query_api = client.query_api()
    
    # Count motes
    query = '''
    from(bucket: "sieis")
      |> range(start: -24h)
      |> filter(fn: (r) => r._measurement == "sensor_reading")
      |> group(columns: ["mote_id"])
      |> count()
    '''
    
    try:
        result = query_api.query(query)
        mote_count = len(result) if result else 0
        
        return {
            "status": "operational",
            "active_motes": mote_count,
            "timestamp": datetime.utcnow().isoformat(),
            "endpoints": [
                "/health",
                "/api/v1/sensors/latest",
                "/api/v1/sensors/{mote_id}/daily-stats",
                "/api/v1/summary"
            ]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn_run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
```

### 8.2 Run API

```powershell
cd c:\Users\aishw\SIEIS

# Start FastAPI server
python -m uvicorn src.app.api.main:app --reload --host 0.0.0.0 --port 8000

# Expected output:
# INFO:     Uvicorn running on http://0.0.0.0:8000
# INFO:     Application startup complete

# Test API (in new terminal)
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","timestamp":"2026-02-23T14:30:22.123456"}

# Get latest readings
curl "http://localhost:8000/api/v1/sensors/latest?hours=24&limit=100"

# Expected response:
# [
#   {
#     "timestamp": "2026-02-23T14:30:00Z",
#     "mote_id": "mote_001",
#     "temperature": 22.5,
#     "humidity": 65.3,
#     "light": 450.2
#   },
#   ...
# ]
```

---

## Phase 9: Testing & Verification

**Time: 30 minutes**

Run full test suite to verify all components.

### 9.1 Run Validation Scripts

```powershell
cd c:\Users\aishw\SIEIS

# Test 1: Incremental data validation
python scripts/validate_incremental_data.py

# Expected: ✅ ALL TESTS PASSED

# Test 2: MinIO storage verification
python scripts/verify_minio_storage.py

# Expected: MinIO Storage Verification ====...
```

### 9.2 Test API Endpoints

```powershell
# In a new terminal

# Test health endpoint
curl http://localhost:8000/health

# Test latest readings
curl "http://localhost:8000/api/v1/sensors/latest?hours=24&limit=50"

# Test daily stats for a mote (replace mote_id)
curl "http://localhost:8000/api/v1/sensors/mote_001/daily-stats?days=7"

# Test summary
curl http://localhost:8000/api/v1/summary

# Expected: All responses should return HTTP 200 with JSON data
```

### 9.3 Test Dashboard

```powershell
# Open browser
Start-Process http://localhost:8501

# Verify:
# - Page loads without errors
# - KPI cards show values (active motes, avg temperature, etc.)
# - Charts display temperature and humidity trends
# - Data table shows recent readings
```

### 9.4 Run Unit Tests

```powershell
cd c:\Users\aishw\SIEIS

# Run all tests
pytest tests/ -v --tb=short

# Expected output:
# tests/test_data_loader.py::test_load_historical_data PASSED
# tests/test_container_influxdb.py::test_influxdb_connectivity PASSED
# tests/test_full_pipeline.py::test_incremental_pipeline PASSED
# ...
# ===================== X passed in Y.XXs ======================
```

### 9.5 Verification Checklist

- [ ] Docker containers running (docker-compose ps)
- [ ] InfluxDB has only incremental data (validate_incremental_data.py passes)
- [ ] MinIO has historical data structure verified
- [ ] ML model trained and saved (src/app/ml/models/ has files)
- [ ] API running and responding to requests
- [ ] Streamlit dashboard loads and displays data
- [ ] All unit tests passing
- [ ] No errors in container logs

---

## Troubleshooting

### InfluxDB Connection Issues

```powershell
# Check InfluxDB container
docker-compose logs sieis-influxdb3

# Restart InfluxDB
docker-compose restart sieis-influxdb3

# Clean restart (WARNING: loses all data)
docker-compose down
docker volume rm sieis_influxdb_data
docker-compose up -d sieis-influxdb3
```

### MinIO Time Skew Error

```powershell
# Sync system time
w32tm /resync

# Restart MinIO container
docker-compose restart sieis-minio

# Verify time
Get-Date
```

### Simulator Not Emitting Data

```powershell
# Check simulator logs
docker-compose logs sieis-simulator --tail=100

# Verify data file exists
Test-Path data\raw\data.txt
Test-Path data\processed\incremental_data.txt

# Restart simulator
docker-compose restart sieis-simulator
```

### API Port Already in Use

```powershell
# Find process using port 8000
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess

# Kill process (replace PID)
Stop-Process -Id <PID> -Force

# Or use different port
python -m uvicorn src.app.api.main:app --port 8001
```

---

## Summary

**Total Execution Time**: 6-12 hours (depending on historical load speed)

**Key Milestones**:
- ✅ Docker infrastructure running
- ✅ Historical data loaded to MinIO
- ✅ Incremental pipeline validating
- ✅ ML model trained and saved
- ✅ Dashboards and API operational
- ✅ Full test suite passing

**Next Steps**:
1. Keep Docker containers running for incremental data accumulation
2. Re-train ML model weekly on latest data: `python src/app/ml/training/train_anomaly_detector.py`
3. Monitor dashboard for anomalies
4. Review logs monthly for data quality issues

**Contact & Support**:
- See ARCHITECTURE.md for system design
- See ML_MODELS.md for ML pipeline details
- See PROJECT_ROADMAP.md for project phases
- See DEPLOYMENT.md for production deployment

---

**Document Version**: 1.0
**Last Updated**: February 23, 2026
**Status**: Ready for Execution
