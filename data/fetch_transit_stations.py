"""
Phase 1 (site selection) transit input: count rapid-transit stations per
Bangkok district, the missing criterion for the MCDA in
docs/SiteSelectionMatrixGemini.md (Tier 1, "Transit & intercept potential").

Source: OpenStreetMap via the Overpass API. We count urban rapid-transit
stations only -- BTS Skytrain + MRT (both tagged station=subway in OSM
Thailand), the Yellow/Pink monorail lines (station=monorail), and the Gold
Line (station=light_rail). Long-distance / commuter heavy rail (SRT mainline,
Airport Rail Link, SRT Red Line; tagged train=yes) is intentionally EXCLUDED,
since the thesis criterion is about the dense commuter-intercept rapid-transit
network, not intercity rail. Flip INCLUDE_HEAVY_RAIL to include it.

Interchange districts naturally score higher because a multi-line interchange
contributes multiple station nodes -- which matches the criterion's intent
(interchanges are the strongest intercept points).

Output: data/gis/bangkok_transit_data.csv
    District, Transit_Station_Count

No heavy dependencies: uses `requests` for the Overpass call and a pure-Python
ray-casting point-in-polygon test to assign each station to a district
(shapely not required).
"""
import csv
import json
import os
import time

import requests

# Rapid-transit station classes to count (OSM `station=` values).
RAPID_TRANSIT_STATION_TYPES = {"subway", "light_rail", "monorail"}
INCLUDE_HEAVY_RAIL = False  # set True to also count train=yes (SRT/ARL/Red Line)

# Bangkok metropolitan bounding box (S, W, N, E).
BBOX = (13.45, 100.30, 14.05, 100.95)

OVERPASS_ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]
USER_AGENT = "thesis-site-selection/1.0 (academic research)"


def fetch_stations():
    s, w, n, e = BBOX
    query = """
    [out:json][timeout:120];
    (
      node[railway=station]({s},{w},{n},{e});
      node[railway=halt]({s},{w},{n},{e});
    );
    out body;
    """.format(s=s, w=w, n=n, e=e)

    last_err = None
    for url in OVERPASS_ENDPOINTS:
        try:
            r = requests.post(url, data={"data": query},
                              headers={"User-Agent": USER_AGENT}, timeout=180)
            if r.status_code == 200:
                print("Overpass OK via {}".format(url))
                return r.json()["elements"]
            last_err = "HTTP {} from {}".format(r.status_code, url)
            print(last_err)
        except Exception as exc:  # network / JSON errors -> try next mirror
            last_err = "{}: {}".format(url, exc)
            print(last_err)
        time.sleep(2)
    raise RuntimeError("All Overpass endpoints failed: {}".format(last_err))


def is_rapid_transit(tags):
    if tags.get("station") in RAPID_TRANSIT_STATION_TYPES:
        return True
    if tags.get("subway") == "yes" or tags.get("light_rail") == "yes" \
            or tags.get("monorail") == "yes":
        return True
    if INCLUDE_HEAVY_RAIL and tags.get("train") == "yes":
        return True
    return False


def point_in_ring(x, y, ring):
    """Ray-casting even-odd test for a single ring of [lon, lat] pairs."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and \
                (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def point_in_polygon(x, y, polygon):
    """polygon = list of rings; ring[0] exterior, rest are holes (even-odd)."""
    inside = False
    for ring in polygon:
        if point_in_ring(x, y, ring):
            inside = not inside
    return inside


def point_in_feature(x, y, geom):
    if geom["type"] == "Polygon":
        return point_in_polygon(x, y, geom["coordinates"])
    if geom["type"] == "MultiPolygon":
        return any(point_in_polygon(x, y, poly) for poly in geom["coordinates"])
    return False


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    geojson_path = os.path.join(base_dir, "gis", "bangkok_districts.geojson")
    out_path = os.path.join(base_dir, "gis", "bangkok_transit_data.csv")

    with open(geojson_path, "r", encoding="utf-8") as f:
        districts = json.load(f)["features"]
    counts = {ft["properties"]["District"]: 0 for ft in districts}

    print("Querying OpenStreetMap for stations in Bangkok bbox {}...".format(BBOX))
    elements = fetch_stations()
    stations = [el for el in elements
                if "lat" in el and "lon" in el and is_rapid_transit(el.get("tags", {}))]
    print("Found {} rapid-transit station nodes (of {} total station/halt nodes)."
          .format(len(stations), len(elements)))

    assigned = 0
    for st in stations:
        x, y = st["lon"], st["lat"]
        for ft in districts:
            if point_in_feature(x, y, ft["geometry"]):
                counts[ft["properties"]["District"]] += 1
                assigned += 1
                break
    print("Assigned {} stations to districts ({} fell outside all districts)."
          .format(assigned, len(stations) - assigned))

    rows = sorted(({"District": d, "Transit_Station_Count": c}
                   for d, c in counts.items()),
                  key=lambda r: -r["Transit_Station_Count"])
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["District", "Transit_Station_Count"])
        writer.writeheader()
        writer.writerows(rows)

    print("Wrote {} districts to {}".format(len(rows), out_path))
    print("Top transit districts:")
    for r in rows[:8]:
        print("  {:<28} {}".format(r["District"], r["Transit_Station_Count"]))


if __name__ == "__main__":
    main()
