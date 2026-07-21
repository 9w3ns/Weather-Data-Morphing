"""Export a satellite basemap that fits the LCZ grid mesh EXACTLY.

The LCZ pixel grid (data/gis/gh_lcz_grid_mesh.py) is drawn in a local planar XY
frame -- equirectangular metres, centred on the mean district vertex
(lon0/lat0 in bangkok_lcz_grid_meta.json). Every other gh_ layer (districts,
transit, land-use, vacant plots, and the BMA land sites) shares that same origin,
verified to 0.00 m. So an image fitted to the LCZ mesh also sits correctly under
the BMA sites -- which is the point: drop it behind the grid to see WHERE a site is.

WHAT IT DOES
  1. Reads the mesh extent from bangkok_lcz_grid.csv (cell centres +/- half a cell)
     -- the true drawn rectangle, not just the meta bbox.
  2. Back-projects that local-XY rectangle to a lon/lat bbox with the SAME
     equirectangular maths the GH scripts use (linear per axis, so the rectangle
     stays a rectangle and the image aligns corner-to-corner with no warping).
  3. Fetches Esri World Imagery for that bbox in EPSG:4326. A single export is
     capped at 4096 px, so it tiles into a grid and stitches with Pillow.
  4. Writes the image, a world file (.jgw, in the LOCAL XY frame), and a sidecar
     with the exact corner coordinates + Grasshopper/Rhino placement steps.

IMAGERY: Esri World Imagery (keyless export). Attribution required in the thesis:
  "Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community".

Run from the repo root.
Output: docs/bangkok_lcz_satellite.jpg  (+ .jgw world file, + .meta.json)
"""
import argparse
import io
import json
import math
import os
import time

import requests
from PIL import Image

EARTH_R = 6371000.0
SERVICE_URL = ("https://services.arcgisonline.com/ArcGIS/rest/services/"
               "World_Imagery/MapServer/export")
ATTRIBUTION = "Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community"
USER_AGENT = "thesis-site-selection/1.0 (academic research)"
CACHE_DIR = "cache"
TILE_MAX_PX = 4096          # Esri export hard cap per request
DEFAULT_MPP = 8.0           # ground metres per pixel (8 m/px over ~66 km city)
REQUEST_SLEEP_S = 0.3
MAX_RETRIES = 3

GRID_CSV = "data/gis/bangkok_lcz_grid.csv"
META_JSON = "data/gis/bangkok_lcz_grid_meta.json"


def mesh_extent_local(grid_csv, half_cell):
    """Exact drawn rectangle of the mesh in local XY: cell centres +/- half a cell."""
    import csv
    xs_min = ys_min = float("inf")
    xs_max = ys_max = float("-inf")
    with open(grid_csv, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            x, y = float(row["X"]), float(row["Y"])
            xs_min, xs_max = min(xs_min, x), max(xs_max, x)
            ys_min, ys_max = min(ys_min, y), max(ys_max, y)
    return (xs_min - half_cell, ys_min - half_cell,
            xs_max + half_cell, ys_max + half_cell)


def fetch_tile(bbox, size_px):
    """One Esri World Imagery export, cached to cache/ by bbox+size."""
    xmin, ymin, xmax, ymax = bbox
    w, h = size_px
    key = "sat_{:.6f}_{:.6f}_{:.6f}_{:.6f}_{}x{}.jpg".format(xmin, ymin, xmax, ymax, w, h)
    cache_file = os.path.join(CACHE_DIR, key)
    if os.path.exists(cache_file):
        return Image.open(cache_file).convert("RGB")

    params = {"bbox": "{},{},{},{}".format(xmin, ymin, xmax, ymax),
              "bboxSR": "4326", "imageSR": "4326",
              "size": "{},{}".format(w, h), "format": "jpg", "f": "image"}
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(SERVICE_URL, params=params,
                             headers={"User-Agent": USER_AGENT}, timeout=180)
            if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("image"):
                os.makedirs(CACHE_DIR, exist_ok=True)
                with open(cache_file, "wb") as fh:
                    fh.write(r.content)
                time.sleep(REQUEST_SLEEP_S)
                return Image.open(io.BytesIO(r.content)).convert("RGB")
            last_err = "HTTP {} / {}".format(r.status_code, r.headers.get("Content-Type"))
        except Exception as exc:
            last_err = str(exc)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError("tile export failed ({}): {}".format(bbox, last_err))


def build(mpp, out_path):
    with open(META_JSON, "r", encoding="utf-8") as f:
        meta = json.load(f)
    lon0, lat0 = float(meta["lon0"]), float(meta["lat0"])
    half_cell = float(meta["cell_size_x_m"]) / 2.0
    coslat0 = math.cos(math.radians(lat0))

    minx, miny, maxx, maxy = mesh_extent_local(GRID_CSV, half_cell)
    ext_x, ext_y = maxx - minx, maxy - miny

    # local XY -> lon/lat (inverse of the GH equirectangular projection)
    def to_lon(x):
        return lon0 + math.degrees(x / (EARTH_R * coslat0))

    def to_lat(y):
        return lat0 + math.degrees(y / EARTH_R)

    min_lon, max_lon = to_lon(minx), to_lon(maxx)
    min_lat, max_lat = to_lat(miny), to_lat(maxy)

    total_w = max(1, round(ext_x / mpp))
    total_h = max(1, round(ext_y / mpp))
    nx = int(math.ceil(total_w / TILE_MAX_PX))
    ny = int(math.ceil(total_h / TILE_MAX_PX))
    print("Mesh extent (local XY): X {:.1f}..{:.1f}  Y {:.1f}..{:.1f}  ({:.0f} x {:.0f} m)"
          .format(minx, maxx, miny, maxy, ext_x, ext_y))
    print("lon/lat bbox: {:.6f},{:.6f} .. {:.6f},{:.6f}".format(min_lon, min_lat, max_lon, max_lat))
    print("Image: {} x {} px @ {:.1f} m/px  ->  {} x {} = {} tiles".format(
        total_w, total_h, mpp, nx, ny, nx * ny))

    # Pixel boundaries so tiles tile exactly to total_w/total_h with no seam drift.
    xb = [round(i * total_w / nx) for i in range(nx + 1)]
    yb = [round(j * total_h / ny) for j in range(ny + 1)]

    canvas = Image.new("RGB", (total_w, total_h))
    done = 0
    for j in range(ny):          # rows: top (max_lat) -> bottom
        lat_hi = max_lat - (max_lat - min_lat) * (j / ny)
        lat_lo = max_lat - (max_lat - min_lat) * ((j + 1) / ny)
        for i in range(nx):      # cols: left (min_lon) -> right
            lon_lo = min_lon + (max_lon - min_lon) * (i / nx)
            lon_hi = min_lon + (max_lon - min_lon) * ((i + 1) / nx)
            w, h = xb[i + 1] - xb[i], yb[j + 1] - yb[j]
            tile = fetch_tile((lon_lo, lat_lo, lon_hi, lat_hi), (w, h))
            if tile.size != (w, h):
                tile = tile.resize((w, h), Image.LANCZOS)
            canvas.paste(tile, (xb[i], yb[j]))
            done += 1
            print("   tile {}/{}  col {} row {}  {}x{}".format(done, nx * ny, i, j, w, h))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.save(out_path, quality=90)
    print("\nWrote {}  ({} x {} px, {:.1f} MB)".format(
        out_path, total_w, total_h, os.path.getsize(out_path) / 1e6))

    # World file (.jgw) in the LOCAL XY frame: pixel -> local metres.
    px_x = ext_x / total_w
    px_y = ext_y / total_h
    wf = os.path.splitext(out_path)[0] + ".jgw"
    with open(wf, "w", encoding="utf-8") as f:
        f.write("\n".join("{:.10f}".format(v) for v in [
            px_x, 0.0, 0.0, -px_y, minx + px_x / 2.0, maxy - px_y / 2.0]) + "\n")
    print("Wrote {} (world file, local XY frame)".format(wf))

    corners = {"lower_left": [round(minx, 2), round(miny, 2)],
               "lower_right": [round(maxx, 2), round(miny, 2)],
               "upper_right": [round(maxx, 2), round(maxy, 2)],
               "upper_left": [round(minx, 2), round(maxy, 2)]}
    sidecar = os.path.splitext(out_path)[0] + ".meta.json"
    with open(sidecar, "w", encoding="utf-8") as f:
        json.dump({
            "fits": "bangkok_lcz_grid_mesh.py (and every gh_ layer -- shared origin)",
            "local_xy_frame": {"lon0": lon0, "lat0": lat0, "earth_r_m": EARTH_R},
            "extent_local_m": {"min_x": minx, "min_y": miny, "max_x": maxx, "max_y": maxy},
            "lonlat_bbox": {"min_lon": min_lon, "min_lat": min_lat,
                            "max_lon": max_lon, "max_lat": max_lat},
            "image_px": [total_w, total_h], "m_per_px": mpp,
            "corners_local_xy_z0": corners,
            "attribution": ATTRIBUTION,
            "grasshopper_placement": [
                "Rhino (simplest): run PictureFrame, pick the image, then type the",
                "lower-left corner {} and press Enter, then the upper-right".format(corners["lower_left"]),
                "corner {} -- places it flat at Z=0 aligned to the mesh.".format(corners["upper_right"]),
                "Send it to back / set Z just below 0 so the LCZ mesh and BMA site",
                "curves draw on top.",
                "Grasshopper: build a rectangle from the four corner points above at",
                "Z=0 and map this image as its material texture (e.g. Human 'Custom",
                "Preview Materials'), or just reference the Rhino PictureFrame object.",
            ],
        }, f, indent=2)
    print("Wrote {} (corners + placement instructions)".format(sidecar))
    print("\n{}".format(ATTRIBUTION))
    print("\nPlace in Rhino:  PictureFrame  ->  LL {}  ->  UR {}".format(
        corners["lower_left"], corners["upper_right"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mpp", type=float, default=DEFAULT_MPP,
                    help="Ground metres per pixel (default: %(default)s). Lower = "
                         "sharper + bigger file. 4 ~= building-legible, 16 ~= context.")
    ap.add_argument("--out", default="docs/bangkok_lcz_satellite.jpg",
                    help="Output image path (default: %(default)s).")
    args = ap.parse_args()
    build(args.mpp, args.out)
