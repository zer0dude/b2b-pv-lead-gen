"""
Step 1: Load 10 DWD annual sunshine grids (2015-2024), replace nodata, compute mean.

Input:  data/raw/sunshine-duration/*201[5-9]17.asc.gz + *202[0-4]17.asc.gz
Output: data/processed/s1_mean_sunshine_raw.tif  (single-band float32, EPSG:31467)

Run:  uv run python scripts/s1_mean_sunshine.py
"""

import gzip
import re
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

ROOT = Path(__file__).parent.parent
SRC_DIR = ROOT / "data" / "raw" / "sunshine-duration"
OUT = ROOT / "data" / "processed" / "s1_mean_sunshine_raw.tif"
SRC_CRS = CRS.from_epsg(31467)


def year_from_path(p: Path) -> int:
    m = re.search(r"_(\d{4})\d{2}\.asc\.gz$", p.name)
    return int(m.group(1)) if m else 0


def load_asc_gz(path: Path) -> tuple[np.ndarray, object]:
    """Decompress and read an ASC.GZ file; return (float32 array, rasterio transform)."""
    with gzip.open(path, "rb") as gz:
        raw = gz.read()
    with MemoryFile(raw) as mf:
        with mf.open() as src:
            arr = src.read(1).astype(np.float32)
            transform = src.transform
            width, height = src.width, src.height
    arr[arr == -999] = np.nan
    return arr, transform


def main():
    gz_files = sorted(SRC_DIR.glob("*.asc.gz"))
    chosen = sorted([p for p in gz_files if 2015 <= year_from_path(p) <= 2024],
                    key=year_from_path)
    print(f"Found {len(chosen)} files for 2015-2024:")
    for p in chosen:
        print(f"  {p.name}")
    if len(chosen) != 10:
        raise RuntimeError(f"Expected 10 files, got {len(chosen)}")

    stack = []
    transform = None
    for p in chosen:
        arr, tf = load_asc_gz(p)
        stack.append(arr)
        if transform is None:
            transform = tf
        valid = int(np.sum(~np.isnan(arr)))
        print(f"  {year_from_path(p)}: {valid:,} valid cells  "
              f"range [{np.nanmin(arr):.0f}, {np.nanmax(arr):.0f}] h")

    mean_arr = np.nanmean(np.stack(stack, axis=0), axis=0)
    valid_total = int(np.sum(~np.isnan(mean_arr)))
    print(f"\nMean array: shape={mean_arr.shape}, valid={valid_total:,} cells")
    print(f"Range: [{np.nanmin(mean_arr):.0f}, {np.nanmax(mean_arr):.0f}] h/yr")
    print(f"Transform: {transform}")

    height, width = mean_arr.shape
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        OUT, "w",
        driver="GTiff",
        height=height, width=width,
        count=1, dtype="float32",
        crs=SRC_CRS,
        transform=transform,
        nodata=np.nan,
        compress="lzw",
    ) as dst:
        dst.write(mean_arr, 1)

    size_kb = OUT.stat().st_size / 1024
    print(f"\nSaved: {OUT}  ({size_kb:.0f} KB)")

    # Quick sanity: re-open and report
    with rasterio.open(OUT) as dst:
        print(f"Re-opened CRS: {dst.crs}")
        print(f"Bounds: {dst.bounds}")


if __name__ == "__main__":
    main()
