# SIEIS - Smart Indoor Environmental Intelligent System

Real-time sensor data simulation and analytics system using Kafka, InfluxDB 2.7, MinIO (Parquet archive), and Python.

## 🏗️ Architecture Overview

**Dual-Write Pattern for Hot & Cold Data:**

- **Hot Path (Real-time):** CSV → Simulator → Redpanda → Consumer → InfluxDB 2.7 → Streamlit Dashboard
  - InfluxDB 2.7 stores data for real-time queries (configurable retention)
  - Uses `updated_timestamp` field (2004 data mapped to 2025+)

- **Cold Path (Historical):** Consumer → MinIO (Parquet files)
  - Simultaneous write to MinIO as date-partitioned Parquet files
  - Used for ML training, analytics, long-term storage
  - Path structure: `year=YYYY/month=MM/day=DD/mote_id=X/*.parquet`

**Note:** InfluxDB 3.x migration is planned for future when stable Docker images are available.

## 📋 Table of Contents
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Setup Instructions](#setup-instructions)
- [Service Credentials](#service-credentials)
- [Running the Application](#running-the-application)
- [Accessing Services](#accessing-services)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, ensure you have:
- **Windows 11** (or similar OS with Docker Desktop)
- **Docker Desktop** 29.2.0 or later
  - Enable Hyper-V virtualization in BIOS
  - 4GB RAM minimum allocated to Docker
- **Python 3.11.5+**
- **Git** for version control
- **Internet connection** (for initial data download)
---

## Project Architecture

![SIEIS Architecture](./Documentation/Architecture%20Diagram/sieis-architecture.png)
---

## Project Structure

```
SIEIS/
├── data/
│   └── raw/
│       ├── data.txt                 # Intel Lab sensor readings (~150MB)
│       └── mote_locs.txt            # Mote location data
├── src/
│   ├── app/
│   │   ├── config.py                # Environment and config loader
│   │   ├── simulator/
│   │   │   ├── __init__.py
│   │   │   ├── data_loader.py       # CSV data parser
│   │   │   ├── producer.py          # Kafka producer wrapper
│   │   │   ├── emitter.py           # Per-mote emission logic
│   │   │   └── main.py              # Multi-threaded orchestrator
│   │   ├── consumer/                # [Phase 11] Kafka→InfluxDB consumer
│   │   ├── api/                     # [Phase 12] FastAPI ML endpoints
│   │   └── dashboard/               # [Phase 13] Streamlit dashboard
├── docker-compose.yml               # Infrastructure definition
├── .env                             # Environment variables
└── README.md                        # This file
```

---

## Setup Instructions

Follow these steps **in order** to set up the entire system:

### Step 1: Clone & Navigate to Project
```powershell
cd C:\Users\<YourUsername>\SIEIS
```

### Step 2: Install Dependencies (Optional - only for development)
```powershell
# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

Note: Dependencies are automatically installed in Docker containers.

### Step 3: Download Intel Lab Sensor Data
```powershell
# Create data directory
mkdir -p data\raw

# Download data (2.3M rows, ~150MB)
# Visit: http://db.lcs.mit.edu/labdata/
# Download: 2004-03-02 to 2004-03-31 (Intel Lab)
# Extract to: data\raw\data.txt
```
**Expected files:**
- `data\raw\data.txt` (150+ MB)
- `data\raw\mote_locs.txt` (552 B)

### Step 4: Start All Services with Docker Compose
```powershell
# Navigate to project root
cd C:\Users\<YourUsername>\SIEIS

# Build and start all services (Redpanda, InfluxDB 3, MinIO, Simulator, Consumer)
docker-compose up --build -d

# View logs (optional)
docker-compose logs -f

# Verify containers are running
docker ps
```

**Expected services (6 containers):**
```
CONTAINER ID   IMAGE                              STATUS
<id>          redpandadata/redpanda:latest        Up <time>
<id>          redpandadata/console:latest         Up <time>
<id>          influxdata/influxdb3-core:latest    Up <time>
<id>          minio/minio:latest                  Up <time>
<id>          sieis-simulator                     Up <time>
<id>          sieis-consumer                      Up <time>
```

All services are now containerized and orchestrated by Docker Compose!

### Step 5: Verify Services are Running

**Check Redpanda (Kafka):**
```powershell
docker exec -it sieis-redpanda rpk cluster info
```

**Check InfluxDB 2.7:**
```powershell
# Open InfluxDB UI
start http://localhost:8086
# Login: admin / password123
# Navigate to Data Explorer to query sensor_reading measurement
```

**Check MinIO (browse at http://localhost:9001):**
- Username: `minioadmin`
- Password: `minioadmin123`
- Verify bucket `sieis-archive` exists and contains Parquet files

**View Consumer Logs:**
```powershell
docker-compose logs -f consumer
```

Expected: Dual-write logs showing "Dual-write successful: InfluxDB + MinIO"

---

## Service Credentials

### 🔥 Redpanda (Kafka Broker)
- **Host:** `localhost:9092` (from Windows host)
- **Host:** `host.docker.internal:9092` (from Docker containers)
- **Port:** 9092
- **Topic:** `sensor_readings`
- **Default Topic Partitions:** 6

### 📊 Redpanda Console (UI)
- **URL:** `http://localhost:8080`
- **No authentication required**
- **Features:** View topics, messages, partitions, consumer groups
- **Usage:** Browse sensor_readings topic in real-time

### 💾 InfluxDB 2.7 (Time-Series Database - Hot Data)
- **URL:** `http://localhost:8086`
- **Organization:** `sieis`
- **Bucket:** `sensor_data`
- **Username:** `admin`
- **Password:** `password123`
- **API Token:** `my-super-secret-token`
- **Retention:** Configurable (30d recommended for cold path duration)
- **Query Language:** Flux
- **Login:** Open http://localhost:8086, login with admin/password123

### 🗄️ MinIO (Object Storage - Cold Data Archive)
- **Console URL:** `http://localhost:9001`
- **API URL:** `http://localhost:9000`
- **Username:** `minioadmin`
- **Password:** `minioadmin123`
- **Bucket:** `sieis-archive`
- **Format:** Parquet files (date-partitioned)
- **Usage:** Browse files via console, query with Python (see `src/app/ml/load_historical.py`)

---

## Running the Application

### All Services Run Automatically!

With the new containerized architecture, everything runs automatically:

```powershell
# Start everything
docker-compose up -d

# Stop everything
docker-compose down

# Restart specific service
docker-compose restart simulator
docker-compose restart consumer
```

**What's happening:**
1. **Simulator** container emits sensor data to Redpanda (Kafka)
2. **Consumer** container reads from Kafka and writes to both:
   - InfluxDB 3 (real-time queries, last 30 days)
   - MinIO (historical Parquet archive, permanent)
3. Data is immediately available in both hot and cold storage

### Verify Messages Are Flowing
```powershell
# In another terminal
docker exec sieis-redpanda rpk topic consume sensor_readings --num 5 --offset start
```

**Expected:** JSON messages with fields: mote_id, timestamp, temperature, humidity, light, voltage

### Example Message (Now includes `updated_timestamp`)
```json
{
  "topic": "sensor_readings",
  "key": "8",
  "value": "{
    \"mote_id\": 8,
    \"timestamp\": \"2004-02-28T01:02:16.424892\",
    \"updated_timestamp\": \"2025-02-28T01:02:16.424892\",
    \"temperature\": 19.1848,
    \"humidity\": 38.9742,
    \"light\": 108.56,
    \"voltage\": 2.68742,
    \"epoch\": 9
  }",
  "partition": 0,
  "offset": 0
}
```

**Note:** `updated_timestamp` maps 2004 data to 2025+ for realistic demos
```

---

## Accessing Services

| Service | URL | Purpose |
|---------|-----|---------|
| Redpanda Console | `http://localhost:8080` | Browse Kafka topics & messages |
| InfluxDB 2.7 | `http://localhost:8086` | Query real-time data (Flux, admin/password123) |
| MinIO Console | `http://localhost:9001` | Browse Parquet files (minioadmin/minioadmin123) |
| MinIO API | `http://localhost:9000` | S3-compatible object storage API |
| Kafka Broker | `localhost:9092` | Direct Kafka client connections |

---

## Querying Historical Data from MinIO

Use the provided utility to load historical Parquet data for ML training or analytics:

```python
from datetime import datetime
from src.app.ml.load_historical import load_historical_data

# Load February 2025 data
df = load_historical_data(
    start_date=datetime(2025, 2, 1),
    end_date=datetime(2025, 2, 28),
    mote_ids=[1, 2, 3]  # Optional: filter specific motes
)

print(f"Loaded {len(df)} records")
print(df.head())

# Use for ML training, analytics, etc.
```

Data is organized in MinIO as:
```
s3://sieis-archive/
  year=2025/
    month=02/
      day=01/
        mote_id=1/
          batch_20250201_120000.parquet
          batch_20250201_120030.parquet
        mote_id=2/
          ...
```

---

## Troubleshooting

### 1. Docker Containers Not Starting
```powershell
# Check logs
docker-compose logs -f

# Restart containers
docker-compose down
docker-compose up -d
```

### 2. Redpanda Console Not Accessible (localhost:8080)
```powershell
# Verify container is running
docker ps | grep console

# Check if port is in use
Get-NetTCPConnection -LocalPort 8080

# If blocked, use different port in docker-compose.yml
# Change "8080:8080" to "8081:8080"
```

### 3. Kafka Producer Connection Timeout
```powershell
# Verify broker is healthy
docker exec sieis-redpanda rpk cluster info

# Check if advertise address is correct (should show host.docker.internal:9092)
# If localhost appears, restart containers:
docker-compose down
docker-compose up -d
```

### 4. InfluxDB Login Issues
```powershell
# Reset InfluxDB (removes all data)
docker-compose down
docker volume rm sieis_influxdb_data
docker-compose up -d
```
Then login with: `admin` / `password123`

### 5. Python Module Not Found
```powershell
# Ensure PYTHONPATH includes project root
# Use -m flag to run Python modules:
.\venv\Scripts\python.exe -m src.app.simulator.main

# NOT:
.\venv\Scripts\python.exe src/app/simulator/main.py
```

---

## Project Phases

| Phase | Status | Component | Purpose |
|-------|--------|-----------|---------|
| 1-6 | ✅ Complete | Setup & Infrastructure | Docker, venv, config |
| 7 | ✅ Complete | Data Loader | CSV parsing, validation |
| 8 | ✅ Complete | Simulator | Producer, emitter, orchestrator |
| 11 | ⏳ Pending | Consumer | Kafka→InfluxDB pipeline |
| 12 | ⏳ Pending | API | FastAPI ML endpoints |
| 13 | ⏳ Pending | Dashboard | Streamlit visualization |

---

## Contributing

When adding new services or changing credentials:
1. Update `.env` file
2. Update `docker-compose.yml` if needed
3. Update this README with new URLs and credentials
4. Commit changes to git

---

## Quick Reference Commands

```powershell
# Start everything
docker-compose up -d

# Stop everything
docker-compose down

# View logs
docker-compose logs -f redpanda
docker-compose logs -f influxdb
docker-compose logs -f sieis-console

# Run simulator
.\venv\Scripts\python.exe -m src.app.simulator.main

# Check Kafka topic
docker exec sieis-redpanda rpk topic list
docker exec sieis-redpanda rpk topic describe sensor_readings

# Consume messages
docker exec sieis-redpanda rpk topic consume sensor_readings --num 10

# Check which ports are in use
Get-NetTCPConnection -State Listen | Where-Object {$_.LocalPort -in @(8080, 8086, 9092)}
```

---

**Last Updated:** February 5, 2026  
**Python Version:** 3.11.5  
**Docker Desktop Version:** 29.2.0
