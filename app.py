import os
from pathlib import Path
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from dotenv import load_dotenv

# ---------- Setup ----------
load_dotenv()
TITLE = os.getenv('DASHBOARD_TITLE', 'Live Sensor Data Chart')
DATA_DIR = Path(os.getenv('DATA_DIR', 'data'))  # folder to scan at startup
CSV_FILE_DEFAULT = os.getenv('CSV_FILE_RECEIVER', 'sensor_data.csv')

st.set_page_config(page_title=TITLE, layout="wide")
st.title(TITLE)

# ---------- Session state bootstrapping ----------
if "csv_paths" not in st.session_state:
    st.session_state.csv_paths = []
if "csv_titles" not in st.session_state:
    st.session_state.csv_titles = []
if "initialized_from_folder" not in st.session_state:
    st.session_state.initialized_from_folder = False

def init_from_folder():
    """Populate csv_paths/titles from DATA_DIR on first load."""
    candidates = []
    if DATA_DIR.exists() and DATA_DIR.is_dir():
        # All CSVs in data dir (non-recursive), sorted by name
        candidates = sorted([p for p in DATA_DIR.glob("*.csv") if p.is_file()], key=lambda p: p.name)
    # Fallback to default if folder empty
    if not candidates:
        candidates = [Path(CSV_FILE_DEFAULT)]
    st.session_state.csv_paths = [str(p) for p in candidates]
    st.session_state.csv_titles = [p.name for p in candidates]
    st.session_state.initialized_from_folder = True

if not st.session_state.initialized_from_folder:
    init_from_folder()

# ---------- Sidebar: global controls ----------
st.sidebar.markdown("### Data sources")

# Add file button (instant)
if st.sidebar.button("➕ Add file", use_container_width=True):
    st.session_state.csv_paths.append(CSV_FILE_DEFAULT)
    st.session_state.csv_titles.append(Path(CSV_FILE_DEFAULT).name)
    st.rerun()

# Render paired inputs: path + title + delete
for i in range(len(st.session_state.csv_paths)):
    with st.sidebar.container():
        c1, c2 = st.sidebar.columns([6, 1])
        with c1:
            # path
            st.session_state.csv_paths[i] = st.text_input(
                f"CSV file path {i+1}",
                value=st.session_state.csv_paths[i],
                key=f"csv_path_{i}"
            )
            # title
            default_title = Path(st.session_state.csv_paths[i]).name or st.session_state.csv_titles[i]
            st.session_state.csv_titles[i] = st.text_input(
                f"Chart title {i+1}",
                value=st.session_state.csv_titles[i] or default_title,
                key=f"csv_title_{i}"
            )
        with c2:
            # delete button
            if st.button("🗑️", key=f"del_{i}", help="Remove this chart"):
                del st.session_state.csv_paths[i]
                del st.session_state.csv_titles[i]
                st.rerun()
    st.sidebar.markdown("---")

refresh_interval = st.sidebar.number_input("Refresh interval (seconds)", min_value=1, value=5)

time_options = [
    "Last 1 minute",
    "Last 10 minutes",
    "Last 20 minutes",
    "Last 1 hour",
    "Last 12 hours",
    "Last 1 day"
]
time_range = st.sidebar.selectbox("Time range", time_options, index=3)

# Display series (applies to all charts)
display_choice = st.sidebar.selectbox(
    "Display series (applies to all charts)",
    ["Voltage (mV)", "pH"],
    index=0
)
if display_choice == "pH":
    series_col = "pH"
    axis_title = "pH"
    metric_label = "Current pH"
    metric_fmt = "{:.2f}"
else:
    series_col = "value"
    axis_title = "Value (mV)"
    metric_label = "Current Value (mV)"
    metric_fmt = "{:.2f}"

# Y-axis limits (global)
set_limits = st.sidebar.checkbox("Set Y-axis limits manually")
y_min_manual = y_max_manual = None
if set_limits:
    y_min_manual = st.sidebar.number_input("Y-axis min", value=0.00, format="%.2f", step=0.1)
    y_max_manual = st.sidebar.number_input("Y-axis max", value=100.00, format="%.2f", step=0.1)

# Smoothing (global)
smoothing = st.sidebar.number_input("Smoothing window (points)", min_value=1, value=1, step=1)

# Auto-refresh
_ = st_autorefresh(interval=refresh_interval * 1000, key="data_refresh")

# ---------- Helpers ----------
def load_and_prepare(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        st.warning(f"File '{path}' not found.")
        return None
    try:
        # Read as-is; avoid relying only on parse_dates
        df = pd.read_csv(path)

        # Normalize column names (strip spaces)
        df.columns = [c.strip() for c in df.columns]

        # Ensure required columns
        if "time" not in df.columns or "value" not in df.columns:
            st.error(f"CSV '{path}' must contain 'time' and 'value' columns.")
            return None

        # Robust parsing
        df["time"] = pd.to_datetime(df["time"], errors="coerce")
        df["value"] = pd.to_numeric(df["value"], errors="coerce")

        if "pH" in df.columns:
            df["pH"] = pd.to_numeric(df.get("pH"), errors="coerce")

        # Drop rows with invalid time or value
        bad_time = df["time"].isna().sum()
        bad_val = df["value"].isna().sum()
        if bad_time or bad_val:
            st.warning(
                f"'{path.name}': dropped {bad_time} rows with bad time and {bad_val} with non-numeric value."
            )
        df = df.dropna(subset=["time", "value"])

        # Sort by time after cleaning
        df = df.sort_values("time").reset_index(drop=True)
        return df

    except Exception as e:
        st.error(f"Error reading CSV '{path}': {e}")
        return None


def filter_time(df: pd.DataFrame, time_range: str) -> pd.DataFrame:
    # df['time'] is guaranteed datetime64[ns] after load_and_prepare
    now = pd.Timestamp.now()
    delta_map = {
        "Last 1 minute": pd.Timedelta(minutes=1),
        "Last 10 minutes": pd.Timedelta(minutes=10),
        "Last 20 minutes": pd.Timedelta(minutes=20),
        "Last 1 hour": pd.Timedelta(hours=1),
        "Last 12 hours": pd.Timedelta(hours=12),
        "Last 1 day": pd.Timedelta(days=1),
    }
    cutoff = now - delta_map.get(time_range, pd.Timedelta(hours=1))
    return df[df["time"] >= cutoff].copy()


def y_domain_from_series(series: pd.Series):
    if set_limits and y_min_manual is not None and y_max_manual is not None:
        return [y_min_manual, y_max_manual]
    data_min = series.min()
    data_max = series.max()
    padding = (data_max - data_min) * 0.10
    if padding <= 0:
        padding = abs(float(data_min)) * 0.10 if data_min != 0 else 1.0
    return [data_min - padding, data_max + padding]

def x_axis_for(time_range: str):
    fmt_map = {
        "Last 1 minute": ("%H:%M:%S", 6),
        "Last 10 minutes": ("%H:%M", 10),
        "Last 20 minutes": ("%H:%M", 4),
        "Last 1 hour": ("%H:%M", 12),
        "Last 12 hours": ("%H:%M", 12),
        "Last 1 day": ("%H:%M", 24)
    }
    fmt, tick_count = fmt_map.get(time_range, ("%H:%M", 10))
    return {"format": fmt, "title": "Time", "tickCount": tick_count, "labelAngle": -45}

def render_chart(df_filtered: pd.DataFrame, title: str):
    # If pH selected but none present, warn
    if series_col == "pH" and ("pH" not in df_filtered.columns or df_filtered["pH"].dropna().empty):
        st.subheader(title)
        st.warning("No pH data available in the selected window.")
        return

    # Apply smoothing
    working_col = series_col
    if smoothing > 1:
        smoothed_col = f"{series_col}_smoothed"
        df_filtered[smoothed_col] = (
            df_filtered[series_col]
            .rolling(window=int(smoothing), min_periods=1)
            .mean()
        )
        working_col = smoothed_col

    # Latest metric
    latest_row = df_filtered.iloc[-1]
    latest_val = latest_row.get(series_col, None)
    if pd.isna(latest_val) if latest_val is not None else True:
        recent_non_nan = df_filtered[series_col].dropna()
        latest_val = recent_non_nan.iloc[-1] if not recent_non_nan.empty else None

    st.subheader(title)
    if latest_val is None or pd.isna(latest_val):
        st.metric(label=metric_label, value="—", delta=None)
    else:
        st.metric(label=metric_label, value=metric_fmt.format(latest_val), delta=None)

    # Domain and mark
    y_series = df_filtered[working_col].dropna()
    if y_series.empty:
        st.warning("No valid points to plot.")
        return

    y_domain = y_domain_from_series(y_series)
    show_points = len(df_filtered) <= 100
    mark_def = {"type": "line", "tooltip": True, "point": show_points}
    x_axis = x_axis_for(time_range)

    spec = {
        "width": "container",
        "aspect": 2,
        "mark": mark_def,
        "encoding": {
            "x": {"field": "time", "type": "temporal", "axis": x_axis},
            "y": {
                "field": working_col,
                "type": "quantitative",
                "scale": {"domain": y_domain},
                "axis": {"title": axis_title}
            }
        }
    }
    st.vega_lite_chart(df_filtered, spec, use_container_width=True)

# ---------- Load, filter, and render in a 2-per-row grid ----------
prepared = []
for path_str, title in zip(st.session_state.csv_paths, st.session_state.csv_titles):
    p = Path(path_str)
    df = load_and_prepare(p)
    if df is None:
        continue
    df_filtered = filter_time(df, time_range)
    display_title = title or p.name
    if df_filtered.empty:
        prepared.append((display_title, None))
    else:
        prepared.append((display_title, df_filtered))

if not prepared:
    st.info("No valid data sources yet. Add a CSV path on the left.")
else:
    chunk = 2  # two charts per row
    for i in range(0, len(prepared), chunk):
        cols = st.columns(chunk)
        for j, (title, df_filtered) in enumerate(prepared[i:i+chunk]):
            with cols[j]:
                if df_filtered is None or df_filtered.empty:
                    st.subheader(title)
                    st.warning(f"No data in the selected time range: {time_range}")
                else:
                    render_chart(df_filtered, title=title)
