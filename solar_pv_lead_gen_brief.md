# SolarLead Oberbayern — Project Brief
**B2B PV Sales Lead Generation via Solar & Building Data**
*Version 0.2 — Scope narrowed to Oberbayern (2025-05-11)*

---

## 1. Problem Statement

A B2B photovoltaic company operating in Bavaria wants to identify commercial and industrial buildings that are strong candidates for PV installation, based on two factors:
1. The building sits in a location with above-average annual sunshine hours
2. The building is large enough (roof area) to make a PV installation commercially viable

Currently, prospecting is manual and geography-blind. The goal is to build a data-driven pipeline that surfaces ranked, map-ready leads that a salesperson can act on with no technical knowledge.

---

## 2. Scope

- **Geography:** Oberbayern (Regierungsbezirk 091) — narrowed from full Bavaria
- **Target buildings:** Commercial and industrial only (no residential)
- **Output:** A Streamlit app with an interactive map of prioritised buildings, filterable and exportable as a Google My Maps–compatible CSV
- **Development stage:** Prototype — correctness and usability over performance

---

## 3. Data Sources

### 3.1 Solar Radiation — DWD Annual Sunshine Duration Grids

| Property | Detail |
|---|---|
| Provider | Deutscher Wetterdienst (DWD) — Climate Data Center |
| Dataset | Annual sunshine duration grids for Germany |
| Resolution | 1 km × 1 km raster |
| Format | ESRI ASCII Grid (`.asc`), gzipped |
| Projection | Gauss-Krüger Zone 3, EPSG:31467 |
| Unit | Hours per year (integer) |
| Coverage | 1951–present, one file per year |
| Licence | CC BY 4.0 |
| URL | `https://opendata.dwd.de/climate_environment/CDC/grids_germany/annual/sunshine_duration/` |
| Recommended download | 10 most recent complete years (e.g. 2015–2024) |
| Notes | Interpolated from DWD ground station network. Not satellite-derived. Circular interpolation artifacts visible near individual stations. Nodata = -999. Grid dimensions: 654 × 866 cells. |

### 3.2 Building Footprints — Hausumringe Oberbayern

| Property | Detail |
|---|---|
| Provider | Bayerisches Landesamt für Digitalisierung, Breitband und Vermessung (LDBV) |
| Dataset | Hausumringe (building outlines) — ALKIS-derived, Oberbayern only (`091_Oberbayern_Hausumringe.zip`) |
| Format | Shapefile |
| Projection | ETRS89 / UTM Zone 32N, EPSG:25832 |
| Key attributes | Building polygon geometry, `ags` (9-digit municipality key) |
| Record count | ~2.69 million buildings |
| Licence | CC BY 4.0 (open geodata Bayern) |
| URL | `https://geodaten.bayern.de/opengeodata/` |
| **Important** | **`gebaeudefunktion` is NOT present in Hausumringe** — this dataset contains only building outlines with the `ags` field. Commercial/industrial classification relies entirely on spatial overlap with Tatsächliche Nutzung zones (see §3.3). Roof area (polygon area in m²) is the primary per-building PV suitability signal. |

### 3.3 Land Use — Tatsächliche Nutzung Oberbayern (ALKIS)

| Property | Detail |
|---|---|
| Provider | LDBV Bayern |
| Dataset | Tatsächliche Nutzung (actual land use polygons), one ZIP per Landkreis (`tn_09161.zip` … `tn_09190.zip`, 23 districts) |
| Format | Shapefile |
| Projection | ETRS89 / UTM Zone 32N, EPSG:25832 |
| Key attributes | `nutzart` (text field, e.g. `"Industrie- und Gewerbefläche"`) |
| Licence | CC BY 4.0 |
| URL | `https://geodaten.bayern.de/opengeodata/` |
| Relevant values | `Industrie- und Gewerbefläche`, `Fläche besonderer funktionaler Prägung`, optionally `Fläche gemischter Nutzung` |
| Notes | Field is named `nutzart` (not `nutzungsart`), stores full German text (Latin-1 encoding). **This is the sole mechanism for identifying commercial/industrial zones**, since Hausumringe has no function codes. Used both to pre-filter DWD cells AND to select buildings in Step 6. |

### 3.4 Administrative Boundaries — VerwaltungsEinheit Bayern

| Property | Detail |
|---|---|
| Provider | BKG / LDBV |
| Dataset | Administrative units (Gemeinde, Landkreis, Regierungsbezirk) |
| Format | Shapefile |
| Projection | ETRS89 / UTM Zone 32N, EPSG:25832 |
| Notes | Used for regional filtering and display context in the app. Already obtained. |

---

## 4. Processing Pipeline

### Overview

```
DWD .asc files (10 years)
        │
        ▼
[Step 1] Compute 10-year mean sunshine per 1 km cell
        │
        ▼
[Step 2] Reproject to EPSG:25832, clip to Bavaria boundary
        │
        ▼
[Step 3] Compute percentile rank per cell across Bavaria
        │
        ▼
[Step 4] Filter: keep cells above threshold (e.g. top 20%)
        │
        ├──────────────────────────┐
        ▼                          ▼
Tatsächliche Nutzung       Hausumringe buildings
        │                          │
        ▼                          ▼
[Step 5] Spatial join:     [Step 6] Filter by gebaeudefunktion
  keep only cells with       (commercial/industrial codes)
  commercial land use        Compute roof area (m²)
        │                          │
        └──────────┬───────────────┘
                   ▼
        [Step 7] Join buildings to their parent DWD cell
                   │
                   ▼
        [Step 8] Rank buildings by:
                   1. Cell sun percentile
                   2. Roof area (m²)
                   3. Combined score
                   │
                   ▼
        [Step 9] Compute building centroid (lat/lon WGS84)
                 Generate Google Maps search URL per building
                   │
                   ▼
        [Step 10] Export: ranked_leads_oberbayern.csv
                          + leads.geojson for Streamlit map
```

### Step Details

**Step 1 — Multi-year averaging**
- Load each `.asc` year file with `numpy`
- Replace nodata (-999) with `np.nan`
- Stack arrays, compute `nanmean` across years
- Output: single 654×866 float array of mean annual sunshine hours

**Step 2 — Reproject and clip**
- Assign EPSG:31467 to the raster (Gauss-Krüger zone 3)
- Reproject to EPSG:25832 using `rasterio.warp.reproject`
- Clip to Oberbayern boundary polygon (derived from the union of Tatsächliche Nutzung polygons, or from a BKG VerwaltungsEinheit download)

**Step 3–4 — Percentile ranking and threshold**
- Compute percentile rank of each valid cell across Bavaria
- Retain cells above configurable threshold (default: top 20%)
- Store `sun_hours_mean` and `sun_percentile` per cell

**Step 5 — Land use filter**
- Load Tatsächliche Nutzung shapefile with `geopandas`
- Dissolve relevant commercial/industrial Nutzungsart polygons
- Spatial intersect: for each candidate DWD cell, compute what fraction is commercial land use
- Discard cells where commercial fraction < configurable minimum (default: 30%)

**Step 6 — Building filter**
- Load Hausumringe shapefile (geometry + `ags` only — no function codes available)
- Compute `roof_area_m2` = polygon area in m² (already in metres, EPSG:25832)
- Apply minimum roof size filter (default: 500 m²)
- **Commercial/industrial identification is handled entirely via spatial overlay with Tatsächliche Nutzung zones** (Step 5): only buildings whose centroid or majority area falls within a `Industrie- und Gewerbefläche` / `Fläche besonderer funktionaler Prägung` polygon are retained

**Step 7–8 — Join and rank**
- Spatial join: assign each building to its DWD 1 km cell
- Merge building attributes with cell sun data
- Compute combined score: `score = 0.5 × sun_percentile + 0.5 × roof_area_percentile`
  *(weights configurable)*

**Step 9–10 — Export**
- Compute centroids, convert to WGS84 (EPSG:4326) for `lat`, `lon` columns
- Generate `maps_url = f"https://maps.google.com/?q={lat},{lon}"`
- Export `ranked_leads_bavaria.csv` and `leads.geojson`

### Key Libraries

```
numpy          # raster array operations
rasterio       # ASC read, reproject
geopandas      # shapefile read, spatial joins
pandas         # tabular processing
shapely        # geometry operations (via geopandas)
streamlit      # app framework
pydeck         # map rendering in Streamlit
```

---

## 5. Streamlit Application

### Purpose

Give a salesperson (non-technical) a way to:
1. Browse prioritised commercial buildings on a map
2. Filter by region and minimum criteria
3. Click through to Google Maps for any building
4. Export a filtered list for their territory

### Pages / Sections

#### 5.1 Overview Map
- Oberbayern map with all candidate buildings as dots, coloured by combined score (green = high, red = low)
- Hover tooltip: roof area, sun hours, Landkreis, maps URL
- Filter sidebar:
  - Regierungsbezirk / Landkreis selector
  - Minimum roof area slider (default 500 m²)
  - Minimum sun percentile slider (default 70th)
  - Score weighting slider: sun vs. roof area

#### 5.2 Top Leads Table
- Tabular view of top N buildings (default: top 100) filtered by sidebar settings
- Columns: Rank, Landkreis, Roof Area (m²), Sun Hours (mean), Sun Percentile, Score, Google Maps link
- Sortable by any column
- One-click Google Maps button per row (opens in new tab)

#### 5.3 Cell Detail View
- Click a DWD cell on the map → see all buildings within that cell
- Mini-table of buildings ranked by roof area
- Satellite basemap option to visually verify building type
- Sun hours chart: show the 10-year time series for that cell

#### 5.4 Export
- Download filtered results as CSV (Google My Maps–compatible format)
  - Required columns: `Name`, `Latitude`, `Longitude`, `Description`
  - Description field pre-populated with: roof area, sun hours, score, maps URL
- Instructions for importing into Google My Maps (brief tooltip/help text)

### Google My Maps CSV Format

The export must be directly importable into Google My Maps with no modification:

```csv
Name,Latitude,Longitude,Description
Building_12345,48.1234,11.5678,"Roof: 1240 m² | Sun: 1847 h/yr (92nd pct) | Score: 0.87 | https://maps.google.com/?q=48.1234,11.5678"
```

---

## 6. Key Design Decisions & Rationale

| Decision | Rationale |
|---|---|
| Oberbayern only | Narrowed from full Bavaria — reduces data volume and focusses the prototype; Oberbayern includes München metro + alpine fringe with strong sun exposure |
| 10-year DWD average | Smooths out anomalous years; more defensible solar potential claim |
| Roof area as PV proxy | More reliable than `gebaeudefunktion` codes; directly relevant to PV capacity |
| No business name lookup | Avoids API costs and data licensing; deferred to salesperson via Google Maps |
| Google My Maps output | Zero friction for sales team; familiar tool; no new software needed |
| Combined score (sun + roof) | Neither factor alone is sufficient; weighting configurable for different sales strategies |
| Top 20% sun threshold | Balances coverage vs. focus; configurable |
| 500 m² minimum roof | Rough threshold for commercially viable PV installation; configurable |

---

## 7. Out of Scope for Prototype

- Business/tenant name identification (no Places API, no commercial directory)
- LoD2 roof geometry (slope, orientation) — flat roof assumption
- Real-time or sub-annual solar data
- Regions outside Oberbayern (other Regierungsbezirke can be added later by downloading their Hausumringe + Tatsächliche Nutzung data)
- Economic modelling (ROI, payback period, grid connection)
- CRM integration
- User authentication

---

## 8. Suggested Development Sequence

1. **Data acquisition** — download 10 DWD annual grids, Hausumringe, Tatsächliche Nutzung for Oberbayern (all present in `data/raw/`)
2. **Pipeline script** — build `pipeline.py` that runs steps 1–10 and produces `leads.geojson` + `ranked_leads_bavaria.csv`
3. **Validate on one Landkreis** — run full pipeline on Rosenheim or München Land before scaling to all Oberbayern
4. **Streamlit app skeleton** — map + table + export, hardcoded to pre-processed output files
5. **Add sidebar filters** — make thresholds interactive
6. **End-to-end test with a salesperson** — observe what they click, what confuses them, what's missing
7. **Iterate** — refine ranking weights and filters based on feedback

---

## 9. Open Questions for Development

- What minimum roof area is commercially meaningful for this company's typical installation size?
- Should ranking weight sun hours or roof area more heavily? (configurable, but a sensible default is needed)
- Are there specific Landkreise or Regierungsbezirke to prioritise first?
- Is there an existing CRM that the CSV export should be formatted to feed into?
- Does the company have any existing customer data that could inform what "good" buildings look like (for calibrating the score)?

---

*Prepared as prototype development brief. All data sources are open/free. No proprietary data or paid APIs required for core functionality.*
