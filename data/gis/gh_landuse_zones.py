#! python 3
# GHPython Script: Residential / Working land-use polygons -> points files + metadata
#
# Companion to gh_geojson_to_curves.py. That script turns the DISTRICT
# boundaries into curves; this one turns the OSM land-use ZONES (residential
# vs working) from fetch_land_use_osm.py into curves so you can overlay the
# work<->home fabric on the same canvas.
#
# Inputs:
#   Residential_Path    : String, path to data/gis/bangkok_residential_zones.geojson
#   Working_Path        : String, path to data/gis/bangkok_working_zones.geojson
#   Origin_GeoJSON_Path : String, path to data/gis/bangkok_districts.geojson.
#                         Used ONLY to derive the projection origin (mean lon/lat
#                         of the district vertices) so these zones land in the
#                         EXACT same local XY frame as gh_geojson_to_curves.py.
#                         Wire the SAME districts file into both scripts or the
#                         layers will be offset from each other.
#   Min_Area_SqM        : Float, drop polygons smaller than this (default 2000).
#                         OSM has thousands of tiny slivers; filtering keeps GH
#                         responsive. Set 0 to keep everything.
#   Simplify_Tolerance_M: Float, Douglas-Peucker tolerance in metres (default 15).
# Outputs:
#   Res_Points_Path  : String, path to a text file: one "x,y" per line, every
#                      residential polygon's simplified ring, back to back.
#   Res_Counts_Path  : String, path to a text file: one integer per line, the
#                      point count of each residential polygon (same order).
#   Work_Points_Path : String, as above, for working zones.
#   Work_Counts_Path : String, as above, for working zones.
#   Res_Poly_Count   : String, number of residential polygons kept.
#   Work_Poly_Count  : String, number of working polygons kept.
#   Report           : String summary / error log.
#
# Why files, not lists: this Script component's output channel drops sizeable
# lists (a ~1700-item list came back empty before -- see gh_geojson_to_curves.py).
# Residential alone is ~5000 polygons, so BOTH the points and the per-polygon
# counts go to files and only the small file PATHS are returned. Rebuild the
# curves natively on the canvas (this chain does not cross the broken boundary):
#   Res_Points_Path -> Read File -> Split Text(newline) -> Split Text(comma, x2)
#     -> Number -> Construct Point => Points
#   Res_Counts_Path -> Read File -> Split Text(newline) -> Number => Sizes
#   Partition List: List=Points, Size=Sizes -> chunks
#   Polyline (Closed=True) per chunk -> Flatten => Residential curves
#   (repeat with the Work_* outputs for the working zones)
# Give the two curve sets different colours (e.g. residential=orange,
# working=red) with a Custom Preview.
import json
import math
import os
import traceback

DEFAULT_MIN_AREA_SQM = 2000.0
DEFAULT_SIMPLIFY_TOL_M = 15.0

# Initialize outputs
Res_Points_Path = None
Res_Counts_Path = None
Work_Points_Path = None
Work_Counts_Path = None
Res_Poly_Count = "0"
Work_Poly_Count = "0"
Report = "Awaiting inputs..."


def perpendicular_distance(pt, line_start, line_end):
    x0, y0 = pt
    x1, y1 = line_start
    x2, y2 = line_end
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x0 - x1, y0 - y1)
    t = ((x0 - x1) * dx + (y0 - y1) * dy) / (dx * dx + dy * dy)
    proj_x, proj_y = x1 + t * dx, y1 + t * dy
    return math.hypot(x0 - proj_x, y0 - proj_y)


def douglas_peucker(points, epsilon):
    if len(points) < 3:
        return points
    start, end = points[0], points[-1]
    max_dist = 0.0
    index = 0
    for i in range(1, len(points) - 1):
        d = perpendicular_distance(points[i], start, end)
        if d > max_dist:
            max_dist = d
            index = i
    if max_dist > epsilon:
        left = douglas_peucker(points[:index + 1], epsilon)
        right = douglas_peucker(points[index:], epsilon)
        return left[:-1] + right
    return [start, end]


def shoelace_area(pts):
    # |signed area| of a closed ring in projected XY (square metres).
    if len(pts) < 3:
        return 0.0
    s = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return abs(s) * 0.5


def clean_path(p):
    return str(p).strip().strip('"').strip("'")


def iter_polygon_rings(geojson):
    """Yield the outer ring (list of [lon,lat]) of every polygon, expanding
    MultiPolygons. We keep only the outer ring of each polygon -- holes are
    ignored for this coarse overlay."""
    for feat in geojson.get('features', []):
        geom = feat.get('geometry') or {}
        gtype = geom.get('type')
        coords = geom.get('coordinates')
        if not coords:
            continue
        if gtype == 'Polygon':
            yield coords[0]
        elif gtype == 'MultiPolygon':
            for poly in coords:
                if poly:
                    yield poly[0]


def collect_origin(geojson):
    all_lon, all_lat = [], []
    for feat in geojson.get('features', []):
        geom = feat.get('geometry') or {}
        gtype = geom.get('type')
        coords = geom.get('coordinates')
        if not coords:
            continue
        polys = coords if gtype == 'MultiPolygon' else [coords]
        for poly in polys:
            for ring in poly:
                for lon, lat in ring:
                    all_lon.append(lon)
                    all_lat.append(lat)
    return all_lon, all_lat


def process_layer(path, lon0, lat0, lat0_rad, min_area, tol, out_points, out_counts):
    EARTH_RADIUS_M = 6371000.0

    def to_xy(lon, lat):
        x = math.radians(lon - lon0) * EARTH_RADIUS_M * math.cos(lat0_rad)
        y = math.radians(lat - lat0) * EARTH_RADIUS_M
        return x, y

    with open(clean_path(path), 'r', encoding='utf-8') as f:
        geojson = json.load(f)

    point_lines = []
    count_lines = []
    kept = 0
    dropped_small = 0
    for ring in iter_polygon_rings(geojson):
        xy = [to_xy(lon, lat) for lon, lat in ring]
        if min_area > 0 and shoelace_area(xy) < min_area:
            dropped_small += 1
            continue
        simplified = douglas_peucker(xy, tol)
        if len(simplified) < 3:
            continue
        for x, y in simplified:
            point_lines.append("{:.2f},{:.2f}".format(x, y))
        count_lines.append(str(len(simplified)))
        kept += 1

    with open(out_points, 'w', encoding='utf-8') as f:
        f.write("\n".join(point_lines))
    with open(out_counts, 'w', encoding='utf-8') as f:
        f.write("\n".join(count_lines))
    return kept, dropped_small, len(point_lines)


if not (Residential_Path and Working_Path and Origin_GeoJSON_Path):
    Report = "Provide Residential_Path, Working_Path and Origin_GeoJSON_Path."
else:
    try:
        min_area = float(Min_Area_SqM) if 'Min_Area_SqM' in globals() and Min_Area_SqM not in (None, "") else DEFAULT_MIN_AREA_SQM
        tol = float(Simplify_Tolerance_M) if 'Simplify_Tolerance_M' in globals() and Simplify_Tolerance_M not in (None, "") else DEFAULT_SIMPLIFY_TOL_M

        # Shared projection origin: mean of DISTRICT vertices, identical to
        # gh_geojson_to_curves.py so the layers overlay perfectly.
        with open(clean_path(Origin_GeoJSON_Path), 'r', encoding='utf-8') as f:
            districts_geojson = json.load(f)
        all_lon, all_lat = collect_origin(districts_geojson)
        if not all_lon:
            raise ValueError("No geometry in Origin_GeoJSON_Path (districts file).")
        lon0 = sum(all_lon) / len(all_lon)
        lat0 = sum(all_lat) / len(all_lat)
        lat0_rad = math.radians(lat0)

        out_dir = os.path.dirname(clean_path(Residential_Path))
        Res_Points_Path = os.path.join(out_dir, "bangkok_residential_points.txt")
        Res_Counts_Path = os.path.join(out_dir, "bangkok_residential_counts.txt")
        Work_Points_Path = os.path.join(out_dir, "bangkok_working_points.txt")
        Work_Counts_Path = os.path.join(out_dir, "bangkok_working_counts.txt")

        r_kept, r_drop, r_pts = process_layer(
            Residential_Path, lon0, lat0, lat0_rad, min_area, tol,
            Res_Points_Path, Res_Counts_Path)
        w_kept, w_drop, w_pts = process_layer(
            Working_Path, lon0, lat0, lat0_rad, min_area, tol,
            Work_Points_Path, Work_Counts_Path)

        Res_Poly_Count = str(r_kept)
        Work_Poly_Count = str(w_kept)

        Report = (
            "Projection origin (shared with districts): lon0={:.5f}, lat0={:.5f}\n"
            "Min area filter: {:.0f} sqm | Simplify tol: {:.0f} m\n"
            "Residential: {} polygons kept ({} dropped as too small), {} points\n"
            "Working:     {} polygons kept ({} dropped as too small), {} points\n"
            "Wrote:\n  {}\n  {}\n  {}\n  {}"
        ).format(
            lon0, lat0, min_area, tol,
            r_kept, r_drop, r_pts,
            w_kept, w_drop, w_pts,
            Res_Points_Path, Res_Counts_Path, Work_Points_Path, Work_Counts_Path)

    except Exception:
        Report = "ERROR:\n" + traceback.format_exc()
