# SIEIS - Smart Indoor Environmental Intelligent System

Real-time sensor data simulation and analytics system using Kafka, InfluxDB, and Python.

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

### Step 2: Download Intel Lab Sensor Data
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

### Step 3: Create Python Virtual Environment
```powershell
# Create venv
python -m venv venv

# Activate venv
.\venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install kafka-python==2.0.2 pandas==2.1.0 numpy python-dotenv==1.0.0
```

### Step 4: Create .env Configuration File
Create `.env` in project root with:
```env
# Kafka Configuration
KAFKA_BROKER=localhost:9092
KAFKA_TOPIC=sensor_readings
SPEED_FACTOR=100

# Data Paths
DATA_PATH=data/raw/data.txt
MOTE_LOCS_PATH=data/raw/mote_locs.txt

# InfluxDB Configuration
INFLUXDB_URL=http://localhost:8086
INFLUXDB_ORG=sieis
INFLUXDB_BUCKET=sensor_data
INFLUXDB_TOKEN=my-super-secret-token
INFLUXDB_USERNAME=admin
INFLUXDB_PASSWORD=password123
```

### Step 5: Start Docker Containers
```powershell
# Navigate to project root
cd C:\Users\<YourUsername>\SIEIS

# Start Redpanda (Kafka), InfluxDB, and Redpanda Console
docker-compose up -d

# Wait 10 seconds for services to initialize
Start-Sleep -Seconds 10

# Verify containers are running
docker ps
```

**Expected output:**
```
CONTAINER ID   IMAGE                              STATUS
<id>          redpandadata/redpanda:latest        Up <time>
<id>          redpandadata/console:latest         Up <time>
<id>          influxdb:2.7                        Up <time>
```

### Step 6: Verify Redpanda Broker Health
```powershell
docker exec -it sieis-redpanda rpk cluster info
```

**Expected output:**
```
CLUSTER
=======
redpanda.<id>

BROKERS
=======
ID    HOST                  PORT
0*    host.docker.internal  9092
```

### Step 7: Run Tests (Optional but Recommended)
```powershell
# Run data loader tests
pytest tests/ -v
```

Expected: 5 tests passing in ~90 seconds

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

### 💾 InfluxDB (Time-Series Database)
- **URL:** `http://localhost:8086`
- **Organization:** `sieis`
- **Bucket:** `sensor_data`
- **Username:** `admin`
- **Password:** `password123`
- **API Token:** `my-super-secret-token`
- **Login Steps:**
  1. Open `http://localhost:8086` in browser
  2. User: `admin`, Password: `password123`
  3. Navigate to **Data → Buckets** to see `sensor_data`
  4. Use API Token in `.env` for programmatic access

---

## Running the Application

### Start Simulator (Emit Data to Kafka)
```powershell
# From project root with venv activated
.\venv\Scripts\python.exe -m src.app.simulator.main
```

**Output:**
```
INFO:src.app.simulator.main:Starting orchestrator for 60 motes
INFO:kafka.conn:<BrokerConnection node_id=0 host=host.docker.internal:9092...>: Connection complete.
```

**Behavior:**
- Spawns 60 threads (one per mote/sensor)
- Emits historical sensor data at accelerated speed (SPEED_FACTOR=100)
- Sends JSON messages to `sensor_readings` topic
- Press **Ctrl+C** to gracefully stop

### Verify Messages Are Flowing
```powershell
# In another terminal
docker exec sieis-redpanda rpk topic consume sensor_readings --num 5 --offset start
```

**Expected:** JSON messages with fields: mote_id, timestamp, temperature, humidity, light, voltage

### Example Message
```json
{
  "topic": "sensor_readings",
  "key": "8",
  "value": "{
    \"mote_id\": 8,
    \"timestamp\": \"2004-02-28T01:02:16.424892\",
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

---

## Accessing Services

| Service | URL | Purpose |
|---------|-----|---------|
| Redpanda Console | `http://localhost:8080` | Browse Kafka topics & messages |
| InfluxDB | `http://localhost:8086` | Query time-series data (admin/password123) |
| Kafka Broker | `localhost:9092` | Direct Kafka client connections |

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
