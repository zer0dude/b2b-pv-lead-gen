"""
Solarpotenzial Oberbayern — Streamlit App

Run:  uv run streamlit run app.py
"""

import geopandas as gpd
import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st
from pathlib import Path

LEADS_PATH = Path("data/processed/leads.geojson")
MAP_PATH = Path("data/processed/overview_map.png")
SITECO_PATH = Path("assets/siteco.png")

st.set_page_config(
    layout="wide",
    page_title="Solarpotenzial Oberbayern",
    page_icon="☀️",
)


@st.cache_data
def load_leads(mtime: float) -> pd.DataFrame:
    gdf = gpd.read_file(LEADS_PATH)
    df = gdf.drop(columns="geometry").copy()
    df["lat"] = gdf.geometry.y
    df["lon"] = gdf.geometry.x
    return df


def rdylgn_rgb(pct_values: np.ndarray) -> list[list[int]]:
    """Map 0–100 percentile to RdYlGn RGB triples."""
    import matplotlib.pyplot as plt
    cmap = plt.cm.RdYlGn
    rgba = cmap(pct_values / 100.0)
    return [[int(r * 255), int(g * 255), int(b * 255), 210]
            for r, g, b, _ in rgba]


# ── Guard: data must exist ──────────────────────────────────────────────────
if not LEADS_PATH.exists():
    st.error("leads.geojson nicht gefunden. Bitte zuerst `uv run python scripts/s5_build_leads.py` ausführen.")
    st.stop()

df_all = load_leads(LEADS_PATH.stat().st_mtime)

# ── Section 1: Einleitung ───────────────────────────────────────────────────
st.title("Oberbayerns ungenutzte Solarpotenziale")

st.markdown("""
Gewerbliche und industrielle Gebäude verfügen häufig über große, ungenutzte Dachflächen,
die sich ideal für Photovoltaikanlagen eignen. Durch die Kombination öffentlich zugänglicher
Daten — der Sonnenscheindauer des **[Deutschen Wetterdienstes (DWD)](https://opendata.dwd.de)**
und der Gebäude- und Nutzungsdaten von **[Geodaten Bayern](https://geodaten.bayern.de)** —
lassen sich Gebäude identifizieren, die aufgrund ihrer Dachfläche und Sonnenstunden
das größte Solarpotenzial aufweisen. Diese Anwendung analysiert alle 23 Landkreise Oberbayerns.
""")

st.divider()

# ── Section 2: Übersichtskarte ──────────────────────────────────────────────
st.subheader("Übersichtskarte: Solarpotenzial in Oberbayern")
if MAP_PATH.exists():
    st.image(str(MAP_PATH), use_container_width=True)
    st.caption(
        "Hintergrund: DWD-Sonnenscheindaten (10-Jahres-Durchschnitt 2015–2024). "
        "Punkte: Top-10-Gebäude pro Landkreis nach Score (Dachfläche × Sonnenstunden)."
    )
else:
    st.warning("Übersichtskarte nicht gefunden. Bitte `uv run python scripts/s6_overview_map.py` ausführen.")

st.divider()

# ── Section 3: Fallbeispiel Siteco ─────────────────────────────────────────
st.subheader("Fallbeispiel: Ungenutztes Solarpotenzial")

siteco_rows = df_all[df_all["rank"] == 12]
siteco = siteco_rows.iloc[0] if not siteco_rows.empty else df_all.iloc[0]

col_img, col_text = st.columns([1, 1])

with col_img:
    if SITECO_PATH.exists():
        st.image(
            str(SITECO_PATH),
            caption="Google Earth — Siteco, Ldkr. Traunstein (07.08.2025)",
            use_container_width=True,
        )

with col_text:
    earth_url = siteco["earth_url"] if "earth_url" in df_all.columns else siteco["maps_url"]

    st.markdown(f"""
**Siteco** im Landkreis Traunstein verfügt über eine Dachfläche von ca.
**{siteco['roof_area_m2']:,.0f} m²** und liegt in einer Region mit
**{siteco['sun_hours_mean']:.0f} Sonnenstunden pro Jahr**.

Mit einem Solarpotenzial-Score von **{siteco['score']:,.0f}** (Dachfläche × Sonnenstunden)
gehört dieses Gebäude zu den attraktivsten Standorten in ganz Oberbayern.

Ein Google-Earth-Luftbild vom **07.08.2025** zeigt keine Photovoltaikanlage auf dem Dach.
Dieses Muster wiederholt sich bei zahlreichen der identifizierten Gebäude — und stellt
die zentrale Frage: Warum bleibt das Potenzial ungenutzt, und könnte eine
Finanzierungslösung die Lücke schließen?
""")

    btn1, btn2 = st.columns(2)
    btn1.link_button("Google Maps öffnen", siteco["maps_url"], use_container_width=True)
    btn2.link_button("Google Earth öffnen", earth_url, use_container_width=True)

st.divider()

# ── Section 4: Interaktive Karte ────────────────────────────────────────────
st.subheader("Karte: Alle Gebäude erkunden")

df_map = df_all.copy()
score_pct = df_map["score"].rank(pct=True) * 100
colors = rdylgn_rgb(score_pct.values)
df_map["color"] = colors
df_map["roof_disp"] = df_map["roof_area_m2"].round(0).astype(int)
df_map["sun_disp"] = df_map["sun_hours_mean"].round(0).astype(int)
df_map["score_str"] = df_map["score"].round(0).astype(int).apply(lambda x: f"{x:,}")

layer = pdk.Layer(
    "ScatterplotLayer",
    data=df_map,
    get_position=["lon", "lat"],
    get_fill_color="color",
    get_radius=100,
    radius_min_pixels=4,
    radius_max_pixels=8,
    pickable=True,
    auto_highlight=True,
)

view = pdk.ViewState(
    latitude=df_map["lat"].mean(),
    longitude=df_map["lon"].mean(),
    zoom=8,
    pitch=0,
)

tooltip = {
    "text": (
        "Rang {rank} — {landkreis_name}\n"
        "Dachfläche: {roof_disp} m²\n"
        "Sonnenstunden: {sun_disp} h/Jahr\n"
        "Score: {score_str}"
    )
}

deck = pdk.Deck(
    layers=[layer],
    initial_view_state=view,
    map_provider="carto",
    map_style=pdk.map_styles.CARTO_LIGHT,
    tooltip=tooltip,
)
st.pydeck_chart(deck, use_container_width=True)
st.caption("Punktfarbe: grün = hoher Score, rot = niedriger Score. Hover für Details und Maps-Link.")

st.divider()

# ── Section 5: Datentabelle ─────────────────────────────────────────────────
st.subheader("Top-10 Gebäude pro Landkreis in Oberbayern")
st.caption("Sortierbar nach jeder Spalte. Klicken Sie auf die Links für Luftbilder.")

display_cols = {
    "rank": "Rang",
    "landkreis_name": "Landkreis",
    "roof_area_m2": "Dachfläche (m²)",
    "sun_hours_mean": "Sonnenstunden (h/Jahr)",
    "score": "Score",
    "maps_url": "Google Maps",
}
if "earth_url" in df_all.columns:
    display_cols["earth_url"] = "Google Earth"

table_df = df_all.sort_values("rank")[list(display_cols.keys())].rename(columns=display_cols).copy()
table_df["Dachfläche (m²)"] = table_df["Dachfläche (m²)"].round(0).astype(int)
table_df["Sonnenstunden (h/Jahr)"] = table_df["Sonnenstunden (h/Jahr)"].round(0).astype(int)
table_df["Score"] = table_df["Score"].round(0).astype(int)

col_config = {
    "Google Maps": st.column_config.LinkColumn(display_text="Maps"),
    "Dachfläche (m²)": st.column_config.NumberColumn(format="%d"),
    "Score": st.column_config.NumberColumn(format="%d"),
}
if "earth_url" in df_all.columns:
    col_config["Google Earth"] = st.column_config.LinkColumn(display_text="Earth")

st.dataframe(
    table_df,
    column_config=col_config,
    use_container_width=True,
    height=600,
)

st.divider()

# ── Section 6: Export ───────────────────────────────────────────────────────
st.subheader("Exportieren")

csv_cols = ["rank", "landkreis_name", "roof_area_m2", "sun_hours_mean",
            "score", "lat", "lon", "maps_url", "earth_url"]
csv_data = df_all.sort_values("rank")[[c for c in csv_cols if c in df_all.columns]].to_csv(index=False)

st.download_button(
    label="CSV herunterladen",
    data=csv_data,
    file_name="solarpotenzial_oberbayern.csv",
    mime="text/csv",
    type="primary",
)
