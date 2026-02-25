# SIEIS Scheduler — Testing Guide

> How to verify the full daily automation pipeline without waiting until midnight.

---

## 0. Rollback Instructions (Before You Start)

If anything goes wrong, restore to the exact pre-scheduler state:

```powershell
# Full rollback — removes ALL scheduler files and reverts docker-compose + requirements
git checkout checkpoint/pre-scheduler -- docker-compose.yml requirements.txt
git clean -fd src/app/scheduler/   # removes the new scheduler/ package
git clean -f Dockerfile.scheduler  # removes Dockerfile

# Verify clean state
git status
# Expected: working tree clean (scheduler files gone)
```

To completely list what the checkpoint contained:
```powershell
git show checkpoint/pre-scheduler --stat
```

---

## 1. What Was Added

| File | Purpose |
|---|---|
| `src/app/scheduler/__init__.py` | Package marker |
| `src/app/scheduler/jobs.py` | Job A (remap + restart) and Job B (retrain + reload) |
| `src/app/scheduler/main.py` | APScheduler entry point with cron triggers |
| `Dockerfile.scheduler` | Container image definition |
| `docker-compose.yml` | New `scheduler` service added |
| `requirements.txt` | `APScheduler==3.10.4` and `docker>=6.1.0` added |

---

## 2. Test Strategy Overview

Think of testing like a film set rehearsal — you run the scene at normal speed before
the real performance. The scheduler has a `RUN_JOBS_ON_START` flag that triggers both
jobs immediately so you never have to wait for midnight.

**Three levels of testing:**

| Level | What It Tests | Time Needed |
|---|---|---|
| Unit | Each job function in isolation | 2–5 min |
| Integration | Full job with live Docker services | 5–15 min |
| End-to-End | Full pipeline with scheduler container | 15–30 min |

---

## 3. Level 1 — Unit Test Each Job Individually

Run these from the project root on your Windows host (venv activated):

### Test Job A: Remap timestamps

```powershell
# Dry run first — no file changes, just preview
.\venv\Scripts\python.exe scripts/remap_timestamps.py --incr-only --dry-run

# Expected output:
# Unique original dates : N
# Mapping preview:
#   2004-03-XX  →  2026-02-25   ← today's date
#   ...
# DRY RUN — no file written.

# Real run (modifies incremental_data.txt)
.\venv\Scripts\python.exe scripts/remap_timestamps.py --incr-only

# Verify the file changed
.\venv\Scripts\python.exe -c "
import pandas as pd
df = pd.read_csv('data/processed/incremental_data.txt', sep='\s+', header=None,
                 names=['date','time','epoch','moteid','temp','hum','light','volt','updated_ts'],
                 nrows=5)
print(df['updated_ts'].values)
# Should show today's date (2026-02-25) in the updated_ts column
"
```

### Test Job B: Retrain model

```powershell
# Retrain from MinIO (requires Docker services running)
.\venv\Scripts\python.exe scripts/retrain_model.py --source minio

# Expected output:
# [1/4] Loading data...
# [2/4] Preparing features...   Feature matrix: (N, 6)
# [3/4] Training new model version...
# [4/4] Saving new model version...
# New model: anomaly_detector_YYYYMMDD_HHMMSS_retrain.pkl

# Verify new model appears in registry
.\venv\Scripts\python.exe -c "
import json
with open('src/app/ml/models/model_registry.json') as f:
    r = json.load(f)
print('Latest:', r['latest'])
print('Total models:', len(r['models']))
"

# Test API reload (requires sieis-api running on localhost:8000)
curl -X POST http://localhost:8000/api/v1/ml/model/reload
# Expected: {"reloaded": true, "model_loaded": true, "model_path": "..."}
```

---

## 4. Level 2 — Test Job Functions Directly in Python

This bypasses the scheduler and calls job functions directly — fastest way to catch import errors:

```powershell
.\venv\Scripts\python.exe -c "
import sys
sys.path.insert(0, '.')

# Test Job A function
from src.app.scheduler.jobs import remap_and_restart
print('Testing Job A...')
remap_and_restart()
print('Job A done')
"

.\venv\Scripts\python.exe -c "
import sys
sys.path.insert(0, '.')

# Test Job B function
from src.app.scheduler.jobs import retrain_and_reload
print('Testing Job B...')
retrain_and_reload()
print('Job B done')
"
```

---

## 5. Level 3 — End-to-End with Scheduler Container

### 5a. Build the scheduler image

```powershell
docker-compose build scheduler
# Expected: Successfully built <image_id>
# Expected: Successfully tagged sieis-scheduler:latest
```

### 5b. Smoke-test with RUN_JOBS_ON_START=true

This fires both jobs immediately when the container starts — no waiting for midnight:

```powershell
# Start all services first
docker-compose up -d

# Wait for API to be healthy
docker-compose ps
# All services should show "Up (healthy)"

# Run scheduler with immediate job execution
docker-compose run --rm \
  -e RUN_JOBS_ON_START=true \
  scheduler

# Watch logs in real time — you should see:
# JOB A: Daily Data Refresh starting
# [1/2] Remapping incremental timestamps
# [2/2] Restarting simulator container 'sieis-simulator'
# JOB A complete — Simulator restart: SUCCESS
# ...
# JOB B: Daily Model Retrain starting
# [1/4] Loading Parquet data from MinIO...
# [2/4] Preparing feature matrix...
# [3/4] Training IsolationForest...
# [4/4] Reloading API model...
# JOB B complete — API reload: SUCCESS
```

### 5c. Start scheduler in normal (production) mode

```powershell
docker-compose up -d scheduler
docker-compose logs -f scheduler

# Expected output when it's waiting:
# SIEIS Scheduler starting
#   Timezone : UTC
#   Job A    : 00:00  remap_and_restart
#   Job B    : 02:00  retrain_and_reload
#   Immediate: False
# Scheduler running. Next runs:
```

### 5d. Verify next-run times

```powershell
docker exec sieis-scheduler python -c "
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
s = BackgroundScheduler(timezone='UTC')
s.add_job(lambda: None, CronTrigger(hour=0, minute=0), id='job_a')
s.add_job(lambda: None, CronTrigger(hour=2, minute=0), id='job_b')
s.start()
for job in s.get_jobs():
    print(f'{job.id}: next run = {job.next_run_time}')
s.shutdown()
"
```

---

## 6. Verify Each Step of the Pipeline

After running the smoke-test, confirm data flowed correctly:

### Check InfluxDB received today's data

```powershell
# Via InfluxDB UI: http://localhost:8086
# Login: admin / password123
# Query (Flux):
# from(bucket: "sensor_data")
#   |> range(start: -1h)
#   |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
#   |> count()

# Via CLI:
docker exec sieis-influxdb3 influx query '
from(bucket: "sensor_data")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
  |> count()
' --token my-super-secret-token --org sieis
```

### Check MinIO has new Parquet files

```powershell
# Via MinIO Console: http://localhost:9001
# Login: minioadmin / minioadmin123
# Navigate to: sieis-archive → year=2026 → month=02 → day=25

# Via CLI:
docker exec sieis-minio mc ls myminio/sieis-archive/year=2026/month=02/day=25/ --recursive
```

### Check new model in registry

```powershell
cat src/app/ml/models/model_registry.json
# Expected: "latest" points to a *_scheduled.pkl file with today's timestamp
```

### Check API uses new model

```powershell
curl http://localhost:8000/api/v1/ml/model/info
# Expected: "model_loaded": true, "model_path" contains today's timestamp

# Run a test prediction
curl -X POST http://localhost:8000/api/v1/ml/predict/anomaly \
  -H "Content-Type: application/json" \
  -d '{"mote_id": 1, "temperature": 22.5, "humidity": 45.0, "light": 200.0, "voltage": 2.7}'
# Expected: {"anomaly_score": ..., "is_anomaly": false/true, "severity": "normal/warning/critical"}
```

---

## 7. Adjust Schedule Times (Optional)

To run Job A at 6 AM and Job B at 8 AM instead of midnight, edit `docker-compose.yml`:

```yaml
scheduler:
  environment:
    - JOB_A_HOUR=6
    - JOB_A_MINUTE=0
    - JOB_B_HOUR=8
    - JOB_B_MINUTE=0
```

Then restart: `docker-compose restart scheduler`

---

## 8. View Scheduler Logs

```powershell
# Live tail
docker-compose logs -f scheduler

# Last 50 lines
docker-compose logs --tail=50 scheduler

# Grep for job outcomes
docker-compose logs scheduler | grep "JOB SUCCESS\|JOB FAILED\|JOB A\|JOB B"
```

---

## 9. Rollback If Something Goes Wrong

```powershell
# Option 1: Stop scheduler only (keep everything else running)
docker-compose stop scheduler
docker-compose rm -f scheduler

# Option 2: Full rollback to pre-scheduler state
docker-compose down
git checkout checkpoint/pre-scheduler -- docker-compose.yml requirements.txt
git clean -fd src/app/scheduler/
git clean -f Dockerfile.scheduler
docker-compose up -d
# System is back to exactly pre-scheduler state

# Option 3: Revert only the model (if retrain produced a bad model)
# Edit src/app/ml/models/model_registry.json
# Change "latest" to the previous .pkl filename
# Then: curl -X POST http://localhost:8000/api/v1/ml/model/reload
```

---

## 10. Quick Reference

```powershell
# Build scheduler image
docker-compose build scheduler

# Start all services including scheduler
docker-compose up -d

# Smoke-test both jobs immediately
docker-compose run --rm -e RUN_JOBS_ON_START=true scheduler

# Watch scheduler logs
docker-compose logs -f scheduler

# Trigger Job A manually (remap + restart)
docker exec sieis-scheduler python -c "
from src.app.scheduler.jobs import remap_and_restart; remap_and_restart()
"

# Trigger Job B manually (retrain + reload)
docker exec sieis-scheduler python -c "
from src.app.scheduler.jobs import retrain_and_reload; retrain_and_reload()
"

# Rollback everything
git checkout checkpoint/pre-scheduler -- docker-compose.yml requirements.txt
git clean -fd src/app/scheduler/ && git clean -f Dockerfile.scheduler
```
