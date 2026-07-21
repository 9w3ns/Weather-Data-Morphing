#! python 3
# GHPython Script: inferred BMA-owned land -> points file + per-site attrs
#
# Renders the BMA land sites from data/build_bma_land_layer.py as curves on the
# canvas, in the SAME local XY frame as your district curves
# (gh_geojson_to_curves.py), LCZ grid, transit network, land-use zones and
# candidate vacant plots -- so it overlays with no extra registration. Read it
# against gh_vacant_plots.py: those are plots that LOOK empty, these are plots the
# city appears to OWN. Different questions, deliberately separate layers.
#
# INFERRED, NOT A TITLE SEARCH: ownership is deduced from BMA operating a facility
# on the land, because Bangkok's real land-asset registry (asset.bangkok.go.th) is
# not public. Filter to Confidence == "high" for siting; anything lower is a lead
# to verify, not a fact. Watch Land_Owner_Risk: "temple_land" means the city runs
# the facility but a wat owns the ground -- do NOT site on those.
#
# Inputs:
#   Land_GeoJSON_Path   : String, path to data/gis/bangkok_bma_land.geojson
#   Origin_GeoJSON_Path : String, path to data/gis/bangkok_districts.geojson
#                         (projection origin -- wire the SAME file as the other
#                         gh_ scripts or the layers will be offset).
#   Top_N               : int, keep only the N largest sites (default 300;
#                         0 = keep all). Caps GH load.
#   Min_Area            : Float, drop sites below this area in sqm (default 0).
# Outputs:
#   Site_Points_Path : String, path to a text file: one "x,y" per line, every
#                      kept site's simplified outer ring, back to back.
#   Site_Counts_Path : String, path to a text file: one integer per line, the
#                      point count of each site (same order). sum == lines in
#                      the points file; line count == number of sites.
#   Centroids        : List of String "x,y", one per site (same order), for tags.
#   Area_SqM         : List of String, site area (same order).
#   Category         : List of String, facility class per site (district_office/
#                      school/market/park/...) (same order).
#   Confidence       : List of String, high/medium/low ownership confidence
#                      (same order) -- colour or filter by this.
#   Land_Owner_Risk  : List of String, "temple_land" or "none" (same order).
#   Site_Name        : List of String, Thai facility name (same order).
#   District         : List of String, district per site (same order).
#   Building_Year    : List of String, district-office building construction/
#                      opening year CE (same order); "" if unknown or not an
#                      office. From data/gis/district_office_building_age.csv,
#                      joined by data/enrich_office_building_age.py.
#   Building_Era     : List of String, coarse lifecycle bucket for colouring
#                      (same order): "Pre-1970 (historic)", "1970-1999",
#                      "2000-present", "Leased (not BMA bldg)", "Unknown", or
#                      "" (non-office). Colour offices by era:
#                        filter Category == "district_office" -> Member Index
#                        Building_Era against that 5-item list -> Colour Swatch.
#   Site_Count       : String, number of sites kept.
#   Report           : String summary / error log.
#
# Bulk ring geometry goes to files (this Script component drops big lists); the
# per-site attribute lists stay small (<= Top_N) so they return directly, same
# split as gh_vacant_plots.py / gh_landuse_zones.py. Rebuild curves natively:
#   Site_Points_Path -> Read File -> Split Text(\n) -> Split Text(",", x2)
#     -> Number -> Construct Point => Points
#   Site_Counts_Path -> Read File -> Split Text(\n) -> Number => Sizes
#   Partition List (List=Points, Size=Sizes) -> Polyline (Closed=True) -> Flatten
#   Confidence -> Member Index against ("high","medium","low") -> Colour Swatch
import json
import math
import os
import traceback

DEFAULT_TOP_N = 300
DEFAULT_SIMPLIFY_TOL_M = 8.0  # match gh_vacant_plots.py so plots and land register

# Initialize outputs
Site_Points_Path = None
Site_Counts_Path = None
Centroids = []
Area_SqM = []
Category = []
Confidence = []
Land_Owner_Risk = []
Site_Name = []
District = []
Building_Year = []
Building_Era = []
Site_Count = "0"
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


if not (Land_GeoJSON_Path and Origin_GeoJSON_Path):
    Report = "Provide Land_GeoJSON_Path and Origin_GeoJSON_Path."
else:
    try:
        top_n = int(Top_N) if "Top_N" in globals() and Top_N not in (None, "") else DEFAULT_TOP_N
        min_area = float(Min_Area) if "Min_Area" in globals() and Min_Area not in (None, "") else 0.0

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

        with open(clean_path(Land_GeoJSON_Path), "r", encoding="utf-8") as f:
            land = json.load(f)

        feats = []
        for feat in land.get("features", []):
            props = feat.get("properties", {}) or {}
            area = props.get("site_area_sqm", 0.0) or 0.0
            if area < min_area:
                continue
            feats.append((area, feat))
        # Largest site first; keep Top_N.
        feats.sort(key=lambda t: t[0], reverse=True)
        if top_n > 0:
            feats = feats[:top_n]

        out_dir = os.path.dirname(clean_path(Land_GeoJSON_Path))
        Site_Points_Path = os.path.join(out_dir, "bangkok_bma_land_points.txt")
        Site_Counts_Path = os.path.join(out_dir, "bangkok_bma_land_counts.txt")

        point_lines, count_lines = [], []
        kept = 0
        for area, feat in feats:
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
            Area_SqM.append("{:.1f}".format(float(area)))
            Category.append(str(props.get("category", "")))
            Confidence.append(str(props.get("ownership_confidence", "")))
            Land_Owner_Risk.append(str(props.get("land_owner_risk", "")))
            Site_Name.append(str(props.get("name", "")))
            District.append(str(props.get("district", "")))
            Building_Year.append(str(props.get("building_year_ce", "")))
            Building_Era.append(str(props.get("building_era", "")))
            kept += 1

        with open(Site_Points_Path, "w", encoding="utf-8") as f:
            f.write("\n".join(point_lines))
        with open(Site_Counts_Path, "w", encoding="utf-8") as f:
            f.write("\n".join(count_lines))

        Site_Count = str(kept)
        n_high = sum(1 for c in Confidence if c == "high")
        n_temple = sum(1 for r in Land_Owner_Risk if r == "temple_land")
        Report = (
            "Origin (shared with districts): lon0={:.5f}, lat0={:.5f}\n"
            "Top_N={} | Min_Area={} | Simplify tol={:.0f} m\n"
            "{} sites kept, {} points.\n"
            "{} high-confidence | {} flagged temple_land (city operates, wat owns).\n"
            "INFERRED ownership -- verify before siting.\nWrote:\n  {}\n  {}"
        ).format(lon0, lat0, top_n, min_area, DEFAULT_SIMPLIFY_TOL_M,
                 kept, len(point_lines), n_high, n_temple,
                 Site_Points_Path, Site_Counts_Path)

    except Exception:
        Report = "ERROR:\n" + traceback.format_exc()
