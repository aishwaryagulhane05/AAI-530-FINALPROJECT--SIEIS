# InfluxDB Query Documentation

A collection of useful InfluxDB Flux queries for SIEIS sensor data analysis.

**Database Configuration:**
- URL: `http://localhost:8086`
- Token: `my-super-secret-token`
- Organization: `sieis`
- Bucket: `sensor_data`
- Measurement: `sensor_reading`

---

## 📊 Data Retrieval Queries

### 1. Count Total Records in InfluxDB

**Purpose:** Get the total count of all sensor readings stored in InfluxDB.

```flux
from(bucket: "sensor_data")
  |> range(start: 0)
  |> group()
  |> count()
```

**Returns:** Single value representing total number of records.

---

### 2. Count Records by Date

**Purpose:** Get count of records grouped by date.

```flux
from(bucket: "sensor_data")
  |> range(start: 2010-01-01T00:00:00Z, stop: 2010-12-31T23:59:59Z)
  |> group(columns: ["_time"])
  |> count()
  |> group()
```

---

### 3. Get All Sensor Data for Year 2010

**Purpose:** Retrieve all sensor readings from 2010.

```flux
from(bucket: "sensor_data")
  |> range(start: 2010-01-01T00:00:00Z, stop: 2010-12-31T23:59:59Z)
  |> filter(fn: (r) => r._measurement == "sensor_reading")
```

---

### 4. Get Latest 100 Records

**Purpose:** Retrieve the most recent 100 sensor readings.

```flux
from(bucket: "sensor_data")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "sensor_reading")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 100)
```

---

## 🎯 Per-Mote Analysis

### 5. Count Records by Mote ID

**Purpose:** See how many records each mote has.

```flux
from(bucket: "sensor_data")
  |> range(start: 0)
  |> filter(fn: (r) => r._measurement == "sensor_reading")
  |> group(columns: ["mote_id"])
  |> count()
```

---

### 6. Get Data for Specific Mote

**Purpose:** Retrieve all readings from mote ID 23.

```flux
from(bucket: "sensor_data")
  |> range(start: 2010-01-01T00:00:00Z, stop: 2010-12-31T23:59:59Z)
  |> filter(fn: (r) => r._measurement == "sensor_reading" and r.mote_id == "23")
```

---

### 7. Get Data for Multiple Motes

**Purpose:** Retrieve readings from motes 15, 23, and 42.

```flux
from(bucket: "sensor_data")
  |> range(start: 2010-01-01T00:00:00Z, stop: 2010-12-31T23:59:59Z)
  |> filter(fn: (r) => r._measurement == "sensor_reading" and (r.mote_id == "15" or r.mote_id == "23" or r.mote_id == "42"))
```

---

## 📈 Statistics & Aggregation

### 8. Average Temperature Per Mote

**Purpose:** Calculate average temperature for each mote.

```flux
from(bucket: "sensor_data")
  |> range(start: 2010-01-01T00:00:00Z, stop: 2010-12-31T23:59:59Z)
  |> filter(fn: (r) => r._measurement == "sensor_reading" and r._field == "temperature")
  |> group(columns: ["mote_id"])
  |> mean()
```

---

### 9. Min/Max/Mean for All Measurements

**Purpose:** Get summary statistics for temperature, humidity, light, and voltage.

```flux
from(bucket: "sensor_data")
  |> range(start: 2010-01-01T00:00:00Z, stop: 2010-12-31T23:59:59Z)
  |> filter(fn: (r) => r._measurement == "sensor_reading")
  |> group(columns: ["_field"])
  |> stats()
```

---

### 10. Hourly Average Temperature

**Purpose:** Get average temperature for each hour.

```flux
from(bucket: "sensor_data")
  |> range(start: 2010-01-01T00:00:00Z, stop: 2010-12-31T23:59:59Z)
  |> filter(fn: (r) => r._measurement == "sensor_reading" and r._field == "temperature")
  |> aggregateWindow(every: 1h, fn: mean)
```

---

### 11. Daily Max Temperature

**Purpose:** Get maximum temperature for each day.

```flux
from(bucket: "sensor_data")
  |> range(start: 2010-01-01T00:00:00Z, stop: 2010-12-31T23:59:59Z)
  |> filter(fn: (r) => r._measurement == "sensor_reading" and r._field == "temperature")
  |> aggregateWindow(every: 1d, fn: max)
```

---

## 🔍 Filtering & Search

### 12. Get Temperature Readings Above Threshold

**Purpose:** Find all temperature readings above 25°C.

```flux
from(bucket: "sensor_data")
  |> range(start: 2010-01-01T00:00:00Z, stop: 2010-12-31T23:59:59Z)
  |> filter(fn: (r) => r._measurement == "sensor_reading" and r._field == "temperature" and r._value > 25.0)
```

---

### 13. Get Humidity Readings Below Threshold

**Purpose:** Find all humidity readings below 30%.

```flux
from(bucket: "sensor_data")
  |> range(start: 2010-01-01T00:00:00Z, stop: 2010-12-31T23:59:59Z)
  |> filter(fn: (r) => r._measurement == "sensor_reading" and r._field == "humidity" and r._value < 30.0)
```

---

### 14. Get Voltage Anomalies

**Purpose:** Find voltage readings outside normal range (2.5V - 3.3V).

```flux
from(bucket: "sensor_data")
  |> range(start: 2010-01-01T00:00:00Z, stop: 2010-12-31T23:59:59Z)
  |> filter(fn: (r) => r._measurement == "sensor_reading" and r._field == "voltage" and (r._value < 2.5 or r._value > 3.3))
```

---

## 📊 Time Series Analysis

### 15. Get Data Between Two Timestamps

**Purpose:** Retrieve data from March 1-15, 2010.

```flux
from(bucket: "sensor_data")
  |> range(start: 2010-03-01T00:00:00Z, stop: 2010-03-15T23:59:59Z)
  |> filter(fn: (r) => r._measurement == "sensor_reading")
```

---

### 16. Get Last Hour of Data

**Purpose:** Retrieve the most recent 1 hour of data.

```flux
from(bucket: "sensor_data")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "sensor_reading")
```

---

### 17. Get Last 7 Days of Data

**Purpose:** Retrieve the most recent 7 days of data.

```flux
from(bucket: "sensor_data")
  |> range(start: -7d)
  |> filter(fn: (r) => r._measurement == "sensor_reading")
```

---

## 🎛️ Advanced Queries

### 18. Compare Temperature Across Two Time Periods

**Purpose:** Compare average temperature in January vs February 2010.

```flux
union(
  tables: [
    from(bucket: "sensor_data")
      |> range(start: 2010-01-01T00:00:00Z, stop: 2010-01-31T23:59:59Z)
      |> filter(fn: (r) => r._measurement == "sensor_reading" and r._field == "temperature")
      |> mean()
      |> map(fn: (r) => ({r with period: "January"})),
    from(bucket: "sensor_data")
      |> range(start: 2010-02-01T00:00:00Z, stop: 2010-02-28T23:59:59Z)
      |> filter(fn: (r) => r._measurement == "sensor_reading" and r._field == "temperature")
      |> mean()
      |> map(fn: (r) => ({r with period: "February"}))
  ]
)
```

---

### 19. Find Motes with Missing Data

**Purpose:** Identify motes with fewer than 1000 records.

```flux
from(bucket: "sensor_data")
  |> range(start: 0)
  |> filter(fn: (r) => r._measurement == "sensor_reading")
  |> group(columns: ["mote_id"])
  |> count()
  |> filter(fn: (r) => r._value < 1000)
```

---

### 20. Calculate Standard Deviation of Temperature

**Purpose:** Get temperature variability for each mote.

```flux
from(bucket: "sensor_data")
  |> range(start: 2010-01-01T00:00:00Z, stop: 2010-12-31T23:59:59Z)
  |> filter(fn: (r) => r._measurement == "sensor_reading" and r._field == "temperature")
  |> group(columns: ["mote_id"])
  |> stdDev()
```

---

## 🔧 Maintenance Queries

### 21. Count Unique Motes

**Purpose:** Find total number of unique sensor motes.

```flux
from(bucket: "sensor_data")
  |> range(start: 0)
  |> filter(fn: (r) => r._measurement == "sensor_reading")
  |> group(columns: ["mote_id"])
  |> count()
  |> group()
  |> count()
```

---

### 22. Get Data Quality Metrics

**Purpose:** Count null/missing values by field.

```flux
from(bucket: "sensor_data")
  |> range(start: 2010-01-01T00:00:00Z, stop: 2010-12-31T23:59:59Z)
  |> filter(fn: (r) => r._measurement == "sensor_reading")
  |> group(columns: ["_field"])
  |> count()
  |> map(fn: (r) => ({r with field: r._field, record_count: r._value}))
```

---

### 23. Check Data Freshness

**Purpose:** Get timestamp of most recent data point.

```flux
from(bucket: "sensor_data")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "sensor_reading")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 1)
  |> map(fn: (r) => ({latest_timestamp: r._time}))
```

---

## 📝 Usage in Python

### Example: Running Query in Python

```python
from influxdb_client import InfluxDBClient

# Connect to InfluxDB
client = InfluxDBClient(
    url="http://localhost:8086",
    token="my-super-secret-token",
    org="sieis"
)

query_api = client.query_api()

# Define query (use any query from above)
query = """
from(bucket: "sensor_data")
  |> range(start: 0)
  |> group()
  |> count()
"""

# Execute query
result = query_api.query(org="sieis", query=query)

# Print results
for table in result:
    for record in table.records:
        print(f"Total records: {record.get_value()}")

client.close()
```

---

## 📚 Query Tips

| Tip | Example |
|-----|---------|
| **Relative time ranges** | `start: -7d`, `start: -1h`, `start: -30m` |
| **Absolute time ranges** | `start: 2010-01-01T00:00:00Z` |
| **Group by tags** | `group(columns: ["mote_id", "tag_name"])` |
| **Filter multiple conditions** | `filter(fn: (r) => r._measurement == "x" and r._field == "y")` |
| **Sort ascending/descending** | `sort(columns: ["_time"], desc: true)` |
| **Limit results** | `limit(n: 100)` |
| **Aggregate windows** | `aggregateWindow(every: 1h, fn: mean)` |

---

**Last Updated:** February 15, 2026  
**Version:** 1.0
