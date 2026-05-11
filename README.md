# Solarpotenzial Oberbayern

B2B lead generation tool that identifies commercial and industrial buildings in Oberbayern with the highest rooftop solar potential, by combining DWD sunshine data with Bavarian building footprints.

**Live app:** [Streamlit Community Cloud link — add after deployment]

---

## What it does

For each of the 23 Landkreise in Oberbayern, the pipeline:
1. Locates all commercial/industrial building footprints (from Hausumringe + Tatsächliche Nutzung)
2. Pre-filters to roofs ≥ 500 m²
3. Samples annual sunshine hours at each building centroid from a 10-year DWD mean raster
4. Scores each building: `score = roof_area_m2 × sun_hours_mean`
5. Keeps the top-10 per Landkreis → 230 leads total

The Streamlit app visualises these leads on an interactive map, provides a sortable table, and exports a CSV with Google Maps / Google Earth links.

---

## Data sources

| Source | Description | License |
|--------|-------------|---------|
| [DWD Open Data](https://opendata.dwd.de/climate_environment/CDC/grids_germany/annual/sunshine_duration/) | Annual sunshine duration grids (10 years, 1 km²) | Open |
| [Hausumringe Bayern](https://geodaten.bayern.de) | Building footprints for Oberbayern (~2.7M buildings) | [Geodaten Bayern](https://www.ldbv.bayern.de/produkte/kataster/gebaeude.html) |
| [Tatsächliche Nutzung Bayern](https://geodaten.bayern.de) | Land-use parcels per Landkreis (commercial zone filter) | [Geodaten Bayern](https://www.ldbv.bayern.de) |

Raw files are **not committed** (too large). See [data/raw/README.md](data/raw/README.md) for download instructions.

---

## Pipeline

Run scripts in order from the project root:

```bash
uv run python scripts/s1_mean_sunshine.py    # average 10 DWD annual grids → TIF
uv run python scripts/s2_reproject.py        # reproject to EPSG:25832
uv run python scripts/s3_clip_oberbayern.py  # clip to Oberbayern boundary
uv run python scripts/s4_percentile.py       # add sun-percentile band
uv run python scripts/s5_build_leads.py      # score buildings, top-10 per Landkreis
uv run python scripts/s6_overview_map.py     # generate static overview PNG
```

Outputs written to `data/processed/`. The five files required by the app are committed to the repo so you can run the Streamlit app without re-running the full pipeline.

---

## Run locally

```bash
uv run streamlit run app.py
```

---

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Select repo, branch `main`, main file `app.py`
4. Streamlit Cloud picks up `pyproject.toml` + `uv.lock` automatically

---

## Project structure

```
├── app.py                        # Streamlit app
├── pyproject.toml                # Dependencies (uv)
├── uv.lock
├── assets/
│   ├── siteco.png                # Fallbeispiel Google Earth screenshot
│   └── himolla.png
├── scripts/
│   ├── s1_mean_sunshine.py
│   ├── s2_reproject.py
│   ├── s3_clip_oberbayern.py
│   ├── s4_percentile.py
│   ├── s5_build_leads.py         # main lead-gen pipeline
│   └── s6_overview_map.py        # static map generation
└── data/
    ├── raw/                      # gitignored — see data/raw/README.md
    └── processed/                # committed outputs (leads, map, boundaries, raster)
```
