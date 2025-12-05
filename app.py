import streamlit as st
import pandas as pd
import requests
import datetime
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

# ---------------------------------------------------------
# 1. PAGE CONFIG
# ---------------------------------------------------------

st.set_page_config(
    page_title="TaxiFareNY",
    page_icon="🚕",
    layout="wide",
)

# ---------------------------------------------------------
# 2. GLOBAL STYLE FIXES (BACKGROUND, SIDEBAR, PICKER COLORS)
# ---------------------------------------------------------

st.markdown("""
    <style>
        body {
            background-color: #ffe5e5 !important;
            overflow-x: hidden;
        }

        /* ----- FIXED SIDEBAR (ALWAYS VISIBLE, NO AUTO-HIDE) ----- */
        [data-testid="stSidebar"] {
            position: fixed !important;
            left: 0;
            top: 0;
            bottom: 0;
            width: 300px !important;
            background-color: #b3003b !important;
            overflow-y: auto !important;
            z-index: 999;
        }

        /* Push main app content to the right */
        [data-testid="stAppViewContainer"] {
            margin-left: 300px !important;
        }

        /* Sidebar text always white */
        [data-testid="stSidebar"] * {
            color: white !important;
        }

        /* General text */
        h1, h2, h3, h4, h5, p, label {
            color: black !important;
        }

        /* ----- DATE & TIME PICKER FIXES (MAKE TEXT BLACK) ----- */
        .stDateInput input,
        .stDateInput div input,
        .stDateInput div *,
        .stTimeInput input,
        .stTimeInput div input,
        .stTimeInput div * {
            color: black !important;
        }

    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 3. CONSTANTS
# ---------------------------------------------------------

API_URL = st.secrets['API_URL']

DEFAULT_LAT = 40.75
DEFAULT_LON = -73.98

NYC_BOUNDS = {
    "min_lon": -74.25,
    "max_lon": -73.70,
    "min_lat": 40.50,
    "max_lat": 40.92,
}

def is_within_nyc(lon, lat):
    return (
        NYC_BOUNDS["min_lon"] < lon < NYC_BOUNDS["max_lon"] and
        NYC_BOUNDS["min_lat"] < lat < NYC_BOUNDS["max_lat"]
    )

geolocator = Nominatim(user_agent="taxi_fare_app")

# ---------------------------------------------------------
# 4. SESSION STATE
# ---------------------------------------------------------

for key in ["pickup_lat", "pickup_lon", "dropoff_lat", "dropoff_lon"]:
    if key not in st.session_state:
        st.session_state[key] = DEFAULT_LAT if "lat" in key else DEFAULT_LON

# ---------------------------------------------------------
# 5. UI TITLE
# ---------------------------------------------------------

st.title("🚕 TaxiFareNY — Fare Estimator")
st.markdown("Select pickup and dropoff directly on the maps below.")

# ---------------------------------------------------------
# 6. SIDEBAR (FIXED)
# ---------------------------------------------------------

with st.sidebar:

    st.header("🚗 Ride Details")

    now = datetime.datetime.now()

    date_data = st.date_input(
        "Date",
        value=now.date(),
        min_value=now.date()
    )

    minutes_to_next = (15 - (now.minute % 15)) % 15
    rounded_time = (now + datetime.timedelta(minutes=minutes_to_next)).replace(second=0, microsecond=0)

    time_data = st.time_input(
        "Time",
        value=rounded_time.time(),
        step=60*15
    )

    dt_raw = datetime.datetime.combine(date_data, time_data)
    dt_valid = dt_raw >= now

    if not dt_valid:
        st.error("Time must be in the future.")

    pickup_datetime_formatted = dt_raw.strftime("%Y-%m-%d %H:%M:%S")

    passenger_count = st.slider("Passengers", 1, 8, 2)

# ---------------------------------------------------------
# 7. TWO MAPS
# ---------------------------------------------------------

col1, col2 = st.columns(2)

# ---- PICKUP MAP ----
with col1:
    st.subheader("📍 Pickup Location")

    fmap_pick = folium.Map(
        location=[st.session_state["pickup_lat"], st.session_state["pickup_lon"]],
        zoom_start=12,
        tiles="CartoDB Positron",
    )

    folium.Marker(
        [st.session_state["pickup_lat"], st.session_state["pickup_lon"]],
        tooltip="Pickup",
        icon=folium.Icon(color="green")
    ).add_to(fmap_pick)

    fmap_pick.add_child(folium.LatLngPopup())

    pick_state = st_folium(fmap_pick, height=250, width=450)

    if pick_state and pick_state.get("last_clicked"):
        lat = pick_state["last_clicked"]["lat"]
        lon = pick_state["last_clicked"]["lng"]

        if is_within_nyc(lon, lat):
            st.session_state["pickup_lat"] = lat
            st.session_state["pickup_lon"] = lon
        else:
            st.error("Selected pickup is outside NYC.")

    try:
        loc = geolocator.reverse(f"{st.session_state['pickup_lat']}, {st.session_state['pickup_lon']}")
        st.caption(f"📨 Address: {loc.address if loc else 'Not found'}")
    except:
        st.caption("Address lookup unavailable.")

# ---- DROPOFF MAP ----
with col2:
    st.subheader("🏁 Dropoff Location")

    fmap_drop = folium.Map(
        location=[st.session_state["dropoff_lat"], st.session_state["dropoff_lon"]],
        zoom_start=12,
        tiles="CartoDB Positron",
    )

    folium.Marker(
        [st.session_state["dropoff_lat"], st.session_state["dropoff_lon"]],
        tooltip="Dropoff",
        icon=folium.Icon(color="red")
    ).add_to(fmap_drop)

    fmap_drop.add_child(folium.LatLngPopup())

    drop_state = st_folium(fmap_drop, height=250, width=450)

    if drop_state and drop_state.get("last_clicked"):
        lat = drop_state["last_clicked"]["lat"]
        lon = drop_state["last_clicked"]["lng"]

        if is_within_nyc(lon, lat):
            st.session_state["dropoff_lat"] = lat
            st.session_state["dropoff_lon"] = lon
        else:
            st.error("Selected dropoff is outside NYC.")

    try:
        loc = geolocator.reverse(f"{st.session_state['dropoff_lat']}, {st.session_state['dropoff_lon']}")
        st.caption(f"📨 Address: {loc.address if loc else 'Not found'}")
    except:
        st.caption("Address lookup unavailable.")

# ---------------------------------------------------------
# 8. ESTIMATE FARE API CALL
# ---------------------------------------------------------

center = st.container()
with center:
    if st.button("Estimate Fare", type="primary"):

        if not dt_valid:
            st.error("Please select a valid future time.")
        elif not is_within_nyc(st.session_state["pickup_lon"], st.session_state["pickup_lat"]):
            st.error("Pickup outside NYC.")
        elif not is_within_nyc(st.session_state["dropoff_lon"], st.session_state["dropoff_lat"]):
            st.error("Dropoff outside NYC.")
        else:
            params = {
                "pickup_datetime": pickup_datetime_formatted,
                "pickup_longitude": st.session_state["pickup_lon"],
                "pickup_latitude": st.session_state["pickup_lat"],
                "dropoff_longitude": st.session_state["dropoff_lon"],
                "dropoff_latitude": st.session_state["dropoff_lat"],
                "passenger_count": passenger_count
            }

            try:
                resp = requests.get(API_URL, params=params, timeout=10)
                if resp.status_code == 200:
                    result = resp.json()
                    fare = result.get("fare")

                    if fare is not None:
                        st.success(f"Estimated Fare: **${float(fare):.2f}**")
                    else:
                        st.error("No 'fare' in API response.")
                else:
                    st.error(f"API error {resp.status_code}")
            except Exception as e:
                st.error(f"Network error: {e}")

# ---------------------------------------------------------
# END
# ---------------------------------------------------------
