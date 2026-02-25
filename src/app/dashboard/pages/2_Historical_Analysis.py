"""Historical data analysis — queries MinIO Parquet files."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

from dotenv import load_dotenv
load_dotenv()

import io
import logging
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Historical Analysis", page_icon="📈", layout="wide")
st.title("📈 Historical Sensor Analysis")
st.caption("Long-term trends from MinIO cold storage (Parquet files)")

from src.app import config


@st.cache_data(ttl=300)
def load_local_data(max_rows: int = 100_000) -> pd.DataFrame:
    """Load from local historical_data.txt (fallback when MinIO is empty)."""
    hist_path = config.DATA_DIR / "processed" / "historical_data.txt"
    if not hist_path.exists():
        return pd.DataFrame()
    cols = ["date", "time", "epoch", "mote_id", "temperature", "humidity", "light", "voltage", "updated_timestamp"]
    df = pd.read_csv(str(hist_path), sep=r"\s+", names=cols, na_values=["N/A", "nan", ""], nrows=max_rows, on_bad_lines="skip")
    df["timestamp"] = pd.to_datetime(df["date"] + " " + df["time"], errors="coerce")
    # Normalize mote_id to plain int — mixed int/float parsing causes duplicates (e.g. 1 vs 1.0)
    df["mote_id"] = pd.to_numeric(df["mote_id"], errors="coerce").astype("Int64")
    for col in ["temperature", "humidity", "light", "voltage"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["temperature", "humidity"], how="all")
    return df


@st.cache_data(ttl=300)
def load_minio_data(max_rows: int = 500_000) -> pd.DataFrame:
    """Load ALL Parquet files from MinIO in parallel, capped at max_rows total rows."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from minio import Minio

    try:
        client = Minio(
            config.MINIO_ENDPOINT,
            access_key=config.MINIO_ACCESS_KEY,
            secret_key=config.MINIO_SECRET_KEY,
            secure=config.MINIO_SECURE,
        )
        objects = list(client.list_objects(config.MINIO_BUCKET, recursive=True))
        parquet_objects = sorted(
            [o for o in objects if o.object_name.endswith(".parquet")],
            key=lambda o: o.object_name,
        )
        if not parquet_objects:
            return pd.DataFrame()

        def _fetch(obj_name: str):
            """Download one Parquet file and return a DataFrame."""
            try:
                # Each thread needs its own client instance (not thread-safe to share)
                _client = Minio(
                    config.MINIO_ENDPOINT,
                    access_key=config.MINIO_ACCESS_KEY,
                    secret_key=config.MINIO_SECRET_KEY,
                    secure=config.MINIO_SECURE,
                )
                resp = _client.get_object(config.MINIO_BUCKET, obj_name)
                data = resp.read()
                resp.close()
                return pd.read_parquet(io.BytesIO(data))
            except Exception as e:
                logger.warning(f"Failed to load {obj_name}: {e}")
                return pd.DataFrame()

        frames = []
        total_rows = 0
        # Use up to 8 parallel workers — saturates MinIO I/O without overwhelming it
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {
                pool.submit(_fetch, obj.object_name): obj.object_name
                for obj in parquet_objects
            }
            for future in as_completed(futures):
                if total_rows >= max_rows:
                    future.cancel()
                    continue
                chunk = future.result()
                if not chunk.empty:
                    frames.append(chunk)
                    total_rows += len(chunk)

        if not frames:
            return pd.DataFrame()

        df = pd.concat(frames, ignore_index=True)
        # Sort chronologically after parallel assembly
        if "timestamp" in df.columns:
            df = df.sort_values("timestamp").reset_index(drop=True)
        # Apply row cap
        if len(df) > max_rows:
            df = df.iloc[:max_rows]
        # Normalize mote_id to plain int
        if "mote_id" in df.columns:
            df["mote_id"] = pd.to_numeric(df["mote_id"], errors="coerce").astype("Int64")
        return df

    except Exception as e:
        logger.warning(f"MinIO load failed: {e}")
        return pd.DataFrame()


# ─── Sidebar Controls ─────────────────────────────────────────────────────────
import datetime as _dt

# Retrieve saved data bounds from session_state (populated after first load)
_saved_min: _dt.date | None = st.session_state.get("data_min")
_saved_max: _dt.date | None = st.session_state.get("data_max")

with st.sidebar:
    st.header("⚙️ Controls")
    data_source = st.radio("Data source", ["Local file", "MinIO Parquet"])
    max_rows = st.slider("Max rows to load", 10_000, 2_000_000, 500_000, 10_000)
    selected_metric = st.selectbox("Metric", ["temperature", "humidity", "light", "voltage"])

    st.markdown("---")
    st.markdown("**🗓️ Date Range Filter**")
    if _saved_min and _saved_max:
        date_start = st.date_input(
            "Start Date", value=_saved_min,
            min_value=_saved_min, max_value=_saved_max,
            key="date_start",
        )
        date_end = st.date_input(
            "End Date", value=_saved_max,
            min_value=_saved_min, max_value=_saved_max,
            key="date_end",
        )
    else:
        st.caption("Loading data to determine date range…")
        date_start = date_end = None

    st.markdown("---")
    if data_source == "MinIO Parquet":
        st.code(f"MinIO: {config.MINIO_ENDPOINT}\nBucket: {config.MINIO_BUCKET}", language="text")
        st.caption("All Parquet files loaded. Use the slider to limit total rows.")
    else:
        st.code("File: data/processed/historical_data.txt", language="text")

# ─── Load data ────────────────────────────────────────────────────────────────
_cache_col, _btn_col = st.columns([5, 1])
with _btn_col:
    if st.button("🔄 Refresh", help="Clear cache and reload data from source"):
        load_minio_data.clear()
        load_local_data.clear()
        st.session_state.pop("data_min", None)
        st.session_state.pop("data_max", None)
        st.rerun()

if data_source == "MinIO Parquet":
    with st.spinner("Loading Parquet files from MinIO in parallel — results are cached for 5 min after first load…"):
        df = load_minio_data(max_rows)
        if df.empty:
            st.warning("No Parquet files found in MinIO. Loading from local file instead.")
            df = load_local_data(max_rows)
else:
    with st.spinner("Loading local data file…"):
        df = load_local_data(max_rows)

if df.empty:
    st.error("No data available. Run `python scripts/load_historical_data.py` first.")
    st.stop()

# Ensure timestamp column
if "timestamp" not in df.columns and "date" in df.columns and "time" in df.columns:
    df["timestamp"] = pd.to_datetime(df["date"] + " " + df["time"], errors="coerce")
elif "timestamp" not in df.columns and "_time" in df.columns:
    df["timestamp"] = pd.to_datetime(df["_time"], errors="coerce")

# Force timestamp to proper datetime dtype regardless of source
if "timestamp" in df.columns:
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

# Ensure numeric sensor cols
for col in ["temperature", "humidity", "light", "voltage"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# ─── Save data bounds to session_state, rerun once so pickers appear ──────────
if "timestamp" in df.columns:
    _ts = df["timestamp"].dropna()
    if len(_ts) > 0:
        _new_min, _new_max = _ts.min().date(), _ts.max().date()
        if st.session_state.get("data_min") != _new_min or st.session_state.get("data_max") != _new_max:
            st.session_state["data_min"] = _new_min
            st.session_state["data_max"] = _new_max
            st.rerun()   # re-render sidebar with correct picker bounds

# ─── Apply date filter ────────────────────────────────────────────────────────
if date_start and date_end and "timestamp" in df.columns:
    mask = (df["timestamp"].dt.date >= date_start) & (df["timestamp"].dt.date <= date_end)
    df = df[mask].reset_index(drop=True)
    if df.empty:
        st.warning("No records in the selected date range. Adjust the filter in the sidebar.")
        st.stop()

# ─── Sidebar stats (injected after filter applied) ────────────────────────────
with st.sidebar:
    st.markdown("**📊 Dataset Stats**")
    st.metric("Records", f"{len(df):,}")
    st.metric("Unique Motes", df["mote_id"].nunique() if "mote_id" in df.columns else "N/A")

# ─── KPI Row ──────────────────────────────────────────────────────────────────
st.subheader("📊 Dataset Overview")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Records", f"{len(df):,}")
col2.metric("Unique Motes", df["mote_id"].nunique() if "mote_id" in df.columns else "N/A")
if "timestamp" in df.columns:
    ts = df["timestamp"].dropna()
    if len(ts) > 0:
        col3.metric("Date Range Start", str(ts.min().date()))
        col4.metric("Date Range End", str(ts.max().date()))

# ─── Daily averages chart ─────────────────────────────────────────────────────
st.subheader(f"📅 Daily Average {selected_metric.title()}")

if "timestamp" in df.columns and selected_metric in df.columns:
    df_daily = df.copy()
    df_daily["date"] = df_daily["timestamp"].dt.date
    daily_avg = df_daily.groupby("date")[selected_metric].mean().reset_index()
    daily_avg.columns = ["date", "avg_value"]
    daily_avg = daily_avg.dropna()

    if not daily_avg.empty:
        fig_daily = px.line(
            daily_avg, x="date", y="avg_value",
            title=f"Daily Average {selected_metric.title()}",
            labels={"avg_value": selected_metric, "date": "Date"},
        )
        fig_daily.update_traces(line_color="#1f77b4")
        fig_daily.update_layout(height=350)
        st.plotly_chart(fig_daily, use_container_width=True)
    else:
        st.info("No daily data to display.")
else:
    st.info("Timestamp or metric column not available in this dataset.")

# ─── Hourly heatmap ───────────────────────────────────────────────────────────
st.subheader(f"🌡️ Hourly Seasonality Heatmap — {selected_metric.title()}")

if "timestamp" in df.columns and selected_metric in df.columns:
    df_heat = df.copy()
    df_heat["hour"] = df_heat["timestamp"].dt.hour
    df_heat["day_of_week"] = df_heat["timestamp"].dt.day_name()

    heat_pivot = (
        df_heat.groupby(["day_of_week", "hour"])[selected_metric]
        .mean()
        .reset_index()
        .pivot(index="day_of_week", columns="hour", values=selected_metric)
    )

    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    heat_pivot = heat_pivot.reindex([d for d in day_order if d in heat_pivot.index])

    if not heat_pivot.empty:
        fig_heat = px.imshow(
            heat_pivot,
            title=f"{selected_metric.title()} by Hour & Day of Week",
            labels={"x": "Hour of Day", "y": "Day", "color": selected_metric},
            color_continuous_scale="RdYlGn",
            aspect="auto",
        )
        fig_heat.update_layout(height=350)
        st.plotly_chart(fig_heat, use_container_width=True)

# ─── Distribution ─────────────────────────────────────────────────────────────
st.subheader(f"📊 Value Distribution — {selected_metric.title()}")

if selected_metric in df.columns:
    col_a, col_b = st.columns(2)

    with col_a:
        fig_hist = px.histogram(
            df.dropna(subset=[selected_metric]),
            x=selected_metric, nbins=50,
            title=f"Distribution of {selected_metric}",
            color_discrete_sequence=["#636EFA"],
        )
        fig_hist.update_layout(height=350)
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_b:
        if "mote_id" in df.columns:
            box_df = df.dropna(subset=[selected_metric])
            top_motes = box_df["mote_id"].value_counts().nlargest(8).index
            box_df = box_df[box_df["mote_id"].isin(top_motes)]
            fig_box = px.box(
                box_df, x="mote_id", y=selected_metric,
                title=f"{selected_metric.title()} by Mote (top 8)",
                color="mote_id",
            )
            fig_box.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig_box, use_container_width=True)

# ─── Raw data preview ─────────────────────────────────────────────────────────
with st.expander("🔍 Raw data sample (first 200 rows)"):
    preview_cols = [c for c in ["mote_id", "timestamp", "temperature", "humidity", "light", "voltage"] if c in df.columns]
    st.dataframe(df[preview_cols].head(200), use_container_width=True)
