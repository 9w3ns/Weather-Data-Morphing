#! python 3
# GHPython Script: candidate vacant/underused plots -> points file + per-plot attrs
#
# Renders the ranked candidate plots from data/fetch_vacant_plots_osm.py as
# curves on the canvas, in the SAME local XY frame as your district curves
# (gh_geojson_to_curves.py), LCZ grid, transit network and land-use zones -- so
# it overlays with no extra registration. Colour the plots by Rank_Score and
# read them against the transit stations + intercept zones already on the canvas.
#
# CANDIDATES, NOT CONFIRMED VACANT: OSM cannot prove a plot is empty. Treat the
# top-ranked plots as a shortlist to verify against satellite/Street View.
#
# Inputs:
#   Plots_GeoJSON_Path  : String, path to data/gis/bangkok_vacant_plots.geojson
#   Origin_GeoJSON_Path : String, path to data/gis/bangkok_districts.geojson
#                         (projection origin -- wire the SAME file as the other
#                         gh_ scripts or the layers will be offset).
#   Top_N               : int, keep only the N highest-ranked plots (default 300;
#                         0 = keep all). Caps GH load.
#   Min_Score           : Float, drop plots with rank_score below this (default 0).
# Outputs:
#   Plot_Points_Path : String, path to a text file: one "x,y" per line, every
#                      kept plot's simplified outer ring, back to back.
#   Plot_Counts_Path : String, path to a text file: one integer per line, the
#                      point count of each plot (same order). sum == lines in
#                      the points file; line count == number of plots.
#   Centroids        : List of String "x,y", one per plot (same order), for tags.
#   Rank_Score       : List of String, rank_score per plot (same order).
#   Dist_To_Station  : List of String, metres to nearest station (same order).
#   Area_SqM         : List of String, plot area (same order).
#   Source_Class     : List of String, OSM signal tag per plot (brownfield/
#                      greenfield/construction = high-confidence; grass/scrub =
#                      noisy) -- filter or restyle the low-confidence ones.
#   District         : List of String, district per plot (same order).
#   Plot_Count       : String, number of plots kept.
#   Report           : String summary / error log.
#
# Bulk ring geometry goes to files (this Script component drops big lists); the
# per-plot attribute lists stay small (<= Top_N) so they return directly, same
# split as gh_landuse_zones.py / gh_intercept_scores.py. Rebuild curves natively:
#   Plot_Points_Path -> Read File -> Split Text(\n) -> Split Text(",", x2)
#     -> Number -> Construct Point => Points
#   Plot_Counts_Path -> Read File -> Split Text(\n) -> Number => Sizes
#   Partition List (List=Points, Size=Sizes) -> Polyline (Closed=True) -> Flatten
#   Rank_Score -> Number -> Remap (0..max) -> Gradient -> Custom Preview on curves
import json
import math
import os
import traceback

DEFAULT_TOP_N = 300
DEFAULT_SIMPLIFY_TOL_M = 8.0  # plots are small; keep detail finer than the zones

# Initialize outputs
Plot_Points_Path = None
Plot_Counts_Path = None
Centroids = []
Rank_Score = []
Dist_To_Station = []
Area_SqM = []
Source_Class = []
District = []
Plot_Count = "0"
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
    """Outer ring [[lon,lat],...] of a Polygon, or the largest of a MultiPolygon."""
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


if not (Plots_GeoJSON_Path and Origin_GeoJSON_Path):
    Report = "Provide Plots_GeoJSON_Path and Origin_GeoJSON_Path."
else:
    try:
        top_n = int(Top_N) if "Top_N" in globals() and Top_N not in (None, "") else DEFAULT_TOP_N
        min_score = float(Min_Score) if "Min_Score" in globals() and Min_Score not in (None, "") else 0.0

        # Shared projection origin from the DISTRICT vertices (== other gh_ scripts).
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

        with open(clean_path(Plots_GeoJSON_Path), "r", encoding="utf-8") as f:
            plots = json.load(f)

        feats = []
        for feat in plots.get("features", []):
            props = feat.get("properties", {}) or {}
            score = props.get("rank_score", 0.0) or 0.0
            if score < min_score:
                continue
            feats.append((score, feat))
        # Highest rank first; keep Top_N.
        feats.sort(key=lambda t: t[0], reverse=True)
        if top_n > 0:
            feats = feats[:top_n]

        out_dir = os.path.dirname(clean_path(Plots_GeoJSON_Path))
        Plot_Points_Path = os.path.join(out_dir, "bangkok_vacant_plots_points.txt")
        Plot_Counts_Path = os.path.join(out_dir, "bangkok_vacant_plots_counts.txt")

        point_lines, count_lines = [], []
        kept = 0
        for score, feat in feats:
            ring = outer_ring(feat.get("geometry") or {})
            if not ring:
                continue
            xy = [to_xy(lon, lat) for lon, lat in ring]
            simplified = douglas_peucker(xy, DEFAULT_SIMPLIFY_TOL_M)
            if len(simplified) < 3:
                continue
            for x, y in simplified:
                point_lines.append("{:.2f},{:.2f}".format(x, y))
            count_lines.append(str(len(simplified)))

            cx = sum(p[0] for p in simplified) / len(simplified)
            cy = sum(p[1] for p in simplified) / len(simplified)
            props = feat.get("properties", {}) or {}
            Centroids.append("{:.2f},{:.2f}".format(cx, cy))
            Rank_Score.append("{:.4f}".format(float(score)))
            Dist_To_Station.append("{:.1f}".format(float(props.get("dist_to_station_m", -1) or -1)))
            Area_SqM.append("{:.1f}".format(float(props.get("area_sqm", 0) or 0)))
            Source_Class.append(str(props.get("source_class", "")))
            District.append(str(props.get("district", "")))
            kept += 1

        with open(Plot_Points_Path, "w", encoding="utf-8") as f:
            f.write("\n".join(point_lines))
        with open(Plot_Counts_Path, "w", encoding="utf-8") as f:
            f.write("\n".join(count_lines))

        Plot_Count = str(kept)
        Report = (
            "Origin (shared with districts): lon0={:.5f}, lat0={:.5f}\n"
            "Top_N={} | Min_Score={} | Simplify tol={:.0f} m\n"
            "{} plots kept, {} points.\nWrote:\n  {}\n  {}"
        ).format(lon0, lat0, top_n, min_score, DEFAULT_SIMPLIFY_TOL_M,
                 kept, len(point_lines), Plot_Points_Path, Plot_Counts_Path)

    except Exception:
        Report = "ERROR:\n" + traceback.format_exc()
