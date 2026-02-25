# SIEIS - Quick Start Guide

Get the project running in **under 10 minutes**.

---

## 🚀 Prerequisites

- ✅ **Docker Desktop** installed and running
- ✅ **Python 3.11+** installed
- ✅ **Git** installed
- ✅ **Internet connection**

---

## 📦 Step 1: Clone & Navigate

```powershell
cd C:\Users\aishw\SIEIS
```

---

## 📥 Step 2: Download Sensor Data

The project uses the Intel Lab sensor dataset. Download it to `data\raw\`:

### Option A: Manual Download (Recommended)
1. Visit: http://db.lcs.mit.edu/labdata/labdata.html
2. Download **data.txt** (~150 MB) 
3. Save to: `C:\Users\aishw\SIEIS\data\raw\data.txt`
4. Verify `mote_locs.txt` is also in `data\raw\`

### Option B: Using PowerShell
```powershell
# Create directory
New-Item -ItemType Directory -Force -Path data\raw

# Download files
Invoke-WebRequest -Uri "http://db.csail.mit.edu/labdata/data.txt" -OutFile "data\raw\data.txt"
Invoke-WebRequest -Uri "http://db.csail.mit.edu/labdata/mote_locs.txt" -OutFile "data\raw\mote_locs.txt"
```

**Verify files exist:**
```powershell
dir data\raw
```

Expected output:
```
data.txt       (~150 MB)
mote_locs.txt  (~552 bytes)
```

---

## 🐍 Step 3: Setup Python Environment

```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

**Verify installation:**
```powershell
pip list
```

You should see: `kafka-python`, `pandas`, `numpy`, `python-dotenv`, etc.

---

## 🐳 Step 4: Start Docker Infrastructure

```powershell
# Start all containers (Redpanda, InfluxDB, Console)
docker-compose up -d

# Wait 10 seconds for initialization
Start-Sleep -Seconds 10

# Verify containers are running
docker ps
```

**Expected output:**
```
CONTAINER ID   IMAGE                              STATUS
xxxx           redpandadata/redpanda:latest       Up X seconds
xxxx           redpandadata/console:latest        Up X seconds  
xxxx           influxdb:2.7                       Up X seconds
```

---

## ✅ Step 5: Verify Services

### Check Redpanda (Kafka)
```powershell
docker exec sieis-redpanda rpk cluster info
```

Expected: Should show broker ID 0 at `host.docker.internal:9092`

### Access Redpanda Console
Open browser: **http://localhost:8080**

You should see the Redpanda Console UI.

### Access InfluxDB
Open browser: **http://localhost:8086**

Login with:
- **Username:** `admin`
- **Password:** `password123`

---

## 🎯 Step 6: Run the Simulator

Start emitting sensor data to Kafka:

```powershell
# From project root with venv activated
python -m src.app.simulator.main
```

**Expected output:**
```
Loading data from: data/raw/data.txt
Loading mote locations from: data/raw/mote_locs.txt
Loaded 2313682 readings from 54 motes
Starting orchestrator with 54 motes...
Emitter started for mote_id=1 with 50959 readings
Emitter started for mote_id=2 with 41893 readings
...
```

🎉 **Success!** The simulator is now streaming data to Kafka.

Press **Ctrl+C** to stop the simulator.

---

## 🔍 Step 7: Verify Data Flow

### View Messages in Redpanda Console
1. Open **http://localhost:8080**
2. Click **Topics** → **sensor_readings**
3. Click **Messages** tab
4. You should see JSON messages streaming in real-time

### View Messages via CLI
```powershell
# Open a new terminal and run:
docker exec sieis-redpanda rpk topic consume sensor_readings --num 5
```

**Expected output:**
```json
{
  "mote_id": 8,
  "timestamp": "2004-02-28T01:02:16.424892",
  "temperature": 19.1848,
  "humidity": 38.9742,
  "light": 108.56,
  "voltage": 2.68742
}
```

---

## 🛑 Stopping Everything

### Stop Simulator
In the simulator terminal, press: **Ctrl+C**

### Stop Docker Containers
```powershell
docker-compose down
```

This stops all containers but preserves data in volumes.

### Stop and Remove All Data
```powershell
# WARNING: This deletes all InfluxDB data
docker-compose down -v
```

---

## 📊 Quick Reference

### Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| **Redpanda Console** | http://localhost:8080 | None |
| **InfluxDB** | http://localhost:8086 | admin / password123 |
| **Kafka Broker** | localhost:9092 | None |

### Common Commands

```powershell
# Start infrastructure
docker-compose up -d

# Stop infrastructure
docker-compose down

# View container logs
docker-compose logs -f redpanda
docker-compose logs -f influxdb

# Run simulator
python -m src.app.simulator.main

# List Kafka topics
docker exec sieis-redpanda rpk topic list

# Check Docker status
docker ps
```

---

## 🐛 Troubleshooting

### Issue: Docker containers won't start
```powershell
# Check logs
docker-compose logs

# Restart
docker-compose down
docker-compose up -d
```

### Issue: Port already in use (8080, 8086, or 9092)
```powershell
# Check which process is using the port
Get-NetTCPConnection -State Listen | Where-Object {$_.LocalPort -eq 8080}

# Kill the process or change the port in docker-compose.yml
```

### Issue: "data.txt not found"
- Ensure you downloaded the dataset to `data\raw\data.txt`
- Check the file size is ~150 MB
- Verify path in `.env` file: `DATA_PATH=data/raw/data.txt`

### Issue: Python module not found
```powershell
# Ensure venv is activated (you should see "(venv)" in prompt)
.\venv\Scripts\Activate.ps1

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Kafka connection timeout
```powershell
# Verify Redpanda is running
docker ps | grep redpanda

# Check broker health
docker exec sieis-redpanda rpk cluster info
```

---

## ✅ Step 7: Verify Everything Works

### Quick Verification Commands

**1. Verify All Containers Running:**
```powershell
docker ps
```
Expected: 6 containers (redpanda, console, influxdb3, minio, simulator, consumer)

**2. Verify InfluxDB Data:**
```powershell
python scripts/verify_influxDb.py
```
Expected output:
- Date range of stored data
- Total record count
- Unique mote count
- Sample records

**3. Verify MinIO Storage:**
```powershell
python scripts/verify_minio_storage.py
```
Expected: Parquet files in date-partitioned structure

**4. Run Full Pipeline Test:**
```powershell
python tests/test_full_pipeline.py
```
Expected: All 6 tests pass (containers, simulator, consumer → InfluxDB, consumer → MinIO, data consistency)

**5. Check Recent Kafka Messages:**
```powershell
docker exec sieis-redpanda rpk topic consume sensor_readings -n 5 -o newest
```

### Common Issues

**If InfluxDB shows no data:**
- Check consumer logs: `docker logs sieis-consumer | Select-String "Successfully wrote"`
- The consumer may have already processed all data
- Restart simulator: `docker restart sieis-simulator`

**If simulator finished all data:**
```powershell
# Check if incremental_data.txt has today's records
docker logs sieis-simulator | Select-String "Filtered to"

# If no records for today, regenerate the data:
python data/realtime_mapping/transform_to_realtime.py
```

---

## 🎓 Next Steps

Once the simulator is running successfully:

1. ✅ **Consumer Service** - Build Kafka → InfluxDB consumer (Phase 11)
2. ✅ **ML API** - Add anomaly detection endpoints (Phase 12)
3. ✅ **Dashboard** - Create Streamlit visualization (Phase 13)

See [README.md](README.md) for detailed documentation.

See [context.md](context.md) for comprehensive phase-by-phase implementation guide.

---

## 📝 Configuration

All settings are in `.env`:

```env
# Kafka
KAFKA_BROKER=localhost:9092
KAFKA_TOPIC=sensor_readings
SPEED_FACTOR=100

# Data
DATA_PATH=data/raw/data.txt
MOTE_LOCS_PATH=data/raw/mote_locs.txt

# InfluxDB
INFLUX_URL=http://localhost:8086
INFLUX_TOKEN=my-super-secret-token
INFLUX_ORG=sieis
INFLUX_BUCKET=sensor_data
```

**Adjust `SPEED_FACTOR`** to control data emission speed:
- `100` = 100x faster than real-time (default)
- `1` = Real-time speed
- `1000` = 1000x faster (very fast)

---

**Last Updated:** February 9, 2026  
**Estimated Time:** ~10 minutes  
**Status:** Simulator Phase Complete ✅
