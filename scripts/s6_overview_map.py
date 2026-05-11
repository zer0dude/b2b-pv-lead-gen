"""
Step 6: Generate Oberbayern overview map with lead buildings.

Sunshine raster as background, Landkreis boundaries as thin white lines,
and the 230 lead buildings as dots (size = roof area, colour = sun percentile).

Inputs:  data/processed/sunshine_mean_ob.tif
         data/processed/landkreis_boundaries.gpkg
         data/processed/leads.geojson

Output:  data/processed/overview_map.png

Run:  uv run python scripts/s6_overview_map.py
"""

import matplotlib
matplotlib.use("Agg")

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import rasterio

ROOT = Path(__file__).parent.parent
TIF = ROOT / "data" / "processed" / "sunshine_mean_ob.tif"
LK = ROOT / "data" / "processed" / "landkreis_boundaries.gpkg"
LEADS = ROOT / "data" / "processed" / "leads.geojson"
OUT = ROOT / "data" / "processed" / "overview_map.png"


def main():
    for path, name in [(TIF, "sunshine_mean_ob.tif"), (LK, "landkreis_boundaries.gpkg"),
                       (LEADS, "leads.geojson")]:
        if not path.exists():
            raise FileNotFoundError(f"Run earlier pipeline steps first: {name}")

    # --- Load raster ---
    with rasterio.open(TIF) as src:
        hours = src.read(1)
        bounds = src.bounds
    extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]

    # --- Load supporting layers ---
    lk_gdf = gpd.read_file(LK)

    # Load leads and reproject to raster CRS (EPSG:25832) for correct overlay
    leads = gpd.read_file(LEADS).to_crs("EPSG:25832")
    leads["x"] = leads.geometry.x
    leads["y"] = leads.geometry.y

    # --- Figure ---
    fig, ax = plt.subplots(figsize=(12, 9))

    # Sunshine background
    vmin = np.nanpercentile(hours, 2)
    vmax = np.nanpercentile(hours, 98)
    im = ax.imshow(hours, extent=extent, origin="upper", cmap="YlOrRd",
                   vmin=vmin, vmax=vmax, aspect="equal", interpolation="nearest")
    plt.colorbar(im, ax=ax, label="Mittlere Jahressonnenscheindauer (h/Jahr)",
                 fraction=0.035, pad=0.02)

    # Landkreis boundaries
    lk_gdf.boundary.plot(ax=ax, color="white", linewidth=0.6, alpha=0.7)

    # Landkreis name labels
    for _, row in lk_gdf.iterrows():
        cx, cy = row.geometry.centroid.x, row.geometry.centroid.y
        name = row.get("name", row.get("landkreis_name", ""))
        if name:
            short = name.replace(" (Lkr)", "").replace(" (Stadt)", "").replace("Bad ", "B.")
            ax.text(cx, cy, short[:10], color="white", fontsize=4.5,
                    ha="center", va="center", alpha=0.8,
                    bbox=dict(boxstyle="round,pad=0.1", fc="black", alpha=0.25, ec="none"))

    # --- Building dots (uniform small size, location markers only) ---
    ax.scatter(leads["x"].values, leads["y"].values,
               s=8, c="deepskyblue",
               edgecolors="white", linewidths=0.4, alpha=0.9, zorder=3)

    # Axes formatting
    ax.set_title("Solarpotenzial Oberbayern — Top-10 Gebäude pro Landkreis",
                 fontsize=11, fontweight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_xticks([])
    ax.set_yticks([])

    plt.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=120, bbox_inches="tight")
    print(f"Saved: {OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")
    plt.close(fig)


if __name__ == "__main__":
    main()
