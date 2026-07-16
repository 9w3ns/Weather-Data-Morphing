"""Fetch BMA-operated facilities: the ownership SEEDS for the BMA land map.

Sibling of fetch_bma_parcels.py. That script gets real cadastral plot boundaries
but no owner attribute; this one gets things we know the city operates. A BMA
district office / BMA school / BMA health centre sits on BMA land, so the parcels
underneath one are the city's. build_bma_land_layer.py does that join.

WHY THIS IS AN INFERENCE, NOT A REGISTRY: Bangkok's authoritative land-asset
system (asset.bangkok.go.th, สำนักการคลัง) is login-gated and no public export
exists -- see docs/bma_land_sourcing_notes.md. Operating a facility is strong
evidence of owning the land under it, but it is not a title deed. BMA does lease
some sites, and this cannot detect that.

TWO SOURCES, DELIBERATELY WEIGHTED DIFFERENTLY:
  1. BMA open data -- ที่ตั้งโรงเรียนในสังกัดกรุงเทพมหานคร (bma_school.csv, 437
     schools with lat/lng). An authoritative BMA registry -> `high`.
  2. OpenStreetMap -- broader coverage and real footprint polygons, but
     `operator` tagging in Bangkok is sparse, so most rows can only be `low`.

THE FALSE-POSITIVE THAT MATTERS: "public-looking" is not "BMA's". Bangkok is full
of Crown Property Bureau, State Railway (SRT), Port Authority and Treasury
(ราชพัสดุ) land, and national ministries sit on Treasury land, not the city's.
Anything whose operator matches NOT_BMA_PATTERNS is dropped outright rather than
downgraded. Category defaults are deliberately pessimistic for the same reason:
for a hard ownership gate, precision beats recall.

Outputs (both EPSG:4326):
    data/gis/bangkok_bma_facilities.geojson
        facility_id, name, category, operator_raw, ownership_confidence, source
    data/gis/bangkok_temple_land.geojson
        temple compounds -- an EXCLUSION layer. Most BMA schools are วัด schools
        on temple land: the city runs the school, the temple owns the ground.
        See fetch_temple_land().
"""
import io
import re
import warnings

import geopandas as gpd
import osmnx as ox
import pandas as pd
import requests

warnings.filterwarnings("ignore")

# --- Configuration ---------------------------------------------------------
UTM47N = 32647
USER_AGENT = "thesis-site-selection/1.0 (academic research)"

BMA_SCHOOL_CSV = ("https://data.bangkok.go.th/dataset/"
                  "7153ce14-741f-4715-ad90-01f59925940c/resource/"
                  "0eb615c4-f9a5-43a6-89c6-bcd3257aab53/download/bma_school.csv")

# OSM tags to pull. Broad on purpose -- classify_category + the confidence table
# below do the filtering, so we can see what was rejected and why.
OSM_TAGS = {
    "amenity": ["townhall", "school", "marketplace", "fire_station", "library",
                "community_centre", "clinic"],
    "office": "government",
    "leisure": "park",
    "healthcare": "centre",
}

# Operator/owner strings that mean "the city owns this". Matched against the
# operator* / owner tags ONLY -- never against `name`, because names like
# "มหาวิทยาลัยกรุงเทพ" (Bangkok University, private) would match on the city name
# and quietly poison the high-confidence set.
BMA_OPERATOR_PATTERNS = [
    "กรุงเทพมหานคร", "กทม", "สำนักงานเขต", "สำนักอนามัย", "สำนักสิ่งแวดล้อม",
    r"\bbangkok metropolitan\b", r"\bbma\b",
]

# Operators that read institutional but are NOT the city. These are the dangerous
# false positives; drop them outright.
NOT_BMA_PATTERNS = [
    "ทรัพย์สินพระมหากษัตริย์", "ทรัพย์สินส่วนพระมหากษัตริย์",  # Crown Property Bureau
    "การรถไฟ",                                                    # SRT
    "การท่าเรือ",                                                 # Port Authority
    "กรมธนารักษ์", "ราชพัสดุ",                                    # Treasury / state land
    "กองทัพ", "ทหาร",                                             # military
    "จุฬาลงกรณ์มหาวิทยาลัย",                                       # Chulalongkorn (major landowner)
    r"\bcrown property\b", r"\bstate railway\b", r"\bport authority\b",
    r"\btreasury\b", r"\broyal thai (army|navy|air force)\b",
]

# Default confidence per category when no operator tag settles it. Pessimistic by
# design -- see module docstring.
CATEGORY_DEFAULT_CONF = {
    "district_office": "high",    # amenity=townhall in Bangkok is สำนักงานเขต / City Hall: always BMA
    "health_centre": "medium",    # ศูนย์บริการสาธารณสุข is BMA (สำนักอนามัย), but the tag also catches private clinics
    "fire_station": "medium",     # BMA runs these (สำนักป้องกันและบรรเทาสาธารณภัย)
    "school": "low",              # most Bangkok schools are private or Ministry of Education; only the BMA registry lifts one to high
    "park": "low",                # BMA runs many parks -- but so do Crown Property, the Army and private developers
    "market": "low",              # most Bangkok markets are private
    "library": "low",
    "community_centre": "low",
    "government_office": "low",   # ministries sit on Treasury land (ราชพัสดุ), NOT the city's
}

def _matches(text, patterns):
    if not isinstance(text, str) or not text.strip():
        return False
    t = text.strip().lower()
    for p in patterns:
        if p.startswith(r"\b"):          # latin pattern -> word-boundary regex
            if re.search(p, t):
                return True
        elif p in t:                      # thai pattern -> plain containment
            return True
    return False


def classify_category(row):
    """Map OSM tags to one of CATEGORY_DEFAULT_CONF's categories (or None)."""
    amenity = row.get("amenity")
    if amenity == "townhall":
        return "district_office"
    if amenity == "school":
        return "school"
    if amenity == "marketplace":
        return "market"
    if amenity == "fire_station":
        return "fire_station"
    if amenity == "library":
        return "library"
    if amenity == "community_centre":
        return "community_centre"
    if row.get("healthcare") == "centre" or amenity == "clinic":
        return "health_centre"
    if row.get("leisure") == "park":
        return "park"
    if row.get("office") == "government":
        return "government_office"
    return None


def operator_text(row):
    """Concatenate the operator/owner tags only -- deliberately excludes `name`."""
    parts = []
    for key in ("operator", "operator:en", "operator:th", "owner", "owner:en"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())
    return " | ".join(parts)


def fetch_bma_schools():
    """The authoritative BMA school registry (437 points, lat/lng)."""
    r = requests.get(BMA_SCHOOL_CSV, headers={"User-Agent": USER_AGENT}, timeout=180)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.content.decode("utf-8-sig")))
    df = df.dropna(subset=["lat", "lng"])
    gdf = gpd.GeoDataFrame(
        pd.DataFrame({
            "name": df["name"].astype(str).str.strip(),
            "category": "school",
            "operator_raw": "BMA school registry (data.bangkok.go.th)",
            "ownership_confidence": "high",
            "source": "bma_open_data",
        }),
        geometry=gpd.points_from_xy(df["lng"], df["lat"]),
        crs=4326,
    )
    return gdf


def fetch_osm_facilities():
    ox.settings.timeout = 1800
    ox.settings.use_cache = True
    gdf = ox.features_from_place("Bangkok, Thailand", tags=OSM_TAGS)
    gdf = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon", "Point"])].copy()

    for col in ("amenity", "office", "leisure", "healthcare", "name",
                "operator", "operator:en", "operator:th", "owner", "owner:en"):
        if col not in gdf.columns:
            gdf[col] = None

    gdf["category"] = gdf.apply(classify_category, axis=1)
    gdf = gdf[gdf["category"].notna()].copy()
    gdf["operator_raw"] = gdf.apply(operator_text, axis=1)

    # Drop the not-BMA landowners outright.
    not_bma = gdf["operator_raw"].apply(lambda t: _matches(t, NOT_BMA_PATTERNS))
    if not_bma.any():
        print("   - dropped {} facility(ies) on non-BMA public land "
              "(Crown Property / SRT / Treasury / military / university).".format(
                  int(not_bma.sum())))
    gdf = gdf[~not_bma].copy()

    is_bma = gdf["operator_raw"].apply(lambda t: _matches(t, BMA_OPERATOR_PATTERNS))
    gdf["ownership_confidence"] = [
        "high" if flag else CATEGORY_DEFAULT_CONF[cat]
        for flag, cat in zip(is_bma, gdf["category"])
    ]
    gdf["source"] = ["osm_operator_tag" if flag else "osm_category_default"
                     for flag in is_bma]
    gdf["name"] = gdf["name"].fillna("")
    return gdf[["name", "category", "operator_raw", "ownership_confidence",
                "source", "geometry"]].reset_index(drop=True)


def merge_school_registry(osm, schools):
    """Give registry schools an extent where OSM has mapped the school grounds.

    A registry point inside an OSM school polygon promotes that polygon to `high`
    (authoritative ownership) while keeping OSM's footprint (real extent). Points
    with no polygon are kept as points -- still `high`, but their site area will
    only ever be the one parcel underneath.
    """
    osm_schools = osm[(osm["category"] == "school")
                      & osm.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    if osm_schools.empty:
        return osm, schools, 0

    sch_proj = schools.to_crs(epsg=UTM47N)
    poly_proj = osm_schools.to_crs(epsg=UTM47N)
    hit = gpd.sjoin(sch_proj[["name", "geometry"]], poly_proj[["geometry"]],
                    how="inner", predicate="within")
    matched_poly_idx = set(hit["index_right"])
    matched_school_idx = set(hit.index)

    # Promote the matched OSM polygons.
    osm.loc[osm.index.isin(matched_poly_idx), "ownership_confidence"] = "high"
    osm.loc[osm.index.isin(matched_poly_idx), "source"] = "bma_open_data+osm_footprint"
    osm.loc[osm.index.isin(matched_poly_idx), "operator_raw"] = \
        "BMA school registry (data.bangkok.go.th)"

    leftover = schools[~schools.index.isin(matched_school_idx)].copy()
    return osm, leftover, len(matched_poly_idx)


def fetch_temple_land():
    """Buddhist temple compounds -- an EXCLUSION layer, not a facility layer.

    Most BMA schools are วัด schools (โรงเรียนวัด...) built in a temple's grounds.
    BMA runs the school; the temple owns the ground (ธรณีสงฆ์). Seeding ownership
    off the school therefore claims the whole wat compound as city land, which is
    simply false -- in Bang Rak all 5 "BMA school" parcels turned out to be 54-93%
    covered by a temple. build_bma_land_layer.py uses this layer to catch that.
    """
    gdf = ox.features_from_place("Bangkok, Thailand",
                                 tags={"amenity": "place_of_worship"})
    gdf = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    if "name" not in gdf.columns:
        gdf["name"] = None
    gdf["name"] = gdf["name"].fillna("")
    return gdf[["name", "geometry"]].reset_index(drop=True)


def fetch_facilities():
    out_path = "data/gis/bangkok_bma_facilities.geojson"
    temple_path = "data/gis/bangkok_temple_land.geojson"

    print("1. Fetching BMA school registry (data.bangkok.go.th)...")
    schools = fetch_bma_schools()
    print("   - {} authoritative BMA schools.".format(len(schools)))

    print("2. Fetching candidate facilities from OSM (city-wide)...")
    osm = fetch_osm_facilities()
    print("   - {} facilities after category filter.".format(len(osm)))

    print("3. Matching registry schools to OSM footprints...")
    osm, leftover_schools, n_matched = merge_school_registry(osm, schools)
    print("   - {} OSM school polygons promoted to high (authoritative + footprint).".format(n_matched))
    print("   - {} registry schools kept as points (no OSM footprint).".format(len(leftover_schools)))

    gdf = pd.concat([osm, leftover_schools], ignore_index=True)
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=4326)
    gdf["facility_id"] = gdf.index

    print("4. Fetching temple compounds (exclusion layer)...")
    temples = fetch_temple_land()
    temples.to_file(temple_path, driver="GeoJSON")
    print("   - {} temple polygons -> {}".format(len(temples), temple_path))

    print("5. Writing output...")
    cols = ["facility_id", "name", "category", "operator_raw",
            "ownership_confidence", "source"]
    gdf[cols + ["geometry"]].to_file(out_path, driver="GeoJSON")
    print("   - {}".format(out_path))

    print("\nConfidence distribution:")
    print(gdf["ownership_confidence"].value_counts().to_string())
    print("\nBy category / confidence:")
    print(pd.crosstab(gdf["category"], gdf["ownership_confidence"]).to_string())
    print("\nGeometry types:")
    print(gdf.geom_type.value_counts().to_string())
    print("\nDone. `high` = trust as BMA land. `medium`/`low` = MUST be verified "
          "before use;\nBangkok has extensive Crown Property / SRT / Treasury land "
          "that looks public but is not the city's.")


if __name__ == "__main__":
    fetch_facilities()
