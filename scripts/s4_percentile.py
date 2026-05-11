"""
Step 4: Compute per-cell percentile rank across all Oberbayern cells.

Input:  data/processed/s3_clipped_ob.tif
Output: data/processed/sunshine_mean_ob.tif  (2-band: hours + percentile)
          Band 1: sun_hours_mean  (float32, h/yr)
          Band 2: sun_percentile  (float32, 0-100)

This is the committed output — small enough (~200 KB) to track in git.

Run:  uv run python scripts/s4_percentile.py
"""

from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).parent.parent
IN = ROOT / "data" / "processed" / "s3_clipped_ob.tif"
OUT = ROOT / "data" / "processed" / "sunshine_mean_ob.tif"


def main():
    if not IN.exists():
        raise FileNotFoundError(f"Run s3_clip_oberbayern.py first: {IN}")

    with rasterio.open(IN) as src:
        hours = src.read(1)
        profile = src.profile.copy()
        print(f"Input: {IN}")
        print(f"  Shape:  {src.height} x {src.width}")
        print(f"  CRS:    {src.crs}")
        print(f"  Bounds: {src.bounds}")

    valid_mask = ~np.isnan(hours)
    valid_vals = hours[valid_mask]
    print(f"\nValid cells: {len(valid_vals):,}")
    print(f"Hours range: [{valid_vals.min():.0f}, {valid_vals.max():.0f}] h/yr")
    print(f"Hours mean:  {valid_vals.mean():.0f} h/yr")

    order = np.argsort(valid_vals)
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(1, len(valid_vals) + 1)
    percentiles = (ranks / len(valid_vals)) * 100.0

    pct_arr = np.full_like(hours, np.nan)
    pct_arr[valid_mask] = percentiles.astype(np.float32)

    print(f"\nPercentile range: [{pct_arr[valid_mask].min():.2f}, {pct_arr[valid_mask].max():.2f}]")

    # Report absolute values at key thresholds
    for p in [50, 70, 80, 90]:
        val = np.percentile(valid_vals, p)
        n_above = int(np.sum(valid_vals >= val))
        print(f"  {p}th pct = {val:.0f} h/yr  ({n_above:,} cells above)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    write_profile = profile.copy()
    write_profile.update(count=2, compress="lzw", predictor=3)
    with rasterio.open(OUT, "w", **write_profile) as dst:
        dst.write(hours, 1)
        dst.write(pct_arr, 2)
        dst.update_tags(1, name="sun_hours_mean", unit="h/yr")
        dst.update_tags(2, name="sun_percentile", unit="0-100")

    size_kb = OUT.stat().st_size / 1024
    print(f"\nSaved: {OUT}  ({size_kb:.0f} KB)")
    if size_kb > 1000:
        print("  WARNING: file >1 MB — reconsider committing to git")
    else:
        print("  OK to commit to git")


if __name__ == "__main__":
    main()
