# End-to-End Testing Guide

## 📋 Overview

Test the complete SIEIS pipeline: **Simulator → Kafka → Consumer → InfluxDB**

## 🚀 Quick Start (Recommended)

Run everything with a single command:

```powershell
python run_full_test.py
```

This will:
1. Check Docker containers are running
2. Verify configuration (InfluxDB & Kafka connectivity)
3. Run the full end-to-end test
4. Display results

---

## 🔧 Manual Testing (Step by Step)

### **Step 1: Start Docker Infrastructure**

```powershell
# Start containers
docker-compose up -d

# Wait for services to initialize
timeout /t 10

# Verify containers
docker ps | findstr sieis
```

Expected output:
```
sieis-redpanda     Up 10 seconds
sieis-influxdb     Up 10 seconds
```

---

### **Step 2: Configuration Check**

```powershell
python tests\test_config_check.py
```

This verifies:
- ✅ InfluxDB is reachable
- ✅ Kafka is reachable  
- ✅ Data files exist
- ✅ Configuration loaded correctly

Expected output:
```
✅ ALL CHECKS PASSED - Ready to run end-to-end test!
```

---

### **Step 3: Run End-to-End Test**

```powershell
python tests\test_end_to_end.py
```

This will:
1. Start simulator (produces data to Kafka)
2. Start consumer (reads from Kafka, writes to InfluxDB)
3. Wait 15 seconds for data flow
4. Query InfluxDB to verify data exists
5. Assert data integrity

Expected output:
```
✅ END-TO-END TEST PASSED!

📈 Pipeline Status:
   • Simulator → Kafka: ✅ Working
   • Kafka → Consumer: ✅ Working
   • Consumer → InfluxDB: ✅ Working
   • Data Verification: ✅ Passed
```

---

## 🧪 Using Pytest

Run with pytest for detailed test reporting:

```powershell
# Run just the end-to-end test
pytest tests\test_end_to_end.py -v

# Run with output visible
pytest tests\test_end_to_end.py -v -s

# Run all integration tests
pytest tests\ -m integration -v
```

---

## 🔍 Verification (After Test)

### **Check Kafka Topic**

```powershell
docker exec -it sieis-redpanda rpk topic describe sensor_readings
```

### **Check InfluxDB Data**

Open browser: http://localhost:8086
- Login: `admin` / `password123`
- Go to "Data Explorer"
- Select bucket: `sensor_data`
- Select measurement: `sensor_reading`

### **View Redpanda Console**

Open browser: http://localhost:8080
- Go to "Topics" → "sensor_readings"
- See messages flowing

---

## 🐛 Troubleshooting

### **Containers not running**

```powershell
docker-compose down
docker-compose up -d
timeout /t 10
```

### **Kafka connection failed**

```powershell
# Check Redpanda is healthy
docker logs sieis-redpanda | findstr "ready"

# Recreate topic
docker exec -it sieis-redpanda rpk topic delete sensor_readings
docker exec -it sieis-redpanda rpk topic create sensor_readings --partitions 6
```

### **InfluxDB connection failed**

```powershell
# Check InfluxDB is healthy
docker logs sieis-influxdb | findstr "Listening"

# Restart container
docker restart sieis-influxdb
timeout /t 10
```

### **No data in InfluxDB**

```powershell
# Check consumer is writing
python -c "from src.app.consumer.main import ConsumerService; c=ConsumerService(); c.start()"

# Check InfluxDB bucket
curl -X GET http://localhost:8086/api/v2/buckets `
  -H "Authorization: Token my-super-secret-token"
```

---

## 📊 Test Files

| File | Purpose |
|------|---------|
| `run_full_test.py` | **Recommended** - Runs all checks automatically |
| `tests/test_config_check.py` | Verify configuration and connectivity |
| `tests/test_end_to_end.py` | Full pipeline test (standalone or pytest) |
| `tests/test_data_loader.py` | Unit tests for data loader |
| `tests/test_producer.py` | Unit tests for Kafka producer |
| `tests/test_orchestrator.py` | Unit tests for orchestrator |

---

## ✅ Success Criteria

Your pipeline is working if:

1. ✅ Docker containers are `Up` status
2. ✅ Config check passes all tests
3. ✅ End-to-end test finds 10+ data points
4. ✅ Data from multiple motes (2+)
5. ✅ All sensor fields present (temperature, humidity, light, voltage)

---

## 🎯 Next Steps

After tests pass:
1. ✅ Implement ML service (Phase 12)
2. ✅ Create main entry point (Phase 13)
3. ✅ Build Streamlit dashboard (Phase 14)
