"""
Transit *network* exporter for Grasshopper centrality analysis (route B in the
site-selection discussion). Unlike data/fetch_transit_stations.py (which just
counts stations per district), this builds the actual rail NETWORK -- station
nodes + the edges connecting consecutive stations along each line -- so a GH
network-analysis plugin (DeCodingSpaces Toolbox / Urbano) can compute
centrality (degree / betweenness / closeness) directly on the geometry.

Coordinates are projected into the SAME local planar XY (meters,
equirectangular, centered on the mean district vertex) used by
data/gis/gh_geojson_to_curves.py and data/fetch_lcz_grid.py, so the network
drops onto the existing GH canvas already aligned with the district curves and
LCZ grid -- no manual registration.

LINES INCLUDED: all route=subway + route=monorail (BTS Sukhumvit, BTS Silom,
Gold Line, MRT Blue, MRT Purple, MRT Pink, MRT Yellow) and route=train where
network=ARL (Airport Rail Link).

LINES EXCLUDED (deliberately): SRT commuter/heavy rail -- SRT Red Line
(Dark/Light), BKK Commuter (Don Mueang-Ayutthaya), SRT Mahachai line -- and the
Suvarnabhumi airport-internal APM (route=light_rail). SRT is excluded because
the thesis criterion targets the dense urban rapid-transit intercept network;
note this exclusion in the methodology.

Interchange handling: stop points from different lines within
CLUSTER_RADIUS_M of each other are merged into ONE network node, so an
interchange (e.g., Asok/Sukhumvit, Siam, Mo Chit/Chatuchak) becomes a single
high-degree node that actually connects its lines -- essential for centrality.

Outputs:
    data/gis/bangkok_transit_nodes.csv  (Node_ID, Name, Lines, Degree, Lat, Lon, X, Y, District)
    data/gis/bangkok_transit_edges.csv  (From_ID, To_ID, Lines, From_X, From_Y, To_X, To_Y)

Requires: `requests` (OSM Overpass). No shapely; pure-Python geometry.
"""
import csv
import json
import math
import os
import time

import requests

BBOX = (13.45, 100.30, 14.05, 100.95)  # S, W, N, E
CLUSTER_RADIUS_M = 250.0                # merge stops closer than this into one node
EARTH_RADIUS_M = 6371000.0
USER_AGENT = "thesis-site-selection/1.0 (academic research)"
OVERPASS_ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]


def clean_line_name(tags):
    """Map an OSM route relation to a clean English line name, or None to skip."""
    route = tags.get("route", "")
    ref = tags.get("ref", "") or ""
    net = tags.get("network", "") or ""
    if route == "train":
        return "ARL" if net == "ARL" else None            # keep ARL, drop SRT
    if route == "light_rail":
        return None                                        # airport-internal APM
    if route not in ("subway", "monorail"):
        return None
    table = {
        "MRT-BL": "MRT Blue", "MRT Purple": "MRT Purple", "MRT Pink": "MRT Pink",
        "MRT Yellow": "MRT Yellow",
    }
    if ref in table:
        return table[ref]
    if "Gold" in ref:
        return "Gold Line"
    if "สุขุมวิท" in ref:   # สุขุมวิท
        return "BTS Sukhumvit"
    if "สีลม" in ref:                          # สีลม
        return "BTS Silom"
    if "ชมพู" in (tags.get("name", "")):       # สีชมพู Pink (branch, no ref)
        return "MRT Pink"
    return "{} {}".format(route, ref).strip()             # fallback: keep, labelled


def overpass(query):
    last = None
    for url in OVERPASS_ENDPOINTS:
        try:
            r = requests.post(url, data={"data": query},
                              headers={"User-Agent": USER_AGENT}, timeout=200)
            if r.status_code == 200 and r.text.strip().startswith("{"):
                print("Overpass OK via {}".format(url))
                return r.json()["elements"]
            last = "HTTP {} ({} bytes) {}".format(r.status_code, len(r.text), url)
            print(last)
        except Exception as exc:
            last = "{}: {}".format(url, exc)
            print(last)
        time.sleep(3)
    raise RuntimeError("All Overpass endpoints failed: {}".format(last))


def compute_origin(geojson):
    lons, lats = [], []
    for feat in geojson["features"]:
        geom = feat["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys:
            for ring in poly:
                for lon, lat in ring:
                    lons.append(lon); lats.append(lat)
    return sum(lons) / len(lons), sum(lats) / len(lats)


def make_to_xy(lon0, lat0):
    lat0_rad = math.radians(lat0)

    def to_xy(lon, lat):
        return (math.radians(lon - lon0) * EARTH_RADIUS_M * math.cos(lat0_rad),
                math.radians(lat - lat0) * EARTH_RADIUS_M)
    return to_xy


def meters_between(a, b):
    (lon1, lat1), (lon2, lat2) = a, b
    latm = math.radians((lat1 + lat2) / 2)
    dx = math.radians(lon2 - lon1) * EARTH_RADIUS_M * math.cos(latm)
    dy = math.radians(lat2 - lat1) * EARTH_RADIUS_M
    return math.hypot(dx, dy)


def point_in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]; xj, yj = ring[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def district_of(lon, lat, districts):
    for ft in districts:
        geom = ft["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys:
            if any(point_in_ring(lon, lat, ring) for ring in poly):
                return ft["properties"]["District"]
    return ""


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    geojson_path = os.path.join(base, "gis", "bangkok_districts.geojson")
    nodes_out = os.path.join(base, "gis", "bangkok_transit_nodes.csv")
    edges_out = os.path.join(base, "gis", "bangkok_transit_edges.csv")

    with open(geojson_path, encoding="utf-8") as f:
        geojson = json.load(f)
    lon0, lat0 = compute_origin(geojson)
    to_xy = make_to_xy(lon0, lat0)
    districts = geojson["features"]

    s, w, n, e = BBOX
    query = """
    [out:json][timeout:200];
    (
      relation[type=route][route=subway]({s},{w},{n},{e});
      relation[type=route][route=monorail]({s},{w},{n},{e});
      relation[type=route][route=train][network=ARL]({s},{w},{n},{e});
    )->.r;
    (.r; .r >;);
    out body;
    """.format(s=s, w=w, n=n, e=e)

    print("Fetching transit route relations + members from OSM...")
    elements = overpass(query)

    node_coords = {}   # osm node id -> (lon, lat) and tags
    node_tags = {}
    relations = []
    for el in elements:
        if el["type"] == "node":
            node_coords[el["id"]] = (el["lon"], el["lat"])
            node_tags[el["id"]] = el.get("tags", {})
        elif el["type"] == "relation":
            relations.append(el)

    # Build ordered stop sequences per included line.
    line_sequences = []  # list of (line_name, [osm_node_id ordered])
    for rel in relations:
        line = clean_line_name(rel.get("tags", {}))
        if not line:
            continue
        stops = [m["ref"] for m in rel.get("members", [])
                 if m["type"] == "node" and m.get("role", "").startswith("stop")
                 and m["ref"] in node_coords]
        if len(stops) < 2:  # fall back to platform nodes if no stop_position role
            stops = [m["ref"] for m in rel.get("members", [])
                     if m["type"] == "node" and m.get("role", "").startswith("platform")
                     and m["ref"] in node_coords]
        if len(stops) >= 2:
            line_sequences.append((line, stops))

    # Collapse to ONE canonical sequence per line (the longest variant), so
    # directional duplicates and partial short-turn "reinforcement" services
    # don't inject phantom shortcut edges that inflate node degree.
    canonical = {}
    for line, stops in line_sequences:
        if line not in canonical or len(stops) > len(canonical[line]):
            canonical[line] = stops
    line_sequences = [(line, stops) for line, stops in canonical.items()]

    # Cluster stop points into stations (interchange merging).
    clusters = []  # each: {"pts":[(lon,lat)], "lines":set, "names":set, "cx","cy"}
    osmid_to_cluster = {}

    def find_cluster(lon, lat):
        for idx, c in enumerate(clusters):
            if meters_between((lon, lat), (c["cx"], c["cy"])) <= CLUSTER_RADIUS_M:
                return idx
        return None

    for line, stops in line_sequences:
        for nid in stops:
            if nid in osmid_to_cluster:
                clusters[osmid_to_cluster[nid]]["lines"].add(line)
                continue
            lon, lat = node_coords[nid]
            ci = find_cluster(lon, lat)
            if ci is None:
                clusters.append({"pts": [(lon, lat)], "lines": {line}, "names": set(),
                                 "cx": lon, "cy": lat})
                ci = len(clusters) - 1
            else:
                clusters[ci]["pts"].append((lon, lat))
                clusters[ci]["lines"].add(line)
                lons = [p[0] for p in clusters[ci]["pts"]]
                lats = [p[1] for p in clusters[ci]["pts"]]
                clusters[ci]["cx"] = sum(lons) / len(lons)
                clusters[ci]["cy"] = sum(lats) / len(lats)
            osmid_to_cluster[nid] = ci
            nm = node_tags[nid].get("name:en") or node_tags[nid].get("name")
            if nm:
                clusters[ci]["names"].add(nm)

    # Edges: consecutive distinct clusters along each line (undirected, deduped).
    edges = {}  # frozenset(pair) -> set(lines)
    for line, stops in line_sequences:
        seq = [osmid_to_cluster[nid] for nid in stops]
        for a, b in zip(seq, seq[1:]):
            if a == b:
                continue
            key = frozenset((a, b))
            edges.setdefault(key, set()).add(line)

    degree = {i: 0 for i in range(len(clusters))}
    for a, b in edges:
        degree[a] += 1; degree[b] += 1

    # Write nodes.
    with open(nodes_out, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["Node_ID", "Name", "Lines", "Degree", "Lat", "Lon", "X", "Y", "District"])
        for i, c in enumerate(clusters):
            x, y = to_xy(c["cx"], c["cy"])
            name = sorted(c["names"])[0] if c["names"] else ""
            wr.writerow([i, name, "|".join(sorted(c["lines"])), degree[i],
                         round(c["cy"], 6), round(c["cx"], 6),
                         round(x, 2), round(y, 2),
                         district_of(c["cx"], c["cy"], districts)])

    # Write edges.
    with open(edges_out, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["From_ID", "To_ID", "Lines", "From_X", "From_Y", "To_X", "To_Y"])
        for key, lines in edges.items():
            a, b = tuple(key)
            ax, ay = to_xy(clusters[a]["cx"], clusters[a]["cy"])
            bx, by = to_xy(clusters[b]["cx"], clusters[b]["cy"])
            wr.writerow([a, b, "|".join(sorted(lines)),
                         round(ax, 2), round(ay, 2), round(bx, 2), round(by, 2)])

    lines_found = sorted({ln for ln, _ in line_sequences})
    interchanges = sum(1 for i in range(len(clusters)) if len(clusters[i]["lines"]) > 1)
    print("\nLines included ({}): {}".format(len(lines_found), ", ".join(lines_found)))
    print("Stations (network nodes): {}".format(len(clusters)))
    print("Edges (station-to-station links): {}".format(len(edges)))
    print("Interchange nodes (>=2 lines): {}".format(interchanges))
    print("\nHighest-degree nodes (interchange hubs):")
    for i in sorted(range(len(clusters)), key=lambda i: -degree[i])[:8]:
        nm = sorted(clusters[i]["names"])[0] if clusters[i]["names"] else "(unnamed)"
        print("  deg {}  {:<22} lines: {}".format(
            degree[i], nm, ", ".join(sorted(clusters[i]["lines"]))))
    print("\nWrote {}\n      {}".format(nodes_out, edges_out))
    print("NOTE: SRT Red Line / BKK Commuter / SRT Mahachai and the Suvarnabhumi "
          "airport APM were excluded by design (see module docstring).")


if __name__ == "__main__":
    main()
