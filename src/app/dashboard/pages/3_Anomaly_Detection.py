"""Anomaly detection page — ML model inference via the SIEIS API."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

from dotenv import load_dotenv
load_dotenv()

import json
import logging
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Anomaly Detection", page_icon="🤖", layout="wide")
st.title("🤖 Anomaly Detection")
st.caption("ML-powered anomaly analysis using Isolation Forest")

from src.app import config

_api_url = os.getenv("API_URL", f"http://localhost:{config.API_PORT}")
API_BASE = f"{_api_url}/api/v1"


def call_api(path: str, method: str = "GET", body: dict = None):
    """Call the SIEIS API with error handling."""
    try:
        url = f"{API_BASE}{path}"
        if method == "POST":
            resp = requests.post(url, json=body, timeout=5)
        else:
            resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.ConnectionError:
        return None, "API not running. Start it with: python -m src.app.api_server"
    except Exception as e:
        return None, str(e)


# ─── API Status ───────────────────────────────────────────────────────────────
health_data, health_err = call_api("/health", method="GET")

col_status, col_model = st.columns(2)
with col_status:
    if health_err:
        st.error(f"❌ API Offline — {health_err}")
        api_online = False
    else:
        st.success("✅ API Online")
        api_online = True

with col_model:
    if api_online and health_data:
        model_loaded = health_data.get("model_loaded", False)
        if model_loaded:
            st.success("✅ ML Model Loaded")
        else:
            st.warning("⚠️ Model not trained yet — using rule-based fallback")
            st.caption("Run: `python scripts/train_model.py` to train the model")

st.markdown("---")

# ─── Model Info ───────────────────────────────────────────────────────────────
if api_online:
    with st.expander("📋 Model Info", expanded=False):
        model_info, err = call_api("/ml/model/info")
        if model_info:
            st.json(model_info)
        else:
            st.warning(err or "Could not fetch model info")

    col_reload, _ = st.columns([1, 3])
    with col_reload:
        if st.button("🔄 Reload Model"):
            result, err = call_api("/ml/model/reload", method="POST")
            if result:
                st.success("Model reloaded!")
            else:
                st.error(err)

st.markdown("---")

# ─── Single Reading Prediction ─────────────────────────────────────────────────
st.subheader("🔎 Single Reading Prediction")
st.markdown("Enter sensor values to check if they're anomalous.")

with st.form("predict_form"):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        temperature = st.number_input("Temperature (°C)", min_value=-50.0, max_value=100.0, value=22.5, step=0.1)
    with col2:
        humidity    = st.number_input("Humidity (%)",     min_value=0.0,   max_value=100.0, value=55.0, step=0.1)
    with col3:
        light       = st.number_input("Light (Lux)",      min_value=0.0,   max_value=5000.0,value=300.0,step=1.0)
    with col4:
        voltage     = st.number_input("Voltage (V)",      min_value=0.0,   max_value=5.0,   value=2.9,  step=0.01)

    mote_id_input = st.text_input("Mote ID (optional)", value="", placeholder="e.g. 1")
    submitted = st.form_submit_button("🔍 Check for Anomaly", use_container_width=True)

if submitted:
    if not api_online:
        st.error("API is not running. Cannot make predictions.")
    else:
        payload = {
            "temperature": temperature,
            "humidity": humidity,
            "light": light,
            "voltage": voltage,
        }
        if mote_id_input.strip():
            payload["mote_id"] = mote_id_input.strip()

        with st.spinner("Running anomaly detection..."):
            result, err = call_api("/ml/predict/anomaly", method="POST", body=payload)

        if result:
            severity = result.get("severity", "normal")
            score = result.get("anomaly_score", 0)
            is_anomaly = result.get("is_anomaly", False)

            color_map = {"normal": "🟢", "warning": "🟡", "critical": "🔴"}
            emoji = color_map.get(severity, "⚪")

            res_col1, res_col2, res_col3 = st.columns(3)
            res_col1.metric("Anomaly Score", f"{score:.4f}", delta=None)
            res_col2.metric("Status", f"{emoji} {severity.upper()}")
            res_col3.metric("Is Anomaly", "YES ⚠️" if is_anomaly else "NO ✅")

            # Score gauge
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=score * 100,
                domain={"x": [0, 1], "y": [0, 1]},
                title={"text": "Anomaly Score (0=Normal, 100=Anomaly)"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "darkred" if is_anomaly else "darkgreen"},
                    "steps": [
                        {"range": [0,  50], "color": "lightgreen"},
                        {"range": [50, 65], "color": "yellow"},
                        {"range": [65, 100], "color": "lightcoral"},
                    ],
                    "threshold": {"line": {"color": "red", "width": 4}, "thickness": 0.75, "value": 65},
                },
            ))
            fig_gauge.update_layout(height=300)
            st.plotly_chart(fig_gauge, use_container_width=True)
        else:
            st.error(f"Prediction failed: {err}")

st.markdown("---")

# ─── Batch anomaly scan ───────────────────────────────────────────────────────
st.subheader("📊 Batch Anomaly Scan — Recent Sensor Data")
st.markdown("Scan latest readings from InfluxDB for anomalies.")

if st.button("🚀 Run Batch Scan", disabled=not api_online):
    # Fetch latest readings from InfluxDB
    try:
        from influxdb_client import InfluxDBClient
        client = InfluxDBClient(url=config.INFLUX_URL, token=config.INFLUX_TOKEN, org=config.INFLUX_ORG)
        query_api = client.query_api()
        flux = f"""
from(bucket: "{config.INFLUX_BUCKET}")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
  |> last()
  |> pivot(rowKey:["_time","mote_id"], columnKey: ["_field"], valueColumn: "_value")
"""
        tables = query_api.query_data_frame(flux, org=config.INFLUX_ORG)
        client.close()

        if isinstance(tables, list):
            df = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()
        else:
            df = tables

        if df.empty:
            st.warning("No recent data in InfluxDB. Run the simulator first.")
        else:
            results = []
            progress = st.progress(0)
            for i, row in df.iterrows():
                payload = {
                    "temperature": float(row.get("temperature", 22)),
                    "humidity": float(row.get("humidity", 50)),
                    "light": float(row.get("light", 100)),
                    "voltage": float(row.get("voltage", 2.9)),
                    "mote_id": str(row.get("mote_id", "unknown")),
                }
                result, _ = call_api("/ml/predict/anomaly", method="POST", body=payload)
                if result:
                    results.append({
                        "mote_id": payload["mote_id"],
                        "temperature": payload["temperature"],
                        "humidity": payload["humidity"],
                        "light": payload["light"],
                        "voltage": payload["voltage"],
                        "anomaly_score": result["anomaly_score"],
                        "is_anomaly": result["is_anomaly"],
                        "severity": result["severity"],
                    })
                progress.progress(min(1.0, (i + 1) / max(len(df), 1)))

            if results:
                df_results = pd.DataFrame(results)
                anomalies = df_results[df_results["is_anomaly"]]

                a_col1, a_col2, a_col3 = st.columns(3)
                a_col1.metric("Motes Scanned", len(df_results))
                a_col2.metric("Anomalies Found", len(anomalies))
                a_col3.metric("Anomaly Rate", f"{len(anomalies)/max(len(df_results),1):.1%}")

                # Anomaly score scatter
                fig_scatter = px.scatter(
                    df_results, x="mote_id", y="anomaly_score",
                    color="severity",
                    color_discrete_map={"normal": "green", "warning": "orange", "critical": "red"},
                    title="Anomaly Scores per Mote",
                    size_max=15,
                )
                fig_scatter.add_hline(y=0.5,  line_dash="dash", line_color="orange", annotation_text="Warning threshold")
                fig_scatter.add_hline(y=0.65, line_dash="dash", line_color="red",    annotation_text="Critical threshold")
                st.plotly_chart(fig_scatter, use_container_width=True)

                # ── Full results table with colour-coded rows ──────────────
                st.subheader("📋 All Readings")

                # Row-level background colours by severity
                def _row_color(row):
                    colors = {
                        "normal":   "background-color: #d4edda",   # green
                        "warning":  "background-color: #fff3cd",   # amber
                        "critical": "background-color: #f8d7da",   # red
                    }
                    style = colors.get(row.get("severity", "normal"), "")
                    return [style] * len(row)

                # Add a Status emoji column at the front for quick scanning
                display_df = df_results.copy()
                display_df.insert(0, "Status", display_df["severity"].map({
                    "normal":   "🟢 Normal",
                    "warning":  "🟡 Warning",
                    "critical": "🔴 Critical",
                }))
                display_df = display_df.sort_values("anomaly_score", ascending=False)

                st.dataframe(
                    display_df.style.apply(_row_color, axis=1),
                    use_container_width=True,
                )

                # Keep a focused anomaly-only section below
                if not anomalies.empty:
                    st.subheader("🚨 Anomalous Readings Only")
                    st.dataframe(
                        anomalies.sort_values("anomaly_score", ascending=False),
                        use_container_width=True,
                    )
    except Exception as e:
        st.error(f"Batch scan failed: {e}")
