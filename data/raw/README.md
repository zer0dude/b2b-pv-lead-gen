# Raw Data Sources

All raw data files are excluded from version control due to file size.
Download them to the correct subdirectory before running the pipeline.

---

## 1. Sunshine Duration — DWD Annual Grids

**Destination:** `data/raw/sunshine-duration/`

**Format:** `.asc.gz` (ESRI ASCII Grid, gzipped)

**Download 10 most recent complete years from:**
```
https://opendata.dwd.de/climate_environment/CDC/grids_germany/annual/sunshine_duration/
```

Recommended years: 2015–2024 (files like `grids_germany_annual_sunshine_duration_201517.asc.gz`).
Note: the `17` suffix in filenames is a DWD version tag, not part of the year.

The `.asc.gz` files for 2015–2025 are tracked in git (≈4 MB total) — already present.

---

## 2. Building Outlines — Hausumringe Oberbayern

**Destination:** `data/raw/hausumringe/`

**File:** `091_Oberbayern_Hausumringe.zip` → extracts to `hausumringe.shp` + sidecar files

**Download from:**
```
https://geodaten.bayern.de/opengeodata/OpenDataList/list.html
```
Search for "Hausumringe" and select the Oberbayern (Regierungsbezirk 091) download.

**Projection:** ETRS89 / UTM Zone 32N (EPSG:25832)

**Note:** This dataset contains building outline polygons with only one attribute: `ags`
(Amtlicher Gemeindeschlüssel — 9-digit municipality key). It does NOT contain
`gebaeudefunktion` codes. Commercial/industrial building identification relies entirely
on spatial overlap with Tatsächliche Nutzung zones (see below).

---

## 3. Land Use — Tatsächliche Nutzung Bayern (per Landkreis)

**Destination:** `data/raw/tatsaechliche-nutzung/`

**Files:** One ZIP per Landkreis, e.g. `tn_09161.zip` through `tn_09190.zip`
(all 23 Oberbayern Landkreise + kreisfreie Städte)

**Download from:**
```
https://geodaten.bayern.de/opengeodata/OpenDataList/list.html
```
Search for "Tatsächliche Nutzung" and download all districts with AGS starting `091`.

**Key attribute:** `nutzart` (text) — commercial/industrial targets:
- `Industrie- und Gewerbefläche`
- `Fläche besonderer funktionaler Prägung`
- `Fläche gemischter Nutzung` (optional, mixed-use zones)

**Projection:** ETRS89 / UTM Zone 32N (EPSG:25832)

---

## 4. Administrative Boundaries

For Regierungsbezirk and Landkreis display/filtering in the Streamlit app, download the
BKG Verwaltungseinheit shapefile for Bavaria from:
```
https://gdz.bkg.bund.de/index.php/default/digitale-geodaten/verwaltungsgebiete.html
```
or the LDBV open geodata portal. The Landkreis code can also be derived from the first
5 digits of the `ags` field in Hausumringe.
