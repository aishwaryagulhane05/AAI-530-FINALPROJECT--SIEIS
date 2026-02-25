# SIEIS Quick Start

Run the full SIEIS stack (Kafka + Consumer + InfluxDB + MinIO + API + Dashboard + Scheduler) in about 10 minutes.

## 1. Prerequisites

- Docker Desktop running
- Python 3.11+ (optional, for utility scripts)
- Git

## 2. Required Data Files

Confirm these files exist:

- `data/raw/mote_locs.txt`
- `data/processed/incremental_data.txt`
- `data/processed/historical_data.txt`

If missing, regenerate with project scripts under `data/realtime_mapping/` and `scripts/`.

## 3. Start the Full Stack

From project root:

```powershell
docker-compose up --build -d
```

Check containers:

```powershell
docker ps --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"
```

Expected key containers:

- `sieis-redpanda`
- `sieis-console`
- `sieis-influxdb3`
- `sieis-minio`
- `sieis-minio-init`
- `sieis-simulator`
- `sieis-consumer`
- `sieis-api`
- `sieis-dashboard`
- `sieis-scheduler`

## 4. Verify Services Manually

### 4.1 Core health checks

```powershell
docker exec sieis-redpanda rpk cluster info
curl http://localhost:8086/health
curl http://localhost:9000/minio/health/live
curl http://localhost:8000/api/v1/health
```

### 4.2 Web consoles

- Redpanda Console: `http://localhost:8080`
- InfluxDB UI: `http://localhost:8086`
- MinIO Console: `http://localhost:9001`
- Dashboard: `http://localhost:8501`
- API docs: `http://localhost:8000/docs`

### 4.3 Login credentials

- InfluxDB
  - Username: `admin`
  - Password: `password123`
  - Org: `sieis`
  - Bucket: `sensor_data`
  - Token: `my-super-secret-token`
- MinIO
  - Username: `minioadmin`
  - Password: `minioadmin123`
  - Bucket: `sieis-archive`

## 5. Verify Streaming and Storage

Consume sample Kafka messages:

```powershell
docker exec sieis-redpanda rpk topic consume sensor_readings --num 5
```

Optional validation scripts:

```powershell
python scripts/verify_influxDb.py
python scripts/verify_minio_storage.py
```

## 6. ML Quick Check (Optional)

Train anomaly model manually:

```powershell
python scripts/train_model.py --source minio
```

Confirm model is loaded:

```powershell
curl http://localhost:8000/api/v1/ml/model/info
```

## 7. Scheduler Quick Check (Optional)

Run scheduler jobs immediately for smoke testing:

```powershell
docker compose down scheduler
RUN_JOBS_ON_START=true docker compose up scheduler
```

Default schedule (UTC):

- Job A `00:00`: restart simulator
- Job B `02:00`: retrain model and reload API model

## 8. Stop or Reset

Stop all services:

```powershell
docker-compose down
```

Stop and delete volumes (destructive reset):

```powershell
docker-compose down -v
```

## 9. Troubleshooting

- No dashboard data:
  - `docker logs sieis-consumer`
  - `docker logs sieis-simulator`
- API health degraded:
  - confirm InfluxDB reachable on `8086`
- MinIO empty:
  - check `sieis-minio-init` logs and bucket `sieis-archive`
- Scheduler not acting:
  - `docker logs sieis-scheduler --tail 200`
