"""Real-time sensor monitoring page — queries InfluxDB directly."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

from dotenv import load_dotenv
load_dotenv()

import time
import logging
from typing import List, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Real-time Monitor", page_icon="🔴", layout="wide")
st.title("🔴 Real-time Sensor Monitor")
st.caption("Live data from InfluxDB — auto-refreshes every 30 seconds")

from src.app import config


@st.cache_resource
def get_influx_client():
    from influxdb_client import InfluxDBClient
    return InfluxDBClient(url=config.INFLUX_URL, token=config.INFLUX_TOKEN, org=config.INFLUX_ORG)


def query_influx(flux: str) -> pd.DataFrame:
    """Run a Flux query and return results as DataFrame."""
    try:
        client = get_influx_client()
        query_api = client.query_api()
        tables = query_api.query_data_frame(flux, org=config.INFLUX_ORG)
        if isinstance(tables, list):
            if not tables:
                return pd.DataFrame()
            df = pd.concat(tables, ignore_index=True)
        else:
            df = tables
        # Drop internal InfluxDB columns
        drop_cols = [c for c in df.columns if c.startswith("_") and c not in ["_value", "_time", "_field"]]
        df = df.drop(columns=drop_cols, errors="ignore")
        return df
    except Exception as e:
        st.warning(f"InfluxDB query failed: {e}")
        return pd.DataFrame()


# ─── Sidebar Controls ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Controls")
    time_window = st.selectbox(
        "Time window",
        options=["-15m", "-1h", "-6h", "-24h"],
        index=1,
        format_func=lambda x: {"‑15m": "Last 15 min", "-15m": "Last 15 min", "-1h": "Last 1 hour", "-6h": "Last 6 hours", "-24h": "Last 24 hours"}.get(x, x),
    )
    metric = st.selectbox("Metric to plot", ["temperature", "humidity", "light", "voltage"])
    auto_refresh = st.checkbox("Auto-refresh (30s)", value=False)

    st.markdown("---")
    st.markdown("**Connection**")
    st.code(f"InfluxDB: {config.INFLUX_URL}\nBucket: {config.INFLUX_BUCKET}", language="text")

# ─── KPI Row ──────────────────────────────────────────────────────────────────
st.subheader("📊 Key Metrics")

flux_active = f"""
from(bucket: "{config.INFLUX_BUCKET}")
  |> range(start: -15m)
  |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
  |> keep(columns: ["mote_id"])
  |> distinct(column: "mote_id")
  |> count()
"""

flux_summary = f"""
from(bucket: "{config.INFLUX_BUCKET}")
  |> range(start: {time_window})
  |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
  |> filter(fn: (r) => r["_field"] == "{metric}")
  |> mean()
"""

col1, col2, col3, col4 = st.columns(4)

df_active = query_influx(flux_active)
active_count = 0
if not df_active.empty and "_value" in df_active.columns:
    active_count = int(df_active["_value"].iloc[0])
elif not df_active.empty:
    active_count = len(df_active)

col1.metric("Active Motes (15m)", active_count, delta=None)

df_avg = query_influx(flux_summary)
if not df_avg.empty and "_value" in df_avg.columns:
    avg_val = round(df_avg["_value"].mean(), 2)
    col2.metric(f"Avg {metric.title()}", avg_val)
else:
    col2.metric(f"Avg {metric.title()}", "N/A")

# Count total records
flux_count = f"""
from(bucket: "{config.INFLUX_BUCKET}")
  |> range(start: {time_window})
  |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
  |> filter(fn: (r) => r["_field"] == "temperature")
  |> count()
"""
df_count = query_influx(flux_count)
total_recs = 0
if not df_count.empty and "_value" in df_count.columns:
    total_recs = int(df_count["_value"].sum())
col3.metric("Total Records", f"{total_recs:,}")
col4.metric("Time Window", time_window)

# ─── Time Series Chart ─────────────────────────────────────────────────────────
st.subheader(f"📈 {metric.title()} Over Time")

flux_ts = f"""
from(bucket: "{config.INFLUX_BUCKET}")
  |> range(start: {time_window})
  |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
  |> filter(fn: (r) => r["_field"] == "{metric}")
  |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
"""

df_ts = query_influx(flux_ts)

if not df_ts.empty and "_value" in df_ts.columns:
    time_col = "_time" if "_time" in df_ts.columns else df_ts.columns[0]
    mote_col = "mote_id" if "mote_id" in df_ts.columns else None

    if mote_col:
        # Show top 5 motes to avoid clutter
        top_motes = df_ts.groupby(mote_col)["_value"].count().nlargest(5).index.tolist()
        df_plot = df_ts[df_ts[mote_col].isin(top_motes)]
        fig = px.line(
            df_plot, x=time_col, y="_value", color=mote_col,
            title=f"{metric.title()} — Top 5 most active motes",
            labels={"_value": metric, time_col: "Time", mote_col: "Mote"},
        )
    else:
        fig = px.line(df_ts, x=time_col, y="_value",
                      title=f"{metric.title()} over time",
                      labels={"_value": metric})

    fig.update_layout(height=400, legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No data available for the selected time window. Make sure the simulator and consumer are running.")

# ─── Latest readings grid ──────────────────────────────────────────────────────
st.subheader("🗃️ Latest Reading per Mote")

flux_latest = f"""
from(bucket: "{config.INFLUX_BUCKET}")
  |> range(start: {time_window})
  |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
  |> last()
  |> pivot(rowKey:["_time","mote_id"], columnKey: ["_field"], valueColumn: "_value")
"""

df_latest = query_influx(flux_latest)
if not df_latest.empty:
    display_cols = [c for c in ["mote_id", "temperature", "humidity", "light", "voltage", "_time"] if c in df_latest.columns]
    df_display = df_latest[display_cols].copy()
    if "_time" in df_display.columns:
        df_display = df_display.rename(columns={"_time": "last_seen"})
    for col in ["temperature", "humidity", "light", "voltage"]:
        if col in df_display.columns:
            df_display[col] = df_display[col].round(2)
    st.dataframe(df_display.sort_values("mote_id") if "mote_id" in df_display.columns else df_display, use_container_width=True)
else:
    st.info("No recent data. Ensure the data pipeline is running.")

# ─── Auto-refresh ──────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(30)
    st.rerun()
