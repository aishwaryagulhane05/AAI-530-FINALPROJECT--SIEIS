# SIEIS Project Setup Guide
## Chronological Step-by-Step (No Custom Docker Images)

**Architecture:** 2 Docker Containers (pre-built) + Local Python  
**Time Estimate:** 4-6 hours for complete setup

---

## OVERVIEW

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           WHAT WE'RE BUILDING                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   DOCKER (2 containers)              LOCAL PYTHON                           │
│   ─────────────────────              ────────────────                       │
│   • Redpanda (Kafka)                 • Simulator                            │
│   • InfluxDB                         • Consumer                             │
│                                      • ML API                               │
│                                      • Dashboard                            │
│                                                                             │
│   DATA FLOW:                                                                │
│   CSV ──► Simulator ──► Redpanda ──► Consumer ──► InfluxDB ──► Dashboard   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# PHASE 1: PREREQUISITES
## Time: 15 minutes

### Step 1.1: Verify Docker Installed

Open terminal and run:
```
docker --version
```

Expected output: `Docker version 24.x.x` or similar

If not installed:
- Mac: Download Docker Desktop from docker.com
- Windows: Download Docker Desktop from docker.com
- Linux: `sudo apt install docker.io docker-compose`

### Step 1.2: Verify Python Installed

```
python --version
```

Expected output: `Python 3.10.x` or `Python 3.11.x`

If not installed:
- Download from python.org
- Or use: `brew install python` (Mac)

### Step 1.3: Verify Git Installed

```
git --version
```

If not installed:
- Mac: `brew install git`
- Windows: Download from git-scm.com
- Linux: `sudo apt install git`

---

# PHASE 2: PROJECT STRUCTURE
## Time: 10 minutes

### Step 2.1: Create Project Folder

```
mkdir sieis
cd sieis
```

### Step 2.2: Create Directory Structure

```
mkdir -p data/raw
mkdir -p data/processed
mkdir -p src/app/simulator
mkdir -p src/app/consumer
mkdir -p src/app/ml
mkdir -p src/dashboard/components
mkdir -p src/dashboard/utils
mkdir -p notebooks
mkdir -p tests
```

### Step 2.3: Verify Structure

```
ls -la
```

You should see:
```
sieis/
├── data/
│   ├── raw/
│   └── processed/
├── src/
│   ├── app/
│   │   ├── simulator/
│   │   ├── consumer/
│   │   └── ml/
│   └── dashboard/
│       ├── components/
│       └── utils/
├── notebooks/
└── tests/
```

---

# PHASE 3: DOWNLOAD DATA
## Time: 5 minutes

### Step 3.1: Download Intel Lab Dataset

```
cd data/raw
```

**Option A: Using wget**
```
wget https://db.csail.mit.edu/labdata/data.txt.gz
wget https://db.csail.mit.edu/labdata/mote_locs.txt
```

**Option B: Using curl**
```
curl -O https://db.csail.mit.edu/labdata/data.txt.gz
curl -O https://db.csail.mit.edu/labdata/mote_locs.txt
```

**Option C: Manual Download**
1. Open browser
2. Go to https://db.csail.mit.edu/labdata/labdata.html
3. Click download links
4. Move files to data/raw/

### Step 3.2: Extract Data

```
gunzip data.txt.gz
```

### Step 3.3: Verify Files

```
ls -la
```

You should see:
```
data.txt       (~150 MB)
mote_locs.txt  (~1 KB)
```

### Step 3.4: Go Back to Project Root

```
cd ../..
```

---

# PHASE 4: SETUP DOCKER INFRASTRUCTURE
## Time: 15 minutes

### Step 4.1: Create docker-compose.yml

Create file `docker-compose.yml` in project root:

```yaml
version: '3.8'

services:
  # CONTAINER 1: Message Queue (Kafka-compatible)
  redpanda:
    image: redpandadata/redpanda:latest
    container_name: sieis-redpanda
    command:
      - redpanda
      - start
      - --smp 1
      - --memory 512M
      - --overprovisioned
      - --kafka-addr PLAINTEXT://0.0.0.0:9092
      - --advertise-kafka-addr PLAINTEXT://localhost:9092
    ports:
      - "9092:9092"
      - "8080:8080"

  # CONTAINER 2: Time-Series Database
  influxdb:
    image: influxdb:2.7
    container_name: sieis-influxdb
    ports:
      - "8086:8086"
    environment:
      - DOCKER_INFLUXDB_INIT_MODE=setup
      - DOCKER_INFLUXDB_INIT_USERNAME=admin
      - DOCKER_INFLUXDB_INIT_PASSWORD=password123
      - DOCKER_INFLUXDB_INIT_ORG=sieis
      - DOCKER_INFLUXDB_INIT_BUCKET=sensor_data
      - DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=my-super-secret-token
    volumes:
      - influxdb_data:/var/lib/influxdb2

volumes:
  influxdb_data:
```

### Step 4.2: Start Docker Containers

```
docker-compose up -d
```

### Step 4.3: Verify Containers Running

```
docker ps
```

Expected output:
```
CONTAINER ID   IMAGE                      PORTS                    NAMES
xxxxxxxxxxxx   redpandadata/redpanda      0.0.0.0:9092->9092/tcp   sieis-redpanda
xxxxxxxxxxxx   influxdb:2.7               0.0.0.0:8086->8086/tcp   sieis-influxdb
```

### Step 4.4: Verify Redpanda

Open browser: http://localhost:8080

You should see Redpanda Console

### Step 4.5: Verify InfluxDB

Open browser: http://localhost:8086

Login with:
- Username: `admin`
- Password: `password123`

### Step 4.6: Create Kafka Topic

```
docker exec -it sieis-redpanda rpk topic create sensor_readings --partitions 6
```

### Step 4.7: Verify Topic Created

```
docker exec -it sieis-redpanda rpk topic list
```

Expected output:
```
NAME              PARTITIONS
sensor_readings   6
```

---

# PHASE 5: SETUP PYTHON ENVIRONMENT
## Time: 10 minutes

### Step 5.1: Create Virtual Environment

```
python -m venv venv
```

### Step 5.2: Activate Virtual Environment

**Mac/Linux:**
```
source venv/bin/activate
```

**Windows:**
```
venv\Scripts\activate
```

### Step 5.3: Verify Activated

Your prompt should show `(venv)`:
```
(venv) user@machine:~/sieis$
```

### Step 5.4: Create requirements.txt

Create file `requirements.txt`:

```
kafka-python==2.0.2
influxdb-client==1.38.0
pandas==2.1.0
scikit-learn==1.3.0
fastapi==0.103.0
uvicorn==0.23.0
streamlit==1.27.0
plotly==5.17.0
python-dotenv==1.0.0
requests==2.31.0
```

### Step 5.5: Install Packages

```
pip install -r requirements.txt
```

### Step 5.6: Verify Installation

```
pip list
```

You should see all packages installed.

---

# PHASE 6: CREATE CONFIGURATION
## Time: 5 minutes

### Step 6.1: Create .env File

Create file `.env` in project root:

```
# Kafka/Redpanda
KAFKA_BROKER=http://localhost:9092
KAFKA_TOPIC=sensor_readings

# InfluxDB
INFLUX_URL=http://localhost:8086
INFLUX_TOKEN=my-super-secret-token
INFLUX_ORG=sieis
INFLUX_BUCKET=sensor_data

# Simulator
SPEED_FACTOR=100
DATA_PATH=data/raw/data.txt
MOTE_LOCS_PATH=data/raw/mote_locs.txt

# ML API
ML_API_HOST=localhost
ML_API_PORT=8000
```

### Step 6.2: Create config.py

Create file `src/app/config.py`:

```python
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
```

---

# PHASE 7: BUILD DATA LOADER
## Time: 30 minutes

### Step 7.1: Create __init__.py Files

```
touch src/__init__.py
touch src/app/__init__.py
touch src/app/simulator/__init__.py
touch src/app/consumer/__init__.py
touch src/app/ml/__init__.py
touch src/dashboard/__init__.py
touch src/dashboard/components/__init__.py
touch src/dashboard/utils/__init__.py
```

### Step 7.2: Create Data Loader

Create file `src/app/simulator/data_loader.py`

**What it should do:**

1. **Load CSV File**
   - Read data.txt (no header)
   - Column names: date, time, epoch, moteid, temperature, humidity, light, voltage

2. **Parse Timestamps**
   - Combine date + time columns
   - Convert to datetime object

3. **Clean Data**
   - Drop rows where temperature is null
   - Drop rows where humidity is null
   - Fill null light with 0
   - Fill null voltage with forward fill

4. **Load Mote Locations**
   - Read mote_locs.txt
   - Columns: mote_id, x, y

5. **Split by Mote**
   - Group data by moteid
   - Sort each group by timestamp
   - Return dictionary: {mote_id: dataframe}

### Step 7.3: Test Data Loader

Create file `tests/test_data_loader.py`

**Test cases:**

1. File loads without error
2. Returns 54 mote groups (or less if some missing)
3. Each group is sorted by timestamp
4. No null values in temperature column
5. No null values in humidity column

### Step 7.4: Run Test

```
python -m pytest tests/test_data_loader.py -v
```

---

# PHASE 8: BUILD KAFKA PRODUCER
## Time: 20 minutes

### Step 8.1: Create Producer Module

Create file `src/app/simulator/producer.py`

**What it should do:**

1. **Initialize Producer**
   - Connect to Redpanda at localhost:9092
   - Set serializer for JSON

2. **Send Message**
   - Accept message dictionary
   - Convert to JSON
   - Send to topic with mote_id as key

3. **Handle Errors**
   - Retry on failure
   - Log errors

### Step 8.2: Test Producer

Create file `tests/test_producer.py`

**Test cases:**

1. Producer connects successfully
2. Can send single message
3. Message appears in Kafka topic

### Step 8.3: Run Test

```
python -m pytest tests/test_producer.py -v
```

### Step 8.4: Verify in Redpanda Console

1. Open http://localhost:8080
2. Click on "sensor_readings" topic
3. Check if test message appears

---

# PHASE 9: BUILD MOTE EMITTER
## Time: 30 minutes

### Step 9.1: Create Emitter Module

Create file `src/app/simulator/emitter.py`

**What it should do:**

1. **Accept Parameters**
   - mote_id
   - dataframe for this mote
   - kafka producer
   - speed_factor

2. **Loop Through Data**
   - Iterate rows in timestamp order
   - Calculate delay from previous row
   - Apply speed factor

3. **Build Message**
   ```
   {
     "mote_id": 23,
     "timestamp": "2024-01-15T14:32:15Z",
     "original_timestamp": "2004-03-01T14:32:15",
     "temperature": 22.5,
     "humidity": 45.2,
     "light": 350.0,
     "voltage": 2.8,
     "epoch": 1234
   }
   ```

4. **Send to Kafka**
   - Use producer to send message
   - Log success/failure

### Step 9.2: Test Emitter

**Manual test:**

1. Run emitter for single mote (mote_id=1)
2. Set speed_factor=1000 (very fast)
3. Watch Redpanda Console for messages

---

# PHASE 10: BUILD ORCHESTRATOR
## Time: 20 minutes

### Step 10.1: Create Orchestrator Module

Create file `src/app/simulator/orchestrator.py`

**What it should do:**

1. **Initialize**
   - Create Kafka producer
   - Load data using data_loader
   - Get list of mote IDs

2. **Create Threads**
   - One thread per mote
   - Each thread runs an emitter

3. **Start Simulation**
   - Start all threads
   - Log progress

4. **Handle Shutdown**
   - Catch Ctrl+C
   - Stop all threads gracefully
   - Close Kafka producer

### Step 10.2: Create Simulator Entry Point

Create file `src/app/simulator/main.py`

**What it should do:**

1. Load config
2. Create orchestrator
3. Start simulation
4. Wait for completion or Ctrl+C

---

# PHASE 11: BUILD CONSUMER
## Time: 30 minutes

### Step 11.1: Create Kafka Consumer Module

Create file `src/app/consumer/kafka_consumer.py`

**What it should do:**

1. **Connect to Kafka**
   - Subscribe to sensor_readings topic
   - Use consumer group: sieis-consumers

2. **Read Messages**
   - Poll for messages
   - Deserialize JSON

3. **Batch Messages**
   - Collect messages for 1 second or 100 messages
   - Pass batch to writer

### Step 11.2: Create InfluxDB Writer Module

Create file `src/app/consumer/influx_writer.py`

**What it should do:**

1. **Connect to InfluxDB**
   - Use token authentication
   - Select bucket: sensor_data

2. **Write Batch**
   - Convert messages to InfluxDB points
   - Measurement: sensor_reading
   - Tags: mote_id
   - Fields: temperature, humidity, light, voltage

3. **Handle Errors**
   - Retry on failure
   - Log errors

### Step 11.3: Create Consumer Entry Point

Create file `src/app/consumer/main.py`

**What it should do:**

1. Initialize Kafka consumer
2. Initialize InfluxDB writer
3. Run consumer loop
4. Handle shutdown

---

# PHASE 12: BUILD ML SERVICE
## Time: 30 minutes

### Step 12.1: Create ML Models Module

Create file `src/app/ml/models.py`

**What it should do:**

1. **Anomaly Detector**
   - Load pre-trained model (or train simple one)
   - Predict anomaly score for reading

2. **Comfort Predictor**
   - Calculate PMV score from temperature + humidity
   - Return comfort label

### Step 12.2: Create FastAPI Service

Create file `src/app/ml/api.py`

**Endpoints:**

| Endpoint | Method | Input | Output |
|----------|--------|-------|--------|
| /health | GET | None | {"status": "ok"} |
| /predict/anomaly | POST | SensorReading | {"is_anomaly": bool, "score": float} |
| /predict/comfort | POST | SensorReading | {"pmv": float, "label": string} |

### Step 12.3: Test API

```
uvicorn src.app.ml.api:app --reload --port 8000
```

Open http://localhost:8000/docs to see Swagger UI

---

# PHASE 13: CREATE MAIN ENTRY POINT
## Time: 15 minutes

### Step 13.1: Create Main Module

Create file `src/app/main.py`

**What it should do:**

1. Start Simulator in background thread
2. Start Consumer in background thread
3. Start ML API (main thread, blocking)

### Step 13.2: Test Main

```
python src/app/main.py
```

Expected behavior:
- Simulator starts emitting
- Consumer starts reading and writing
- ML API available at http://localhost:8000

---

# PHASE 14: BUILD DASHBOARD
## Time: 45 minutes

### Step 14.1: Create InfluxDB Client Utility

Create file `src/dashboard/utils/influx_client.py`

**What it should do:**

1. Connect to InfluxDB
2. Query latest readings
3. Query time range data
4. Return as DataFrame

### Step 14.2: Create KPI Cards Component

Create file `src/dashboard/components/kpi_cards.py`

**Metrics to show:**

| Metric | Query |
|--------|-------|
| Active Sensors | Count distinct mote_id in last 5 min |
| Anomalies | Count where is_anomaly = true |
| Avg Temperature | Mean temperature last 5 min |
| Alerts | Count alerts today |

### Step 14.3: Create Floor Map Component

Create file `src/dashboard/components/floor_map.py`

**What it should do:**

1. Load mote locations
2. Query latest temperature per mote
3. Create scatter plot with color = temperature

### Step 14.4: Create Trend Chart Component

Create file `src/dashboard/components/trend_chart.py`

**What it should do:**

1. Accept mote_id and time_range
2. Query InfluxDB for data
3. Create line chart

### Step 14.5: Create Alert Log Component

Create file `src/dashboard/components/alert_log.py`

**What it should do:**

1. Query recent alerts
2. Display as table with severity colors

### Step 14.6: Create Main Dashboard App

Create file `src/dashboard/app.py`

**Layout:**

```
┌─────────────────────────────────────────────────────────┐
│  SIEIS Dashboard                          [Auto-refresh]│
├─────────────────────────────────────────────────────────┤
│  [KPI Cards Row]                                        │
├─────────────────────────────────────────────────────────┤
│  [Floor Map]              │  [Controls]                 │
├─────────────────────────────────────────────────────────┤
│  [Trend Chart]                                          │
├─────────────────────────────────────────────────────────┤
│  [Alert Log]                                            │
└─────────────────────────────────────────────────────────┘
```

### Step 14.7: Test Dashboard

```
streamlit run src/dashboard/app.py
```

Open http://localhost:8501

---

# PHASE 15: END-TO-END TEST
## Time: 30 minutes

### Step 15.1: Start Infrastructure

```
docker-compose up -d
```

### Step 15.2: Verify Infrastructure

1. Check Redpanda: http://localhost:8080
2. Check InfluxDB: http://localhost:8086

### Step 15.3: Start Python App

**Terminal 1:**
```
source venv/bin/activate
python src/app/main.py
```

### Step 15.4: Start Dashboard

**Terminal 2:**
```
source venv/bin/activate
streamlit run src/dashboard/app.py
```

### Step 15.5: Verify Data Flow

1. **Check Kafka:**
   - Open Redpanda Console
   - See messages in sensor_readings topic

2. **Check InfluxDB:**
   - Open InfluxDB UI
   - Query sensor_data bucket
   - See data points

3. **Check Dashboard:**
   - Open http://localhost:8501
   - See KPI cards updating
   - See floor map with sensors
   - See trend charts

### Step 15.6: Test ML Predictions

```
curl http://localhost:8000/predict/anomaly \
  -H "Content-Type: application/json" \
  -d '{"mote_id": 1, "temperature": 25.0, "humidity": 50.0, "light": 100, "voltage": 2.8}'
```

---

# PHASE 16: CLEANUP & DOCUMENTATION
## Time: 15 minutes

### Step 16.1: Create README.md

```markdown
# SIEIS - Smart Indoor Environmental Intelligent System

## Quick Start

1. Start infrastructure:
   ```
   docker-compose up -d
   ```

2. Setup Python:
   ```
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Start app:
   ```
   python src/app/main.py
   ```

4. Start dashboard:
   ```
   streamlit run src/dashboard/app.py
   ```

5. Open http://localhost:8501
```

### Step 16.2: Create .gitignore

```
venv/
__pycache__/
*.pyc
.env
data/raw/data.txt
*.log
.DS_Store
```

### Step 16.3: Initialize Git

```
git init
git add .
git commit -m "Initial commit: SIEIS project"
```

---

# COMPLETE CHECKLIST

## Phase 1: Prerequisites ☐
- [ ] Docker installed
- [ ] Python installed
- [ ] Git installed

## Phase 2: Project Structure ☐
- [ ] Folders created

## Phase 3: Download Data ☐
- [ ] data.txt downloaded
- [ ] mote_locs.txt downloaded
- [ ] data.txt extracted

## Phase 4: Docker Infrastructure ☐
- [ ] docker-compose.yml created
- [ ] Containers running
- [ ] Redpanda accessible
- [ ] InfluxDB accessible
- [ ] Kafka topic created

## Phase 5: Python Environment ☐
- [ ] Virtual environment created
- [ ] Packages installed

## Phase 6: Configuration ☐
- [ ] .env file created
- [ ] config.py created

## Phase 7: Data Loader ☐
- [ ] data_loader.py created
- [ ] Tests passing

## Phase 8: Kafka Producer ☐
- [ ] producer.py created
- [ ] Tests passing

## Phase 9: Mote Emitter ☐
- [ ] emitter.py created
- [ ] Single mote test working

## Phase 10: Orchestrator ☐
- [ ] orchestrator.py created
- [ ] Multi-mote test working

## Phase 11: Consumer ☐
- [ ] kafka_consumer.py created
- [ ] influx_writer.py created
- [ ] Data appearing in InfluxDB

## Phase 12: ML Service ☐
- [ ] models.py created
- [ ] api.py created
- [ ] API responding

## Phase 13: Main Entry Point ☐
- [ ] main.py created
- [ ] All services starting

## Phase 14: Dashboard ☐
- [ ] Components created
- [ ] app.py created
- [ ] Dashboard rendering

## Phase 15: End-to-End Test ☐
- [ ] Full pipeline working
- [ ] Data flowing
- [ ] Dashboard updating

## Phase 16: Documentation ☐
- [ ] README.md created
- [ ] Git initialized

---

# QUICK REFERENCE

## Start Everything

```bash
# Terminal 1: Infrastructure
docker-compose up -d

# Terminal 2: Python App
source venv/bin/activate
python src/app/main.py

# Terminal 3: Dashboard
source venv/bin/activate
streamlit run src/dashboard/app.py
```

## Stop Everything

```bash
# Stop Python apps
Ctrl+C (in each terminal)

# Stop Docker
docker-compose down
```

## URLs

| Service | URL |
|---------|-----|
| Redpanda Console | http://localhost:8080 |
| InfluxDB UI | http://localhost:8086 |
| ML API Docs | http://localhost:8000/docs |
| Dashboard | http://localhost:8501 |

---

## TOTAL TIME: ~5 hours

| Phase | Time |
|-------|------|
| Prerequisites | 15 min |
| Project Structure | 10 min |
| Download Data | 5 min |
| Docker Setup | 15 min |
| Python Setup | 10 min |
| Configuration | 5 min |
| Data Loader | 30 min |
| Kafka Producer | 20 min |
| Mote Emitter | 30 min |
| Orchestrator | 20 min |
| Consumer | 30 min |
| ML Service | 30 min |
| Main Entry | 15 min |
| Dashboard | 45 min |
| E2E Test | 30 min |
| Documentation | 15 min |
| **TOTAL** | **~5 hours** |