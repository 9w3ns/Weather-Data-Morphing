#! python 3
# GHPython Script: GeoJSON District Boundaries -> points file + metadata
#
# Inputs:
#   GeoJSON_Path : String (absolute path to bangkok_districts.geojson)
# Outputs:
#   Points_File_Path : String, path to a small text file this script writes:
#                      one "x,y" per line, every district's simplified
#                      boundary points concatenated back to back in
#                      District_Names order.
#   Count_Strings    : FLAT list of String (one number per string), how many
#                      points belong to each district, same order as
#                      District_Names. Sum == number of lines in the file.
#   District_Names   : FLAT list of String, one per district.
#   Report            : String summary / error log.
#
# This Script component's output channel is unreliable for sizeable lists
# (a 50-item string list works, a ~1700-item one comes back empty) --
# looks like a payload/buffer size limit, not a type issue. So the bulk
# point data is written to a file and only the file PATH (a single small
# string) is returned; Count_Strings/District_Names stay small enough to
# come back directly. On the canvas, use native components to read the
# file back in -- these don't cross the same broken boundary:
#   Points_File_Path -> Read File -> Split Text (newline) -> Split Text (comma, x2)
#     -> Text to Number (x2) -> Construct Point
#   Count_Strings -> Text to Number -> Partition List "Size" input
#   Partition List "List" input <- the constructed Points
#   Partition List "Chunk" output -> native Polyline component (Closed=True)
#   Polyline output -> Flatten -> gh_data_matcher.py's Curves input
import json
import math
import os
import traceback

SIMPLIFY_TOLERANCE_M = 50.0

# Initialize outputs
Points_File_Path = None
Count_Strings = []
District_Names = []
Report = "Awaiting GeoJSON path..."


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


if not GeoJSON_Path:
    Report = "Provide a path to bangkok_districts.geojson via GeoJSON_Path."
else:
    try:
        clean_path = str(GeoJSON_Path).strip().strip('"').strip("'")
        with open(clean_path, 'r', encoding='utf-8') as f:
            geojson = json.load(f)

        features = geojson.get('features', [])

        all_lons = []
        all_lats = []
        for feat in features:
            geom = feat['geometry']
            polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
            for poly in polys:
                for ring in poly:
                    for lon, lat in ring:
                        all_lons.append(lon)
                        all_lats.append(lat)

        if not all_lons:
            Report = "No geometry found in {}".format(GeoJSON_Path)
        else:
            lon0 = sum(all_lons) / len(all_lons)
            lat0 = sum(all_lats) / len(all_lats)
            lat0_rad = math.radians(lat0)
            EARTH_RADIUS_M = 6371000.0

            def to_xy(lon, lat):
                x = math.radians(lon - lon0) * EARTH_RADIUS_M * math.cos(lat0_rad)
                y = math.radians(lat - lat0) * EARTH_RADIUS_M
                return x, y

            skipped = 0
            raw_total = 0
            point_lines = []
            for feat in features:
                name = feat.get('properties', {}).get('District', 'Unknown')
                geom = feat['geometry']
                polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]

                best_ring = max((ring for poly in polys for ring in poly), key=len, default=None)
                if not best_ring:
                    skipped += 1
                    continue

                raw_total += len(best_ring)
                xy_pts = [to_xy(lon, lat) for lon, lat in best_ring]
                simplified = douglas_peucker(xy_pts, SIMPLIFY_TOLERANCE_M)

                for x, y in simplified:
                    point_lines.append("{:.2f},{:.2f}".format(x, y))

                Count_Strings.append(str(len(simplified)))
                District_Names.append(name)

            out_path = os.path.join(os.path.dirname(clean_path), "bangkok_points_simplified.txt")
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(point_lines))
            Points_File_Path = out_path

            Report = "Loaded {} district(s), {} points (simplified from {}).\nWrote points to {}".format(
                len(District_Names), len(point_lines), raw_total, out_path)
            if skipped:
                Report += "\n{} feature(s) skipped (no usable geometry).".format(skipped)

    except Exception:
        Report = "ERROR:\n" + traceback.format_exc()
