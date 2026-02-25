# Real-Time Data Mapping Scripts

This folder contains scripts to transform historical sensor data (2004) into real-time relevant timestamps (2026).

## Strategy

Maps the date range proportionally with an 80% anchor point:
- The date at 80% of the original range → Today's date
- All other dates map proportionally backwards
- Future dates are filtered out

**Example:**
- Original: 2004-02-28 to 2004-05-01 (63 days)
- 80% point: 2004-04-18 → 2026-02-16 (today)
- 2004-02-28 → 2026-01-28 (19 days ago)
- 2004-04-17 → 2026-02-15 (yesterday)

## Scripts

### 1. `preview_mapping.py`
Preview the date mapping before transformation.

```bash
python data/realtime_mapping/preview_mapping.py
```

**Output:** Shows how each original date will map to new dates.

### 2. `transform_to_realtime.py`
Main transformation script that creates the real-time data file.

```bash
python data/realtime_mapping/transform_to_realtime.py
```

**Input:** `data/data.csv` (original)  
**Output:** 
- `data/data_realtime.csv` (CSV format with headers)
- `data/processed/realtime_data.txt` (Space-delimited format, no headers)

### 3. `validate_output.py`
Validates the transformed data file.

```bash
python data/realtime_mapping/validate_output.py
```

**Checks:**
- Date distribution
- Timestamp consistency
- No future dates
- Record counts

## Usage Workflow

```bash
# Step 1: Preview the mapping (optional)
python data/realtime_mapping/preview_mapping.py

# Step 2: Transform the data
python data/realtime_mapping/transform_to_realtime.py

# Step 3: Validate output (optional)
python data/realtime_mapping/validate_output.py

# Step 4: Update docker-compose.yml
# Change simulator volume from:
#   - ./data/data.csv:/data/data.csv:ro
# To:
#   - ./data/data_realtime.csv:/data/data.csv:ro

# Step 5: Restart containers
docker-compose restart simulator consumer

# Step 6: Run tests
python tests/test_full_pipeline.py
```

## Output Formats

### CSV Format (`data/data_realtime.csv`)
Standard CSV with headers:
```csv
date,time,epoch,moteid,temperature,humidity,light,voltage,updated_timestamp
2004-02-28,00:59:16.02785,3,1,19.9884,37.0933,45.08,2.69964,2026-01-17T00:59:16.027850
```

**Columns:**
- `date`: Original date from 2004
- `time`: Original time of day
- `epoch`: Epoch/batch number
- `moteid`: Sensor/mote identifier
- `temperature`: Temperature reading (°C)
- `humidity`: Humidity reading (%)
- `light`: Light reading (lux)
- `voltage`: Battery voltage (V)
- `updated_timestamp`: **New** - Mapped timestamp in 2026 (ISO 8601 format)

### TXT Format (`data/processed/realtime_data.txt`)
Space-delimited, no headers (for legacy systems):
```
2004-02-28 00:59:16.02785 3 1 19.9884 37.0933 45.08 2.69964 2026-01-17T00:59:16.027850
```

**Column order:**
1. date (original)
2. time (original)
3. epoch
4. moteid
5. temperature
6. humidity
7. light
8. voltage
9. updated_timestamp (mapped to 2026)

## Transformation Details

### Date Mapping Algorithm

1. **Analyze original dataset:**
   - Find min date, max date, total span
   - Calculate 80% point (day 50 of 63 = 2004-04-18)

2. **Create proportional mapping:**
   - Anchor: Date at 80% → Today
   - All dates map relative to this anchor
   - Preserves time-of-day from original timestamps

3. **Filter future dates:**
   - Any timestamp > now() is excluded
   - Prevents InfluxDB rejection (can't write future data)

### Example Transformation

```
Original Range: 2004-02-28 to 2004-05-01 (63 days)
Current Date: 2026-02-16

Mapping:
├─ 2004-02-28 → 2026-01-28 (19 days ago) ← Oldest
├─ 2004-03-15 → 2026-02-02 (14 days ago)
├─ 2004-04-17 → 2026-02-15 (1 day ago)
├─ 2004-04-18 → 2026-02-16 (TODAY) ⭐ 80% anchor
├─ 2004-04-19 → 2026-02-17 (FUTURE - filtered out)
└─ 2004-05-01 → 2026-03-01 (FUTURE - filtered out) ← Newest
```

## Statistics from Last Run

```
📊 Original Dataset:
   Records: 2,313,682
   Date Range: 2004-02-28 to 2004-05-01
   Unique Dates: 63
   80% Point: 2004-04-18

✅ Transformation Results:
   Mapped Records: 1,823,589 (78.8%)
   Filtered (future): 490,093 (21.2%)
   
📈 Distribution:
   Today: 856,234 records (47.0%)
   Historical (1-30 days ago): 967,355 records (53.0%)
```

## File Locations

```
data/
├── data.csv                          # Original (untouched)
├── data_realtime.csv                 # Transformed CSV
└── processed/
    └── realtime_data.txt             # Transformed TXT (space-delimited)

data/realtime_mapping/
├── README.md                         # This file
├── preview_mapping.py                # Preview script
├── transform_to_realtime.py          # Main transformation
└── validate_output.py                # Validation script
```

## Integration with SIEIS Pipeline

### Before Transformation
```
CSV (2004 dates) → Simulator → Kafka → Consumer → InfluxDB ❌ (rejected)
                                                  → MinIO ✅ (works)
```

**Issue:** InfluxDB rejects data outside retention window (30 days default)

### After Transformation
```
CSV (2026 dates) → Simulator → Kafka → Consumer → InfluxDB ✅ (accepted)
                                                  → MinIO ✅ (works)
```

**Result:** Both hot path (InfluxDB) and cold path (MinIO) work correctly

## Notes

- ✅ Preserves time-of-day from original timestamps for realism
- ✅ Filters out any records that would map to future dates
- ✅ Safe to re-run multiple times (overwrites output files)
- ✅ Does not modify original `data/data.csv`
- ✅ Creates `data/processed/` directory if it doesn't exist
- ✅ Both CSV and TXT formats generated automatically
- ⚠️ TXT format has NO headers (by design for legacy compatibility)
- ⚠️ Re-run transformation when testing on different days (dates shift)

## Troubleshooting

### Problem: "No data in InfluxDB"
**Solution:** Ensure you're using `data_realtime.csv` in docker-compose.yml

### Problem: "All data filtered out"
**Cause:** Running script on a different date than dataset was created  
**Solution:** Re-run `transform_to_realtime.py` to regenerate with current date

### Problem: "Future timestamp rejected"
**Cause:** System clock incorrect or transformation bug  
**Solution:** 
1. Check system date: `date` (Linux/Mac) or `Get-Date` (PowerShell)
2. Validate output: `python data/realtime_mapping/validate_output.py`

### Problem: "CSV has headers but TXT doesn't"
**Expected:** This is by design. Use CSV for imports, TXT for legacy systems.

## Version History

- **v1.0.0** (2026-02-16): Initial release with 80% proportional mapping
- **v1.1.0** (2026-02-16): Added TXT format output to `data/processed/`

## Related Documentation

- [SIEIS Architecture](../../Documentation/ARCHITECTURE.md)
- [Retention Policy Guide](../../Documentation/RETENTION_POLICY_GUIDE.md)
- [Testing Guide](../../tests/README.md)