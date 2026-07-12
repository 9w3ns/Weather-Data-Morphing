"""
Phase 2b of docs/uhi_data_sourcing_plan.md: full-resolution LCZ *grid* for
Bangkok, instead of the one-class-per-district majority vote in
data/fetch_uhi_lcz.py. Same source (Demuzere et al. 2022 global LCZ map on
Earth Engine), but pulls every raster cell in the district bounding box via
ee.data.computePixels() -- a single synchronous pixel-array fetch, no
Export.image.toDrive/task-polling needed since the region is small enough
(a few hundred KB - low single-digit MB even at native 100m) to fit well
under computePixels' response-size limit.

Output coordinates are projected into the SAME local planar XY (meters,
equirectangular, centered on the mean vertex of all districts) that
data/gis/gh_geojson_to_curves.py uses for the district curves, so the grid
lines up with existing Grasshopper geometry without any extra alignment
step on the GH side.

Requires: `pip install earthengine-api` and Earth Engine access (see
docs/uhi_data_sourcing_plan.md Phase 1).
"""
import argparse
import csv
import json
import math
import os

import ee

EE_PROJECT = "weather-data-morphing"
DEFAULT_SCALE_M = 200.0
EARTH_RADIUS_M = 6371000.0


def compute_origin_and_bounds(geojson):
    """Mirrors gh_geojson_to_curves.py's origin calc exactly, so the grid's
    local XY matches the district curves already built on the GH canvas."""
    all_lons, all_lats = [], []
    for feat in geojson["features"]:
        geom = feat["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys:
            for ring in poly:
                for lon, lat in ring:
                    all_lons.append(lon)
                    all_lats.append(lat)

    lon0 = sum(all_lons) / len(all_lons)
    lat0 = sum(all_lats) / len(all_lats)
    return lon0, lat0, min(all_lons), max(all_lons), min(all_lats), max(all_lats)


def make_to_xy(lon0, lat0):
    lat0_rad = math.radians(lat0)

    def to_xy(lon, lat):
        x = math.radians(lon - lon0) * EARTH_RADIUS_M * math.cos(lat0_rad)
        y = math.radians(lat - lat0) * EARTH_RADIUS_M
        return x, y

    return to_xy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=float, default=DEFAULT_SCALE_M,
                         help="Grid cell size in meters (default {}). Native map "
                              "resolution is 100m; smaller values grow cell count "
                              "fast (100m ~341k cells, 200m ~85k, 250m ~55k).".format(DEFAULT_SCALE_M))
    args = parser.parse_args()
    scale_m = args.scale

    base_dir = os.path.dirname(os.path.abspath(__file__))
    geojson_path = os.path.join(base_dir, "gis", "bangkok_districts.geojson")
    csv_out_path = os.path.join(base_dir, "gis", "bangkok_lcz_grid.csv")
    meta_out_path = os.path.join(base_dir, "gis", "bangkok_lcz_grid_meta.json")

    print("Loading district boundaries from {}...".format(geojson_path))
    with open(geojson_path, "r", encoding="utf-8") as f:
        geojson = json.load(f)
    lon0, lat0, min_lon, max_lon, min_lat, max_lat = compute_origin_and_bounds(geojson)
    to_xy = make_to_xy(lon0, lat0)

    lat0_rad = math.radians(lat0)
    deg_per_m_lat = 1.0 / (EARTH_RADIUS_M * math.pi / 180.0)
    deg_per_m_lon = deg_per_m_lat / max(math.cos(lat0_rad), 1e-9)
    deg_x = scale_m * deg_per_m_lon
    deg_y = scale_m * deg_per_m_lat

    width = int(math.ceil((max_lon - min_lon) / deg_x))
    height = int(math.ceil((max_lat - min_lat) / deg_y))
    print("Grid: {} x {} = {} cells at {:.0f}m".format(width, height, width * height, scale_m))

    print("Initializing Earth Engine (project={})...".format(EE_PROJECT))
    ee.Initialize(project=EE_PROJECT)

    print("Loading global LCZ map (Demuzere et al. 2022)...")
    lcz_col = ee.ImageCollection("RUB/RUBCLIM/LCZ/global_lcz_map/latest")
    lcz_img = lcz_col.select(["LCZ_Filter", "LCZ_Probability"]).mosaic()

    request = {
        "expression": lcz_img,
        "fileFormat": "NUMPY_NDARRAY",
        "grid": {
            "dimensions": {"width": width, "height": height},
            "affineTransform": {
                "scaleX": deg_x, "shearX": 0, "translateX": min_lon,
                "shearY": 0, "scaleY": -deg_y, "translateY": max_lat,
            },
            "crsCode": "EPSG:4326",
        },
    }

    print("Fetching pixel grid via ee.data.computePixels()...")
    arr = ee.data.computePixels(request)

    rows = []
    for r in range(height):
        lat = max_lat - (r + 0.5) * deg_y
        for c in range(width):
            lon = min_lon + (c + 0.5) * deg_x
            code = int(arr[r, c]["LCZ_Filter"])
            prob = float(arr[r, c]["LCZ_Probability"])
            x, y = to_xy(lon, lat)
            rows.append((r, c, x, y, code, prob))

    print("Writing {} cells to {}...".format(len(rows), csv_out_path))
    with open(csv_out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Row", "Col", "X", "Y", "LCZ_Code", "LCZ_Confidence_Pct"])
        for r, c, x, y, code, prob in rows:
            writer.writerow([r, c, "{:.2f}".format(x), "{:.2f}".format(y), code, "{:.1f}".format(prob)])

    meta = {
        "width": width, "height": height, "scale_m": scale_m,
        "lon0": lon0, "lat0": lat0,
        "min_lon": min_lon, "max_lon": max_lon, "min_lat": min_lat, "max_lat": max_lat,
        "cell_size_x_m": scale_m, "cell_size_y_m": scale_m,
    }
    with open(meta_out_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print("Wrote grid CSV + metadata. {} rows.".format(len(rows)))


if __name__ == "__main__":
    main()
