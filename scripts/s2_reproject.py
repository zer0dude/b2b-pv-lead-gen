"""
Step 2: Reproject sunshine mean raster from EPSG:31467 to EPSG:25832.

Input:  data/processed/s1_mean_sunshine_raw.tif
Output: data/processed/s2_reprojected.tif  (single-band float32, EPSG:25832)

Run:  uv run python scripts/s2_reproject.py
"""

from pathlib import Path

import numpy as np
import rasterio
import rasterio.warp
from rasterio.crs import CRS
from rasterio.enums import Resampling

ROOT = Path(__file__).parent.parent
IN = ROOT / "data" / "processed" / "s1_mean_sunshine_raw.tif"
OUT = ROOT / "data" / "processed" / "s2_reprojected.tif"
DST_CRS = CRS.from_epsg(25832)


def main():
    if not IN.exists():
        raise FileNotFoundError(f"Run s1_mean_sunshine.py first: {IN}")

    with rasterio.open(IN) as src:
        print(f"Input:  {IN}")
        print(f"  CRS:    {src.crs}")
        print(f"  Shape:  {src.height} x {src.width}")
        print(f"  Bounds: {src.bounds}")

        dst_transform, dst_width, dst_height = rasterio.warp.calculate_default_transform(
            src.crs, DST_CRS,
            src.width, src.height,
            *src.bounds,   # left, bottom, right, top
        )
        print(f"\nTarget transform: {dst_transform}")
        print(f"Target shape:     {dst_height} x {dst_width}")

        dst_arr = np.full((dst_height, dst_width), np.nan, dtype=np.float32)

        rasterio.warp.reproject(
            source=rasterio.band(src, 1),
            destination=dst_arr,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=dst_transform,
            dst_crs=DST_CRS,
            resampling=Resampling.bilinear,
            src_nodata=np.nan,
            dst_nodata=np.nan,
        )

    valid = int(np.sum(~np.isnan(dst_arr)))
    print(f"\nReprojected: {dst_height} x {dst_width}, valid={valid:,} cells")
    print(f"Range: [{np.nanmin(dst_arr):.0f}, {np.nanmax(dst_arr):.0f}] h/yr")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        OUT, "w",
        driver="GTiff",
        height=dst_height, width=dst_width,
        count=1, dtype="float32",
        crs=DST_CRS,
        transform=dst_transform,
        nodata=np.nan,
        compress="lzw",
    ) as dst:
        dst.write(dst_arr, 1)

    size_kb = OUT.stat().st_size / 1024
    print(f"\nSaved: {OUT}  ({size_kb:.0f} KB)")

    with rasterio.open(OUT) as check:
        print(f"Re-opened CRS: {check.crs}")
        print(f"Bounds: {check.bounds}")


if __name__ == "__main__":
    main()
