"""
Step 3: Clip reprojected raster to Oberbayern boundary.

Derives the boundary from the union of all 23 Tatsaechliche Nutzung district shapefiles
and caches it as data/processed/oberbayern_boundary.gpkg so it only runs once.

Input:  data/processed/s2_reprojected.tif
        data/raw/tatsaechliche-nutzung/tn_*/Nutzung.shp  (23 districts)
Output: data/processed/oberbayern_boundary.gpkg  (cached boundary, EPSG:25832)
        data/processed/s3_clipped_ob.tif  (clipped raster, EPSG:25832)

Run:  uv run python scripts/s3_clip_oberbayern.py
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import rasterio.mask
from shapely.ops import unary_union as shapely_union

ROOT = Path(__file__).parent.parent
IN = ROOT / "data" / "processed" / "s2_reprojected.tif"
BOUNDARY_CACHE = ROOT / "data" / "processed" / "oberbayern_boundary.gpkg"
OUT = ROOT / "data" / "processed" / "s3_clipped_ob.tif"
TN_ROOT = ROOT / "data" / "raw" / "tatsaechliche-nutzung"


def build_or_load_boundary() -> gpd.GeoDataFrame:
    if BOUNDARY_CACHE.exists():
        print(f"Loading cached boundary: {BOUNDARY_CACHE}")
        return gpd.read_file(BOUNDARY_CACHE)

    print("Building Oberbayern boundary from Tatsaechliche Nutzung (this runs once)...")
    polys = []
    for shp in sorted(TN_ROOT.glob("tn_*/Nutzung.shp")):
        gdf = gpd.read_file(shp)
        poly = gdf.geometry.union_all()
        polys.append(poly)
        print(f"  {shp.parent.name}: {len(gdf):,} parcels -> dissolved")

    boundary_poly = shapely_union(polys)
    print(f"  Result geometry type: {boundary_poly.geom_type}")

    boundary_gdf = gpd.GeoDataFrame(
        [{"district": "Oberbayern"}],
        geometry=[boundary_poly],
        crs="EPSG:25832",
    )
    BOUNDARY_CACHE.parent.mkdir(parents=True, exist_ok=True)
    boundary_gdf.to_file(BOUNDARY_CACHE, driver="GPKG")
    size_kb = BOUNDARY_CACHE.stat().st_size / 1024
    print(f"  Saved boundary cache: {BOUNDARY_CACHE}  ({size_kb:.0f} KB)")
    return boundary_gdf


def main():
    if not IN.exists():
        raise FileNotFoundError(f"Run s2_reproject.py first: {IN}")

    boundary_gdf = build_or_load_boundary()
    boundary_poly = boundary_gdf.geometry.iloc[0]

    with rasterio.open(IN) as src:
        print(f"\nInput raster:  {IN}")
        print(f"  CRS:    {src.crs}")
        print(f"  Shape:  {src.height} x {src.width}")
        print(f"  Bounds: {src.bounds}")
        print(f"Boundary bounds: {boundary_poly.bounds}")

        clipped, clip_transform = rasterio.mask.mask(
            src,
            [boundary_poly],
            crop=True,
            nodata=np.nan,
            all_touched=False,
        )

    clipped_arr = clipped[0]
    valid = int(np.sum(~np.isnan(clipped_arr)))
    print(f"\nClipped: {clipped_arr.shape}, valid={valid:,} cells")
    print(f"Range:   [{np.nanmin(clipped_arr):.0f}, {np.nanmax(clipped_arr):.0f}] h/yr")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        OUT, "w",
        driver="GTiff",
        height=clipped_arr.shape[0], width=clipped_arr.shape[1],
        count=1, dtype="float32",
        crs="EPSG:25832",
        transform=clip_transform,
        nodata=np.nan,
        compress="lzw",
    ) as dst:
        dst.write(clipped_arr, 1)

    size_kb = OUT.stat().st_size / 1024
    print(f"\nSaved: {OUT}  ({size_kb:.0f} KB)")

    with rasterio.open(OUT) as check:
        print(f"Re-opened CRS: {check.crs}")
        print(f"Bounds: {check.bounds}")


if __name__ == "__main__":
    main()
