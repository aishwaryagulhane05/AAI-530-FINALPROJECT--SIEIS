"""SIEIS Streamlit Dashboard — main entry point.

Usage:
    streamlit run src/app/dashboard/app.py

Or via the run script:
    python scripts/run_dashboard.py
"""

import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

st.set_page_config(
    page_title="SIEIS — Smart IoT Sensor Dashboard",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Home page content ───────────────────────────────────────────────────────
st.title("📡 SIEIS — Smart IoT Environmental Information System")
st.markdown("---")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Data Source", "Intel Lab Dataset", delta="54 motes")

with col2:
    st.metric("Sensors", "4 metrics", delta="Temp / Humidity / Light / Voltage")

with col3:
    st.metric("Storage", "Dual-write", delta="InfluxDB + MinIO")

with col4:
    st.metric("ML Model", "Isolation Forest", delta="Anomaly Detection")

st.markdown("---")

st.markdown("""
## Welcome to SIEIS Dashboard

Use the **sidebar** to navigate between views:

| Page | Purpose |
|------|---------|
| 🔴 Real-time Monitor | Live sensor data from InfluxDB (last 1h–24h) |
| 📈 Historical Analysis | Long-term trends from MinIO Parquet archives |
| 🤖 Anomaly Detection | ML-powered anomaly analysis and alerts |

### Quick Start
1. Make sure Docker containers are running: `docker compose up -d`
2. Verify data is flowing: `python scripts/verify_influxDb.py`
3. Train the ML model: `python scripts/train_model.py`
4. Start the API: `python -m src.app.api_server`

### System Architecture
```
Sensors → Simulator → Redpanda/Kafka → Consumer ┬→ InfluxDB (hot)  → API → Dashboard
                                                  └→ MinIO (cold)    → ML  → Dashboard
```
""")

st.sidebar.success("Select a page above ☝️")
