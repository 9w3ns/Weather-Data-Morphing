"""Fetch real cadastral land parcels for Bangkok from the BMA's own GIS server.

Source: Bangkok Metropolitan Administration, Department of City Planning and
Urban Development (สำนักการวางผังและพัฒนาเมือง) ArcGIS server --
    SERVICE_PUBLIC/Parcel/MapServer/0, layer "รูปแปลงที่ดิน"
2,220,982 parcel polygons covering all 50 districts, public and unauthenticated.

WHY THIS EXISTS: fetch_vacant_plots_osm.py approximates plots with OSM `landuse`
polygons, which are tagging artefacts rather than property boundaries. This layer
is the real cadastral fabric -- true plot geometry, true areas.

WHAT IT DOES NOT GIVE YOU: the layer carries NO attributes. Its only field is
OBJECTID -- no owner, no title deed number (โฉนด), no land use, not even a
district. It answers "where are the plot boundaries", never "whose plot is this".
Ownership is INFERRED separately by build_bma_land_layer.py, which joins these
parcels against BMA-operated facilities from fetch_bma_facilities.py. See
docs/bma_land_sourcing_notes.md for why the authoritative ownership registry
(asset.bangkok.go.th) could not be used.

VINTAGE UNKNOWN: the service publishes no description and no metadata date, so
how current these parcels are cannot be established from the service itself.

SCOPE: district-scoped. All 2.2M parcels would take 2,200+ requests against a
public government server; the thesis only needs the Tier 1 shortlist districts.

PAGING: the service caps every response at 1000 features (maxRecordCount) and
flags truncation with `exceededTransferLimit`. We do NOT use resultOffset paging
-- the server is ArcGIS 10.71 and does not advertise pagination support. Instead
any envelope that returns truncated is split into four and re-queried,
recursively. Slower, but provably complete.

Run from the repo root: paths are relative and cache/ is shared with OSMnx's own
response cache.

Output: data/gis/bangkok_parcels_<district_slug>.geojson  (EPSG:4326)
    parcel_id, district, area_sqm
"""
import argparse
import hashlib
import json
import os
import time

import geopandas as gpd
import requests

# --- Configuration ---------------------------------------------------------
UTM47N = 32647  # projected CRS for Bangkok (metres); also the service's native SR
SERVICE_URL = ("https://cityplangis.bangkok.go.th/arcgis/rest/services/"
               "SERVICE_PUBLIC/Parcel/MapServer/0/query")
USER_AGENT = "thesis-site-selection/1.0 (academic research)"
CACHE_DIR = "cache"

# Tier 1 winners from docs/SiteSelectionMatrixGemini.md / site_selection_scores.csv.
DEFAULT_DISTRICTS = ["Bang Rak", "Sathon", "Khlong Toei"]

MAX_RECORD_COUNT = 1000  # server-side cap; a response this size is assumed truncated
MIN_TILE_M = 50.0        # floor on subdivision, so recursion always terminates
REQUEST_SLEEP_S = 0.5    # be gentle: one government server, no mirror to fail over to
MAX_RETRIES = 3


def normalize_name(name):
    n = str(name).strip().lower()
    for token in ("khet ", " district"):
        n = n.replace(token, "")
    return n.strip()


def slugify(name):
    return normalize_name(name).replace(" ", "_")


def _cache_path(params):
    key = hashlib.sha1(json.dumps(params, sort_keys=True).encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, "parcel_{}.json".format(key))


def query_envelope(xmin, ymin, xmax, ymax):
    """One Query call against the parcel layer for a UTM47N envelope.

    Responses are cached to cache/ keyed by a hash of the request, so re-runs and
    interrupted runs cost nothing.
    """
    params = {
        "where": "1=1",
        "geometry": json.dumps({"xmin": xmin, "ymin": ymin,
                                "xmax": xmax, "ymax": ymax,
                                "spatialReference": {"wkid": UTM47N}}),
        "geometryType": "esriGeometryEnvelope",
        "inSR": str(UTM47N),
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson",
    }

    cache_file = _cache_path(params)
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as fh:
            return json.load(fh)

    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(SERVICE_URL, params=params,
                             headers={"User-Agent": USER_AGENT}, timeout=180)
            if r.status_code == 200:
                data = r.json()
                if "error" in data:
                    raise RuntimeError("service error: {}".format(data["error"]))
                os.makedirs(CACHE_DIR, exist_ok=True)
                with open(cache_file, "w", encoding="utf-8") as fh:
                    json.dump(data, fh)
                time.sleep(REQUEST_SLEEP_S)
                return data
            last_err = "HTTP {}".format(r.status_code)
        except Exception as exc:  # network / JSON / service errors
            last_err = str(exc)
        time.sleep(2 * (attempt + 1))  # linear backoff
    raise RuntimeError("Parcel query failed after {} attempts ({}): {}".format(
        MAX_RETRIES, (xmin, ymin, xmax, ymax), last_err))


def fetch_recursive(xmin, ymin, xmax, ymax, features, stats, depth=0):
    """Collect every parcel intersecting an envelope, subdividing on truncation.

    Parcels straddling a cut line are returned by more than one child tile; the
    caller de-duplicates on OBJECTID.
    """
    data = query_envelope(xmin, ymin, xmax, ymax)
    feats = data.get("features", [])
    truncated = bool(data.get("exceededTransferLimit")) or len(feats) >= MAX_RECORD_COUNT

    if truncated and (xmax - xmin) > MIN_TILE_M and (ymax - ymin) > MIN_TILE_M:
        mx, my = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0
        for tile in ((xmin, ymin, mx, my), (mx, ymin, xmax, my),
                     (xmin, my, mx, ymax), (mx, my, xmax, ymax)):
            fetch_recursive(tile[0], tile[1], tile[2], tile[3],
                            features, stats, depth + 1)
        return

    if truncated:
        # Only reachable if >1000 parcels sit inside a 50 m tile, which should not
        # happen in Bangkok. Surface it rather than silently dropping parcels.
        stats["truncated_tiles"] += 1
        print("\n   ! tile at min size STILL truncated ({} feats) -- parcels may be "
              "missing here: {}".format(len(feats), (xmin, ymin, xmax, ymax)))

    features.extend(feats)
    stats["tiles"] += 1
    stats["max_depth"] = max(stats["max_depth"], depth)
    print("   . {} tiles fetched, {} raw parcels".format(stats["tiles"], len(features)),
          end="\r")


def fetch_parcels(district_names):
    districts_path = "data/gis/bangkok_districts.geojson"

    districts = gpd.read_file(districts_path)
    districts_proj = districts.to_crs(epsg=UTM47N)

    wanted = {normalize_name(d) for d in district_names}
    sel = districts_proj[districts_proj["District"].apply(
        lambda d: normalize_name(d) in wanted)]
    found = {normalize_name(d) for d in sel["District"]}
    missing = wanted - found
    if missing:
        raise SystemExit("Unknown district(s): {}\nAvailable: {}".format(
            sorted(missing), sorted(districts["District"].unique())))

    for _, row in sel.iterrows():
        name = row["District"]
        slug = slugify(name)
        out_path = "data/gis/bangkok_parcels_{}.geojson".format(slug)
        print("\n=== {} ===".format(name))

        xmin, ymin, xmax, ymax = row.geometry.bounds
        print("1. Fetching parcels ({:.1f} x {:.1f} km bbox)...".format(
            (xmax - xmin) / 1000.0, (ymax - ymin) / 1000.0))
        features = []
        stats = {"tiles": 0, "max_depth": 0, "truncated_tiles": 0}
        fetch_recursive(xmin, ymin, xmax, ymax, features, stats)
        print("\n   - {} tiles, max depth {}, {} raw features.".format(
            stats["tiles"], stats["max_depth"], len(features)))
        if not features:
            print("   ! no parcels returned; skipping {}.".format(name))
            continue

        print("2. De-duplicating and clipping to district...")
        gdf = gpd.GeoDataFrame.from_features(features, crs=4326)
        gdf = gdf.drop_duplicates("OBJECTID").to_crs(epsg=UTM47N)
        before = len(gdf)

        # The bbox is not the district: keep parcels whose centroid falls inside
        # the real boundary (same centroid convention as fetch_vacant_plots_osm.py).
        centroids = gdf.geometry.centroid
        gdf = gdf[centroids.within(row.geometry)].copy()
        print("   - {} unique parcels, {} inside {}.".format(before, len(gdf), name))
        if gdf.empty:
            print("   ! nothing inside the district boundary; skipping.")
            continue

        gdf["area_sqm"] = gdf.geometry.area
        gdf["district"] = name
        gdf = gdf.rename(columns={"OBJECTID": "parcel_id"})

        print("3. Writing output...")
        out = gdf[["parcel_id", "district", "area_sqm", "geometry"]].to_crs(epsg=4326)
        out.to_file(out_path, driver="GeoJSON")
        print("   - {}".format(out_path))
        print("   - area: median {:.0f} sqm, total {:.2f} sq km".format(
            gdf["area_sqm"].median(), gdf["area_sqm"].sum() / 1e6))

    print("\nDone. These are plot BOUNDARIES only -- the layer carries no owner "
          "attribute.\nRun build_bma_land_layer.py to infer which parcels are BMA's.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--districts", nargs="+", default=DEFAULT_DISTRICTS,
                    help="District names to fetch (default: %(default)s). "
                         "Matching ignores the 'District'/'Khet' suffix.")
    args = ap.parse_args()
    fetch_parcels(args.districts)
