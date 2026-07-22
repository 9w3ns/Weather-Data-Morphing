#! python 3
# GHPython Script: OSM green space (GeoJSON) -> polygon curves + per-feature attrs
#
# Draws the green-coverage layer from data/fetch_green_space_osm.py in the SAME
# local XY frame as the LCZ mesh, district curves, transit, BMA land sites and the
# satellite basemap -- so green overlays everything with no registration step.
#
# Read it against gh_bma_land.py, whose structure this mirrors exactly: bulk ring
# geometry goes to text files (Script components choke on big point lists); the
# per-feature attribute lists return directly. Two green classes so you can colour
# or filter them apart:
#     green_class == "park"       -> recreational, people-usable (colour green)
#     green_class == "vegetation" -> forest/grass/scrub cover (colour a muted tone)
#
# Inputs:
#   Green_GeoJSON_Path  : String, path to data/gis/bangkok_green_space.geojson
#   Origin_GeoJSON_Path : String, path to data/gis/bangkok_districts.geojson
#                         (projection origin -- wire the SAME file as the other
#                         gh_ scripts or the layers will be offset).
#   Min_Area            : Float, drop green features below this area in sqm
#                         (default 1000; there are ~9k features -- raise to cap load).
#   Class_Filter        : String, "all" (default), "park", or "vegetation".
# Outputs:
#   Green_Points_Path : String, text file: one "x,y" per line, every kept feature's
#                       simplified outer ring, back to back.
#   Green_Counts_Path : String, text file: one integer per line, point count per
#                       feature (same order). sum == lines in points; line count == n.
#   Green_Class       : List of String, "park"/"vegetation" per feature (same order)
#                       -> Member Index against ("park","vegetation") -> Colour Swatch.
#   Area_SqM          : List of String, feature area (same order).
#   Name              : List of String, OSM name (same order; often "").
#   District          : List of String, district per feature (same order).
#   Green_Count       : String, number of features kept.
#   Report            : String summary / error log.
#
# Rebuild curves natively (same wiring as gh_bma_land.py):
#   Green_Points_Path -> Read File -> Split Text(\n) -> Split Text(",", x2)
#     -> Number -> Construct Point => Points
#   Green_Counts_Path -> Read File -> Split Text(\n) -> Number => Sizes
#   Partition List (List=Points, Size=Sizes) -> Polyline (Closed=True) -> Flatten
#   Green_Class -> Member Index against ("park","vegetation") -> Colour Swatch
import json
import math
import os
import traceback

DEFAULT_MIN_AREA = 1000.0
SIMPLIFY_TOL_M = 6.0  # match the other gh_ layers so everything registers

Green_Points_Path = None
Green_Counts_Path = None
Green_Class = []
Area_SqM = []
Name = []
District = []
Green_Count = "0"
Report = "Awaiting inputs..."


def perpendicular_distance(pt, a, b):
    x0, y0 = pt
    x1, y1 = a
    x2, y2 = b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x0 - x1, y0 - y1)
    t = ((x0 - x1) * dx + (y0 - y1) * dy) / (dx * dx + dy * dy)
    return math.hypot(x0 - (x1 + t * dx), y0 - (y1 + t * dy))


def douglas_peucker(points, epsilon):
    if len(points) < 3:
        return points
    start, end = points[0], points[-1]
    max_dist, index = 0.0, 0
    for i in range(1, len(points) - 1):
        d = perpendicular_distance(points[i], start, end)
        if d > max_dist:
            max_dist, index = d, i
    if max_dist > epsilon:
        left = douglas_peucker(points[:index + 1], epsilon)
        right = douglas_peucker(points[index:], epsilon)
        return left[:-1] + right
    return [start, end]


def clean_path(p):
    return str(p).strip().strip('"').strip("'")


def outer_ring(geom):
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return None
    if gtype == "Polygon":
        return coords[0]
    if gtype == "MultiPolygon":
        return max((poly[0] for poly in coords if poly), key=len, default=None)
    return None


def collect_origin(geojson):
    lons, lats = [], []
    for feat in geojson.get("features", []):
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates")
        if not coords:
            continue
        polys = coords if geom.get("type") == "MultiPolygon" else [coords]
        for poly in polys:
            for ring in poly:
                for lon, lat in ring:
                    lons.append(lon)
                    lats.append(lat)
    return lons, lats


if not (Green_GeoJSON_Path and Origin_GeoJSON_Path):
    Report = "Provide Green_GeoJSON_Path and Origin_GeoJSON_Path."
else:
    try:
        min_area = float(Min_Area) if "Min_Area" in globals() and Min_Area not in (None, "") else DEFAULT_MIN_AREA
        class_filter = str(Class_Filter).strip().lower() if "Class_Filter" in globals() and Class_Filter else "all"

        with open(clean_path(Origin_GeoJSON_Path), "r", encoding="utf-8") as f:
            districts_geojson = json.load(f)
        lons, lats = collect_origin(districts_geojson)
        if not lons:
            raise ValueError("No geometry in Origin_GeoJSON_Path (districts file).")
        lon0 = sum(lons) / len(lons)
        lat0 = sum(lats) / len(lats)
        lat0_rad = math.radians(lat0)
        EARTH_R = 6371000.0

        def to_xy(lon, lat):
            x = math.radians(lon - lon0) * EARTH_R * math.cos(lat0_rad)
            y = math.radians(lat - lat0) * EARTH_R
            return x, y

        with open(clean_path(Green_GeoJSON_Path), "r", encoding="utf-8") as f:
            green = json.load(f)

        feats = []
        for feat in green.get("features", []):
            props = feat.get("properties", {}) or {}
            gclass = str(props.get("green_class", ""))
            if class_filter in ("park", "vegetation") and gclass != class_filter:
                continue
            area = props.get("area_sqm", 0.0) or 0.0
            if area < min_area:
                continue
            feats.append((area, feat))
        feats.sort(key=lambda t: t[0], reverse=True)

        out_dir = os.path.dirname(clean_path(Green_GeoJSON_Path))
        Green_Points_Path = os.path.join(out_dir, "bangkok_green_points.txt")
        Green_Counts_Path = os.path.join(out_dir, "bangkok_green_counts.txt")

        point_lines, count_lines = [], []
        kept = 0
        for area, feat in feats:
            ring = outer_ring(feat.get("geometry") or {})
            if not ring:
                continue
            xy = [to_xy(lon, lat) for lon, lat in ring]
            simplified = douglas_peucker(xy, SIMPLIFY_TOL_M)
            if len(simplified) < 3:
                continue
            for x, y in simplified:
                point_lines.append("{:.2f},{:.2f}".format(x, y))
            count_lines.append(str(len(simplified)))

            props = feat.get("properties", {}) or {}
            Green_Class.append(str(props.get("green_class", "")))
            Area_SqM.append("{:.1f}".format(float(area)))
            Name.append(str(props.get("name", "")))
            District.append(str(props.get("district", "")))
            kept += 1

        with open(Green_Points_Path, "w", encoding="utf-8") as f:
            f.write("\n".join(point_lines))
        with open(Green_Counts_Path, "w", encoding="utf-8") as f:
            f.write("\n".join(count_lines))

        Green_Count = str(kept)
        n_park = sum(1 for c in Green_Class if c == "park")
        Report = (
            "Origin (shared with districts): lon0={:.5f}, lat0={:.5f}\n"
            "Class_Filter={} | Min_Area={:.0f} | Simplify tol={:.0f} m\n"
            "{} features kept ({} park, {} vegetation), {} points.\nWrote:\n  {}\n  {}"
        ).format(lon0, lat0, class_filter, min_area, kept, n_park, kept - n_park,
                 len(point_lines), Green_Points_Path, Green_Counts_Path)

    except Exception:
        Report = "ERROR:\n" + traceback.format_exc()
