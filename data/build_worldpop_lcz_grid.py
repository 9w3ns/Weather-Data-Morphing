"""WorldPop 100 m -> the 200 m LCZ grid: current de-facto population per cell.

Downloads WorldPop's UN-adjusted 2020 population count for Thailand (people per
100 m pixel) and zonal-SUMS it onto the SAME 200 m grid the LCZ mesh uses
(bangkok_lcz_grid.csv / _meta.json), in the shared local XY frame -- so it overlays
the LCZ mesh, satellite basemap and BMA sites with no registration.

Counts, so SUM (never average) when aggregating pixels into a coarser cell. The LCZ
grid is regular in the local equirectangular frame, and that frame is linear in
lon/lat, so a WorldPop pixel is binned into a cell by forward-projecting its centre
to local XY and integer-dividing by the 200 m cell size -- fast and exact to pixel.

Source: WorldPop, tha_ppp_2020_UNadj.tif (CC-BY). This is a MODELED dasymetric
estimate anchored to the UN total (~= de-facto), NOT a count -- pair with DOPA
registered for the registered/non-registered split (see plan_population_projection_2050.md).

Run from the repo root.
Output: data/gis/bangkok_lcz_grid_population.csv (X, Y, pop_defacto_2020)
"""
import csv
import math
import os

import numpy as np
import rasterio
from rasterio.windows import from_bounds

WP_URL = ("https://data.worldpop.org/GIS/Population/Global_2000_2020/"
          "2020/THA/tha_ppp_2020_UNadj.tif")
TIF = "cache/tha_ppp_2020_UNadj.tif"
GRID_CSV = "data/gis/bangkok_lcz_grid.csv"
META = "data/gis/bangkok_lcz_grid_meta.json"
OUT = "data/gis/bangkok_lcz_grid_population.csv"
EARTH_R = 6371000.0
CELL = 200.0


def download():
    if os.path.exists(TIF) and os.path.getsize(TIF) > 0:
        print("Cached: {} ({:.1f} MB)".format(TIF, os.path.getsize(TIF) / 1e6))
        return
    import requests
    os.makedirs("cache", exist_ok=True)
    print("Downloading WorldPop Thailand 2020 UN-adj (~100 m)...")
    with requests.get(WP_URL, stream=True, timeout=600,
                      headers={"User-Agent": "thesis/1.0"}) as r:
        r.raise_for_status()
        with open(TIF, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    print("  saved {} ({:.1f} MB)".format(TIF, os.path.getsize(TIF) / 1e6))


def main():
    import json
    download()
    with open(META, "r", encoding="utf-8") as f:
        meta = json.load(f)
    lon0, lat0 = float(meta["lon0"]), float(meta["lat0"])
    coslat0 = math.cos(math.radians(lat0))

    # LCZ grid cell centres (local XY) and its regular structure.
    xs, ys = [], []
    with open(GRID_CSV, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            xs.append(float(row["X"]))
            ys.append(float(row["Y"]))
    xs_arr, ys_arr = np.array(xs), np.array(ys)
    minx, miny = xs_arr.min(), ys_arr.min()
    ncol = int(round((xs_arr.max() - minx) / CELL)) + 1
    nrow = int(round((ys_arr.max() - miny) / CELL)) + 1
    x0edge, y0edge = minx - CELL / 2.0, miny - CELL / 2.0  # grid outer edge

    # lon/lat window covering the grid (pad one cell).
    def to_lon(x):
        return lon0 + math.degrees(x / (EARTH_R * coslat0))

    def to_lat(y):
        return lat0 + math.degrees(y / EARTH_R)

    min_lon, max_lon = to_lon(minx - CELL), to_lon(xs_arr.max() + CELL)
    min_lat, max_lat = to_lat(miny - CELL), to_lat(ys_arr.max() + CELL)

    with rasterio.open(TIF) as src:
        win = from_bounds(min_lon, min_lat, max_lon, max_lat, src.transform)
        arr = src.read(1, window=win).astype("float64")
        wt = src.window_transform(win)
        nodata = src.nodata
    ny, nx = arr.shape
    print("WorldPop window: {} x {} px, nodata={}".format(nx, ny, nodata))

    # Pixel-centre lon/lat, then forward-project to local XY.
    jj, ii = np.meshgrid(np.arange(ny), np.arange(nx), indexing="ij")
    lon = wt.c + wt.a * (ii + 0.5) + wt.b * (jj + 0.5)
    lat = wt.f + wt.d * (ii + 0.5) + wt.e * (jj + 0.5)
    pop = np.where((arr == nodata) | (arr < 0) | ~np.isfinite(arr), 0.0, arr)

    x = np.radians(lon - lon0) * EARTH_R * coslat0
    y = np.radians(lat - lat0) * EARTH_R
    col = np.floor((x - x0edge) / CELL).astype(int)
    rowi = np.floor((y - y0edge) / CELL).astype(int)
    ok = (col >= 0) & (col < ncol) & (rowi >= 0) & (rowi < nrow) & (pop > 0)
    flat = rowi[ok] * ncol + col[ok]
    cellpop = np.bincount(flat, weights=pop[ok], minlength=nrow * ncol)

    # Map onto the LCZ grid rows (same X,Y order as bangkok_lcz_grid.csv).
    c = np.round((xs_arr - minx) / CELL).astype(int)
    r = np.round((ys_arr - miny) / CELL).astype(int)
    per_cell = cellpop[r * ncol + c]

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["X", "Y", "pop_defacto_2020"])
        for xv, yv, pv in zip(xs, ys, per_cell):
            w.writerow(["{:.2f}".format(xv), "{:.2f}".format(yv), "{:.2f}".format(pv)])

    total = per_cell.sum()
    win_total = pop.sum()
    print("Grid cells: {} ({} x {}).".format(len(xs), ncol, nrow))
    print("Population captured on grid: {:,.0f}".format(total))
    print("  (window raster total: {:,.0f} -- grid should capture ~all of it)".format(win_total))
    print("  nonzero cells: {} | max cell: {:,.0f} people".format(
        int((per_cell > 0).sum()), per_cell.max()))
    print("Wrote {}".format(OUT))
    print("\nNOTE: WorldPop UN-adjusted ~= de-facto; expect well above DOPA registered "
          "(~5.45M). Next: DOPA registered per district -> registered/non-reg split.")


if __name__ == "__main__":
    main()
