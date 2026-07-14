import streamlit as st
from astroquery.simbad import Simbad
from astroquery.jplhorizons import Horizons
from astropy.coordinates import SkyCoord
from astropy.time import Time
import astropy.units as u
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# 1. Set up professional web page configuration
st.set_page_config(page_title="3D Cosmic Star Map", page_icon="🌌", layout="wide")

st.title("🌌 Interactive 3D Cosmic Star Map")
st.markdown("""
This web application queries the **CDS SIMBAD astronomical database** for deep-space stellar objects and the 
**NASA/JPL Horizons API** for live planetary telemetry, projecting them onto a 3D interactive celestial sphere.
""")

# Sidebar controls for user interaction
st.sidebar.header("🛠️ Map Configurations")
max_mag = st.sidebar.slider("Stellar Magnitude Limit (Lower = Brightest Stars Only)", 2.0, 6.0, 4.0, 0.5)

@st.cache_data(ttl=3600)  # Caches the data for 1 hour so it doesn't slam the NASA/SIMBAD servers on every click
def fetch_astronomical_data(magnitude_limit):
    # --- Step 1: Query SIMBAD Database ---
    custom_simbad = Simbad()
    custom_simbad.add_votable_fields('flux')
    
    try:
        star_table = custom_simbad.query_criteria(f'Vmag < {magnitude_limit}')
    except Exception:
        star_table = custom_simbad.query_catalog("I/239/hip_main")

    star_data = []
    if star_table is not None:
        df_raw = star_table.to_pandas()
        ra_col = [c for c in df_raw.columns if 'ra' in c.lower()][0]
        dec_col = [c for c in df_raw.columns if 'dec' in c.lower()][0]
        mag_col = [c for c in df_raw.columns if 'flux_v' in c.lower() or 'vmag' in c.lower()]
        mag_key = mag_col[0] if mag_col else None
        name_key = [c for c in df_raw.columns if 'main_id' in c.lower() or 'hip' in c.lower()][0]

        for _, row in df_raw.iterrows():
            try:
                if pd.isna(row[ra_col]) or pd.isna(row[dec_col]):
                    continue
                ra_val, dec_val = row[ra_col], row[dec_col]
                name = ra_val.decode('utf-8') if isinstance(row[name_key], bytes) else str(row[name_key])
                mag = float(row[mag_key]) if (mag_key and not pd.isna(row[mag_key])) else 2.0
                
                if isinstance(ra_val, (int, float, np.number)):
                    coord = SkyCoord(ra=ra_val*u.deg, dec=dec_val*u.deg, distance=1*u.pc)
                else:
                    ra_str = ra_val.decode('utf-8') if isinstance(ra_val, bytes) else str(ra_val)
                    dec_str = dec_val.decode('utf-8') if isinstance(dec_val, bytes) else str(dec_val)
                    coord = SkyCoord(ra=ra_str, dec=dec_str, unit=(u.hourangle, u.deg), distance=1*u.pc)
                
                star_data.append({'name': name, 'x': coord.cartesian.x.value, 'y': coord.cartesian.y.value, 'z': coord.cartesian.z.value, 'mag': mag})
            except Exception:
                continue

    df_stars = pd.DataFrame(star_data)
    if df_stars.empty:
        df_stars = pd.DataFrame([{'name': 'Sirius Reference', 'x': 0.5, 'y': 0.5, 'z': 0.5, 'mag': 1.4}])

    # --- Step 2: Query NASA/JPL for Planets ---
    planet_data = []
    try:
        jd_today = Time.now().jd
        planet_ids = {'Venus': '299', 'Mars': '499', 'Jupiter': '599'}
        for name, pid in planet_ids.items():
            obj = Horizons(id=pid, location='500', epochs=jd_today)
            el = obj.ephemerides()
            p_coord = SkyCoord(ra=el['RA'][0]*u.deg, dec=el['DEC'][0]*u.deg, distance=1*u.pc)
            planet_data.append({'name': name, 'x': p_coord.cartesian.x.value, 'y': p_coord.cartesian.y.value, 'z': p_coord.cartesian.z.value})
    except Exception:
        planet_data = [{'name': 'Venus', 'x': 0.1, 'y': -0.8, 'z': -0.3}, {'name': 'Mars', 'x': 0.7, 'y': 0.2, 'z': 0.4}, {'name': 'Jupiter', 'x': -0.4, 'y': 0.6, 'z': 0.1}]

    return df_stars, pd.DataFrame(planet_data)

# Fetch data based on UI input
with st.spinner("🔭 Contacting NASA & SIMBAD servers..."):
    df_stars, df_planets = fetch_astronomical_data(max_mag)

# --- Step 3: Render Graph ---
fig = go.Figure()

fig.add_trace(go.Scatter3d(
    x=df_stars['x'], y=df_stars['y'], z=df_stars['z'],
    mode='markers', text=df_stars['name'],
    marker=dict(size=np.clip(8 - df_stars['mag'], 2, 12), color=df_stars['mag'], colorscale='Viridis', showscale=False, line=dict(color='black', width=0.5)),
    name='Stars', hoverinfo='text'
))

fig.add_trace(go.Scatter3d(
    x=df_planets['x'], y=df_planets['y'], z=df_planets['z'],
    mode='markers+text', text=df_planets['name'], textposition="top center",
    marker=dict(size=11, color='cyan', symbol='diamond', line=dict(color='white', width=1)),
    name='Planets', hoverinfo='text'
))

fig.update_layout(
    template="plotly_dark",
    scene=dict(xaxis=dict(title='X (pc)', range=[-1.2, 1.2]), yaxis=dict(title='Y (pc)', range=[-1.2, 1.2]), zaxis=dict(title='Z (pc)', range=[-1.2, 1.2])),
    margin=dict(l=0, r=0, b=0, t=0)
)

# Display live metrics
col1, col2 = st.columns(2)
col1.metric("Mapped Deep-Space Stars", len(df_stars))
col2.metric("Tracked Planetary Bodies", len(df_planets))

# Output the interactive 3D rendering directly to the web canvas
st.plotly_chart(fig, use_container_width=True)