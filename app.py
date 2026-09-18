from pathlib import Path

import pandas as pd
import streamlit as st
from datetime import timedelta
# add title

"""
Cache the CSV because every widget interaction reruns the app.
"""
@st.cache_data
def load_data(path):
    # Load the CSV
    data = pd.read_csv(path)

    # Convert the service date to a datetime object
    # Arrival times in transit data may exceed 24:00:00
    # (e.g., 24:25:00 means 0:25 AM on the next calendar day),
    service_date = pd.to_datetime(
        data["opd_date"],
        format="%m/%d/%Y",
    )
    # Convert the arrival time to a timedelta object
    arrival_offset = pd.to_timedelta(data["act_arr_time_hhmmss"])
    # Combine the service date and arrival time to create a datetime object
    data["arrival_datetime"] = service_date + arrival_offset
    return data



st.set_page_config(
    page_title="CDTA Route 12 Dashboard",
    layout="wide",
)

st.title("CDTA Route 12 Passenger Dashboard")
st.caption(
    "Automatic Passenger Counter data from July 4, 2025."
)


# Load the data
DATA_PATH = Path(__file__).parent / "cdta_apc_20250704.csv"

""" Option initialization """
# time initializations
df = load_data(DATA_PATH)
minimum_time = df["arrival_datetime"].min().to_pydatetime()
maximum_time = df["arrival_datetime"].max().to_pydatetime()

# stop initializations
stop_options = sorted(
    df["point_name"].dropna().unique().tolist()
)
# metric initializations
metric_options = {
    "Boardings": "psngr_in",
    "Alightings": "psngr_out",
    "On-board load": "psngr_load",
}


with st.sidebar:
    st.header("Controls")
    # Add a slider to select the arrival-time range
    selected_times = st.slider(
        "Arrival-time range",
        min_value=minimum_time,
        max_value=maximum_time,
        value=(minimum_time, maximum_time),
        step=timedelta(minutes=30),
        format="MM/DD HH:mm",
    )
    # Add a radio button to select the metric   
    selected_stops = st.multiselect(
        "Stops",
        options=stop_options,
        help="Leave empty to include all stops.",
    )

    # Add a radio button to select the metric   
    selected_metric = st.radio(
        "Passenger metric",
        options=list(metric_options.keys()),
    )

""" Data filtering """
# get the selected time range
start_time, end_time = selected_times
# Filter the data by the selected time range
filtered = df[
    df["arrival_datetime"].between(
        start_time,
        end_time,
    )
].copy()
# Filter by the selected stops.
if selected_stops:
    filtered = filtered[
        filtered["point_name"].isin(selected_stops)
    ].copy()
# get the selected metric column
metric_column = metric_options[selected_metric]

# get the aggregation method and y-axis label
if selected_metric in ["Boardings", "Alightings"]:
    aggregation_method = "sum"
    y_axis_label = f"Hourly {selected_metric.lower()} (passengers)"
else:
    aggregation_method = "mean"
    y_axis_label = "Mean on-board load (passengers)"


"""    Fisrt chart: Hourly metric """

hourly_data = (
    filtered.groupby(
        [
            pd.Grouper(
                key="arrival_datetime",
                freq="1h",
            ),
            "direction",
        ]
    )[metric_column]
    .agg(aggregation_method)
    .reset_index(name="value")
)


st.subheader(f"Hourly {selected_metric}")
st.line_chart(
    hourly_data,
    x="arrival_datetime",
    y="value",
    color="direction",
    x_label="Arrival time (local time)",
    y_label=y_axis_label,
    width="stretch",
    height=400,
)

"""    Second chart: Stop-level metric """

# Group the data by stop and aggregate the metric
stop_data = (
    filtered.groupby(
        "point_name",
        as_index=False,
    )[metric_column]
    .agg(aggregation_method)
    .rename(
        columns={metric_column: "value"}
    )
)


if selected_metric in ["Boardings", "Alightings"]:
    stop_axis_label = (
        f"Total {selected_metric.lower()} (passengers)"
    )
else:
    stop_axis_label = (
        "Mean on-board load (passengers)"
    )
st.subheader(f"{selected_metric} by stop")
st.bar_chart(
    stop_data,
    x="point_name",
    y="value",
    x_label="Bus stop",
    y_label=stop_axis_label,
    sort="-value",
    width="stretch",
    height=450,
)


"""    Third chart: Relationship between passenger activity and actual dwell time """

# Keep stop-events where the bus doors opened.
scatter_data = filtered[
    filtered["doors"] == "doors opened"
].copy()
# Total passenger movements during one stop-event.
scatter_data["passenger_activity"] = (
    scatter_data["psngr_in"]
    + scatter_data["psngr_out"]
)

st.subheader(
    "Passenger activity and actual dwell time"
)
st.caption(
    "Each point represents one stop-event where "
    "the bus doors opened."
)
if scatter_data.empty:
    st.info(
        "No door-open stop-events match the current filters."
    )
else:
    st.scatter_chart(
        scatter_data,
        x="passenger_activity",
        y="act_dwelltime",
        color="direction",
        x_label="Passenger movements at stop (passengers)",
        y_label="Actual dwell time (seconds)",
        width="stretch",
        height=450,
    )

"""    Pearson correlation coefficient and R-squared """

if len(scatter_data) >= 2:
    correlation = scatter_data[
        "passenger_activity"
    ].corr(
        scatter_data["act_dwelltime"]
    )

    r_squared = correlation ** 2

    col1, col2 = st.columns(2)

    col1.metric(
        "Passenger activity / dwell correlation",
        f"{correlation:.2f}",
    )

    col2.metric(
        "Simple linear R-squared",
        f"{r_squared:.3f}",
    )

"""    Data provenance and blind spots """
with st.expander(
    "Data provenance and blind spots",
    expanded=True,
):
    st.subheader("Data provenance")

    st.markdown(
        """
        - **Collector:** Capital District Transportation Authority (CDTA)
        - **Place:** Route 12 in Albany, New York
        - **Date:** July 4, 2025
        - **Service context:** Friday calendar day operating a Sunday schedule because of the Independence Day holiday
        - **Instrument:** Automatic Passenger Counters installed at bus doors and linked with vehicle-location records
        """
    )

    st.subheader("Blind spots")
    st.markdown(
        "1. **Holiday representativeness:** "
        "A viewer could conclude that these patterns describe a typical Friday. "
        "They do not; the data cover only Independence Day, when Route 12 "
        "operated a Sunday schedule.\n\n"

        "2. **Passenger-count accuracy:** "
        "A viewer could treat the APC counts as exact. The file records "
        "1,636 boardings and 1,684 alightings, an impossible 48-passenger "
        "imbalance that indicates counting error.\n\n"

        "3. **Hourly aggregation:** "
        "A viewer could interpret changes between adjacent hourly values as "
        "real changes in passenger activity. However, the dashboard groups "
        "observations into fixed clock-hour intervals. Events at 07:59 and "
        "08:01 are placed in different groups even though they are only two "
        "minutes apart, so short peaks may be split or hidden by the aggregation."
    )