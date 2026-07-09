#! python 3
"""
GHPython Script: GeoJSON District Boundaries -> Rhino Curves
Author: Antigravity

Inputs:
    GeoJSON_Path : String (absolute path to bangkok_districts.geojson)
Outputs:
    Curves         : List of Curve, one closed boundary curve per district.
    District_Names : List of String, aligned 1:1 with Curves.
    Report         : String summary / error log.

Reprojects lon/lat to a local equirectangular XY (meters) centered on the
dataset's own bounding box, since GeoJSON coordinates are degrees and Rhino
expects a planar unit system.
"""
import json
import math
import traceback
import Rhino.Geometry as rg

# Initialize outputs
Curves = []
District_Names = []
Report = "Awaiting GeoJSON path..."

if not GeoJSON_Path:
    Report = "Provide a path to bangkok_districts.geojson via GeoJSON_Path."
else:
    try:
        with open(GeoJSON_Path, 'r', encoding='utf-8') as f:
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
            for feat in features:
                name = feat.get('properties', {}).get('District', 'Unknown')
                geom = feat['geometry']
                polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]

                # One Curve per district: take the largest ring (by point
                # count) so output stays 1:1 with District_Names, which is
                # what gh_data_matcher.py expects downstream.
                best_ring = max((ring for poly in polys for ring in poly), key=len, default=None)
                if not best_ring:
                    skipped += 1
                    continue

                pts = [rg.Point3d(x, y, 0.0) for x, y in (to_xy(lon, lat) for lon, lat in best_ring)]
                polyline = rg.Polyline(pts)
                Curves.append(polyline.ToPolylineCurve())
                District_Names.append(name)

            Report = "Loaded {} district curves from {}".format(len(Curves), GeoJSON_Path)
            if skipped:
                Report += "\n{} feature(s) skipped (no usable geometry).".format(skipped)

    except Exception:
        Report = "ERROR:\n" + traceback.format_exc()
