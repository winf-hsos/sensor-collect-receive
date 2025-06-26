import os
from pathlib import Path
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()

# Get the title from the environment variable or set a default
TITLE = os.getenv('DASHBOARD_TITLE', 'Live Sensor Data Chart')

# Set wide page layout
st.set_page_config(page_title=TITLE, layout="wide")

# Title
st.title(TITLE)

# Sidebar controls
CSV_FILE_DEFAULT = os.getenv('CSV_FILE_RECEIVER', 'sensor_data.csv')
csv_path = Path(st.sidebar.text_input("CSV file path", CSV_FILE_DEFAULT))
refresh_interval = st.sidebar.number_input(
    "Refresh interval (seconds)", min_value=1, value=5
)

# Time range selector
time_options = [
    "Last 1 minute",
    "Last 10 minutes",
    "Last 20 minutes",
    "Last 1 hour",
    "Last 12 hours",
    "Last 1 day"
]
time_range = st.sidebar.selectbox("Time range", time_options, index=3)

# Y-axis limits toggle and inputs
set_limits = st.sidebar.checkbox("Set Y-axis limits manually")
y_min_manual = None
y_max_manual = None
if set_limits:
    y_min_manual = st.sidebar.number_input(
        "Y-axis min", value=0.00, format="%.2f", step=0.1
    )
    y_max_manual = st.sidebar.number_input(
        "Y-axis max", value=100.00, format="%.2f", step=0.1
    )

# Smoothing control
smoothing = st.sidebar.number_input(
    "Smoothing window (points)", min_value=1, value=1, step=1
)

# Automatically rerun this app every `refresh_interval` seconds
_ = st_autorefresh(interval=refresh_interval * 1000, key="data_refresh")

# Read and process the CSV
if not csv_path.exists():
    st.warning(f"File '{csv_path}' not found. Please check the path.")
else:
    try:
        # Load data
        df = (
            pd.read_csv(csv_path, parse_dates=["time"])  # parse dates
              .sort_values("time")                     # sort by time
        )
        if "value" not in df.columns:
            st.error("CSV must contain 'time' and 'value' columns.")
        else:
            # Filter by selected time range
            now = pd.Timestamp.now()
            delta_map = {
                "Last 1 minute": pd.Timedelta(minutes=1),
                "Last 10 minutes": pd.Timedelta(minutes=10),
                "Last 20 minutes": pd.Timedelta(minutes=20),
                "Last 1 hour": pd.Timedelta(hours=1),
                "Last 12 hours": pd.Timedelta(hours=12),
                "Last 1 day": pd.Timedelta(days=1)
            }
            cutoff = now - delta_map.get(time_range, pd.Timedelta(hours=1))
            df_filtered = df[df["time"] >= cutoff].copy()

            if df_filtered.empty:
                st.warning(f"No data in the selected time range: {time_range}")
            else:
                # Display latest value received with metric component
                latest_row = df_filtered.iloc[-1]
                latest_time = latest_row["time"].strftime('%Y-%m-%d %H:%M:%S')
                latest_value = latest_row["value"]
                st.metric(label="Current Value (mV)", value=f"{latest_value:.2f}", delta=None)

                # Apply smoothing if requested
                if smoothing > 1:
                    df_filtered["smoothed"] = (
                        df_filtered["value"]
                            .rolling(window=int(smoothing), min_periods=1)
                            .mean()
                    )
                    value_field = "smoothed"
                else:
                    value_field = "value"

                # Compute y-axis domain with at least 10% padding
                if set_limits and y_min_manual is not None and y_max_manual is not None:
                    y_domain = [y_min_manual, y_max_manual]
                else:
                    data_min = df_filtered[value_field].min()
                    data_max = df_filtered[value_field].max()
                    padding = (data_max - data_min) * 0.10
                    if padding <= 0:
                        padding = abs(data_min) * 0.10 if data_min != 0 else 1
                    y_domain = [data_min - padding, data_max + padding]

                                                # Determine if points should be shown (limit for readability)
                show_points = len(df_filtered) <= 100

                # Define mark properties
                mark_def = {"type": "line", "tooltip": True, "point": show_points}

                # Configure x-axis formatting and tick counts based on selected time range and tick counts based on selected time range
                fmt_map = {
                    "Last 1 minute": ("%H:%M:%S", 6),       # show seconds, ~6 ticks
                    "Last 10 minutes": ("%H:%M", 10),        # show minutes, ~10 ticks
                    "Last 20 minutes": ("%H:%M", 4),         # show every 5 minutes
                    "Last 1 hour": ("%H:%M", 12),            # show every 5 minutes
                    "Last 12 hours": ("%H:%M", 12),          # show hours
                    "Last 1 day": ("%H:%M", 24)               # show hours
                }
                fmt, tick_count = fmt_map.get(time_range, ("%H:%M", 10))
                x_axis = {"format": fmt, "title": "Time", "tickCount": tick_count, "labelAngle": -45}

                # Define Vega-Lite spec with container width, aspect ratio, and dynamic x-axis
                spec = {
                    "width": "container",
                    "aspect": 2,
                    "mark": mark_def,
                    "encoding": {
                        "x": {"field": "time", "type": "temporal", "axis": x_axis},
                        "y": {"field": value_field, "type": "quantitative", "scale": {"domain": y_domain}, "axis": {"title": "Value (mV)"}}
                    }
                }
                # Render chart
                st.vega_lite_chart(df_filtered, spec, use_container_width=True)
    except Exception as e:
        st.error(f"Error reading CSV: {e}")
      
