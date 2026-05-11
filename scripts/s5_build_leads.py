"""
Step 5 (revised): Full-Oberbayern commercial building leads.

For each of 23 Landkreise + kreisfreie Städte:
  1. Load TN commercial zones (Industrie/Gewerbe + funktionale Prägung)
  2. Bbox-read buildings from Hausumringe; confirm ownership via AGS
  3. Pre-filter: roof_area_m2 >= 500 (eliminates ~85% cheaply, before spatial join)
  4. Centroid-within join: keep buildings whose centroid falls in a commercial zone
  5. Sample sun_hours + sun_percentile from raster at each centroid
  6. Score = roof_area_m2 × sun_hours_mean
  7. Top 10 per Landkreis

Inputs:  data/processed/sunshine_mean_ob.tif   (Band1=sun_hours, Band2=sun_pct)
         data/raw/hausumringe/hausumringe.shp
         data/raw/tatsaechliche-nutzung/tn_*/Nutzung.shp

Outputs: data/processed/leads.geojson              (up to 230 rows, WGS84 points)
         data/processed/ranked_leads_oberbayern.csv (same, no geometry)

Run:  uv run python scripts/s5_build_leads.py
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd
import rasterio

ROOT = Path(__file__).parent.parent
TIF = ROOT / "data" / "processed" / "sunshine_mean_ob.tif"
HAUSUMRINGE = ROOT / "data" / "raw" / "hausumringe" / "hausumringe.shp"
TN_ROOT = ROOT / "data" / "raw" / "tatsaechliche-nutzung"
OUT_GEOJSON = ROOT / "data" / "processed" / "leads.geojson"
OUT_CSV = ROOT / "data" / "processed" / "ranked_leads_oberbayern.csv"

COMMERCIAL_NUTZART = {
    "Industrie- und Gewerbefläche",
    "Fläche besonderer funktionaler Prägung",
}
MIN_ROOF_AREA_M2 = 500
TOP_N = 10

AGS_TO_LK_NAME = {
    "09161": "Ingolstadt (Stadt)",
    "09162": "München (Stadt)",
    "09163": "Rosenheim (Stadt)",
    "09171": "Altötting",
    "09172": "Berchtesgadener Land",
    "09173": "Bad Tölz-Wolfratshausen",
    "09174": "Dachau",
    "09175": "Ebersberg",
    "09176": "Eichstätt",
    "09177": "Erding",
    "09178": "Freising",
    "09179": "Fürstenfeldbruck",
    "09180": "Garmisch-Partenkirchen",
    "09181": "Landsberg am Lech",
    "09182": "Miesbach",
    "09183": "Mühldorf a.Inn",
    "09184": "München (Lkr)",
    "09185": "Neuburg-Schrobenhausen",
    "09186": "Pfaffenhofen a.d.Ilm",
    "09187": "Rosenheim (Lkr)",
    "09188": "Starnberg",
    "09189": "Traunstein",
    "09190": "Weilheim-Schongau",
}


def lk_id_from_ags(ags_int) -> str:
    """Extract 5-digit Landkreis AGS from a building's integer ags field."""
    return f"{int(ags_int):08d}"[:5]


def process_landkreis(lk_id: str, tn_path: Path, raster_src) -> gpd.GeoDataFrame | None:
    lk_name = AGS_TO_LK_NAME.get(lk_id, lk_id)

    # --- TN commercial zones ---
    tn = gpd.read_file(tn_path)
    commercial = tn[tn["nutzart"].isin(COMMERCIAL_NUTZART)].copy()
    if commercial.empty:
        print(f"  {lk_name}: no commercial zones — skip")
        return None

    # Use full TN file bounds to bbox-read buildings (covers whole district)
    lk_bounds = tuple(tn.total_bounds)  # (minx, miny, maxx, maxy)

    # --- Buildings: bbox read + AGS filter to this exact district ---
    buildings = gpd.read_file(HAUSUMRINGE, bbox=lk_bounds)
    if buildings.empty:
        print(f"  {lk_name}: no buildings in bbox — skip")
        return None

    buildings = buildings.copy()
    buildings["lk_from_ags"] = buildings["ags"].apply(lk_id_from_ags)
    buildings = buildings[buildings["lk_from_ags"] == lk_id]
    if buildings.empty:
        print(f"  {lk_name}: no buildings with matching AGS — skip")
        return None

    # --- Pre-filter by roof area (cheap, eliminates most buildings) ---
    buildings["roof_area_m2"] = buildings.geometry.area
    buildings = buildings[buildings["roof_area_m2"] >= MIN_ROOF_AREA_M2]
    if buildings.empty:
        print(f"  {lk_name}: no buildings >= {MIN_ROOF_AREA_M2} m2 — skip")
        return None

    print(f"  {lk_name}: {len(buildings):,} bldgs >= {MIN_ROOF_AREA_M2} m2 "
          f"(from {lk_bounds[0]:.0f},{lk_bounds[1]:.0f} bbox)", end=" ... ")

    # --- Centroid-within commercial zone (faster than full polygon intersect) ---
    bld_c = buildings[["ags", "roof_area_m2", "geometry"]].copy()
    bld_c["geometry"] = buildings.geometry.centroid

    bld = gpd.sjoin(bld_c, commercial[["geometry"]], how="inner", predicate="within")
    bld = bld[~bld.index.duplicated(keep="first")]

    if bld.empty:
        print(f"0 in commercial zones")
        return None

    # Restore original polygon geometry for area accuracy
    bld = bld.drop(columns=["index_right"], errors="ignore")
    bld["geometry"] = buildings.loc[bld.index, "geometry"]

    # --- Sample raster at building centroids ---
    centroids = buildings.loc[bld.index, "geometry"].centroid
    coords = [(pt.x, pt.y) for pt in centroids]
    sampled = list(raster_src.sample(coords))
    bld["sun_hours_mean"] = [float(v[0]) for v in sampled]
    bld["sun_percentile"] = [float(v[1]) for v in sampled]

    # Drop buildings where raster returned nodata (edge of clipped area)
    bld = bld[bld["sun_hours_mean"] > 0]
    if bld.empty:
        print(f"0 with valid sun data")
        return None

    # --- Score and top-N ---
    bld["score"] = bld["roof_area_m2"] * bld["sun_hours_mean"]
    top = bld.nlargest(TOP_N, "score").copy()

    top["landkreis_id"] = lk_id
    top["landkreis_name"] = lk_name

    print(f"{len(bld):,} commercial  |  "
          f"top score={top['score'].max():,.0f}  "
          f"(roof={top['roof_area_m2'].max():.0f} m2, "
          f"sun={top['sun_hours_mean'].max():.0f} h/yr)")
    return top


def main():
    for path, name in [(TIF, "sunshine_mean_ob.tif"), (HAUSUMRINGE, "hausumringe.shp")]:
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {name}")

    tn_dirs = sorted(p for p in TN_ROOT.glob("tn_*") if p.is_dir())
    if not tn_dirs:
        raise FileNotFoundError(f"No TN directories found in {TN_ROOT}")

    print(f"Processing {len(tn_dirs)} Landkreise...\n")

    results = []
    with rasterio.open(TIF) as raster_src:
        for tn_dir in tn_dirs:
            lk_id = tn_dir.name.replace("tn_", "")
            tn_path = tn_dir / "Nutzung.shp"
            if not tn_path.exists():
                continue
            top = process_landkreis(lk_id, tn_path, raster_src)
            if top is not None:
                results.append(top)

    if not results:
        print("\nERROR: no leads found in any Landkreis")
        return

    leads = gpd.GeoDataFrame(pd.concat(results, ignore_index=True), crs="EPSG:25832")
    print(f"\nTotal: {len(leads)} leads across {leads['landkreis_name'].nunique()} Landkreise")

    # --- Centroids to WGS84 ---
    pts = leads.copy()
    pts["geometry"] = leads.geometry.centroid
    pts = pts.to_crs("EPSG:4326")
    pts["lat"] = pts.geometry.y.round(6)
    pts["lon"] = pts.geometry.x.round(6)
    pts["maps_url"] = pts.apply(
        lambda r: f"https://maps.google.com/?q={r['lat']},{r['lon']}", axis=1)
    pts["earth_url"] = pts.apply(
        lambda r: f"https://earth.google.com/web/@{r['lat']},{r['lon']},500a,35y,0h,0t,0r",
        axis=1)

    pts = pts.sort_values("score", ascending=False).reset_index(drop=True)
    pts["rank"] = pts.index + 1

    # --- Save ---
    OUT_GEOJSON.parent.mkdir(parents=True, exist_ok=True)
    pts.to_file(OUT_GEOJSON, driver="GeoJSON")
    print(f"Saved: {OUT_GEOJSON}  ({OUT_GEOJSON.stat().st_size / 1024:.0f} KB)")

    csv_cols = ["rank", "landkreis_id", "landkreis_name", "ags",
                "roof_area_m2", "sun_hours_mean", "sun_percentile", "score",
                "lat", "lon", "maps_url", "earth_url"]
    pts[[c for c in csv_cols if c in pts.columns]].to_csv(OUT_CSV, index=False)
    print(f"Saved: {OUT_CSV}  ({OUT_CSV.stat().st_size / 1024:.0f} KB)")

    # --- Summary table ---
    print(f"\nTop leads overall (score = roof_area_m2 x sun_hours_mean):")
    print(f"{'Rank':<5} {'Landkreis':<26} {'Roof m2':>8} {'Sun h/yr':>9} {'Sun pct':>8} {'Score':>12}")
    print("-" * 75)
    for _, row in pts.head(15).iterrows():
        print(f"  {int(row['rank']):<4} {row['landkreis_name'][:24]:<24}  "
              f"{row['roof_area_m2']:>8.0f}  {row['sun_hours_mean']:>8.0f}  "
              f"{row['sun_percentile']:>7.1f}  {row['score']:>12.0f}")

    print(f"\nPer-Landkreis top building:")
    per_lk = pts.groupby("landkreis_name").first().sort_values("score", ascending=False)
    for lk_name, row in per_lk.iterrows():
        print(f"  {lk_name[:26]:<26}  roof={row['roof_area_m2']:.0f} m2  "
              f"sun={row['sun_hours_mean']:.0f} h/yr  score={row['score']:.0f}")


if __name__ == "__main__":
    main()
