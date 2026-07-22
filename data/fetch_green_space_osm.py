"""Fetch Bangkok green space from OSM -> the green-coverage backbone layer.

Behind the UDDC "15-minute green city" story (uddc.net/scrollytellingminsgreen)
is ordinary green-space geometry, and OSM carries it city-wide. This pulls it so
the thesis can (a) draw a green layer, (b) measure green access per candidate
site, and (c) compute per-capita green by district -- see
docs/plan_green_space_layer.md.

TWO CLASSES, tagged so downstream can choose:
  - green_class == "park"       : recreational, people-usable (leisure=park/garden
                                  /nature_reserve/recreation_ground/common/dog_park).
                                  Use THIS for 15-min-walk access metrics.
  - green_class == "vegetation" : green COVER not necessarily accessible (landuse=
                                  grass/forest/meadow/village_green/greenfield,
                                  natural=wood/scrub/grassland). Include for
                                  per-capita green cover; it inflates "access".

Same conventions as fetch_bma_facilities.py: osmnx city-wide pull, keep polygons,
clip to districts by centroid, areas in UTM47N (EPSG:32647).

Run from the repo root.
Output: data/gis/bangkok_green_space.geojson (EPSG:4326)
    green_id, green_class, green_type, name, district, area_sqm
"""
import warnings

import geopandas as gpd
import osmnx as ox
import pandas as pd

warnings.filterwarnings("ignore")

UTM47N = 32647
DISTRICTS_PATH = "data/gis/bangkok_districts.geojson"
OUT_PATH = "data/gis/bangkok_green_space.geojson"

# Broad pull; classify_green() splits park vs vegetation. Tunable (plan decision 2).
OSM_GREEN_TAGS = {
    "leisure": ["park", "garden", "nature_reserve", "recreation_ground",
                "common", "dog_park"],
    "landuse": ["grass", "forest", "meadow", "village_green", "greenfield"],
    "natural": ["wood", "scrub", "grassland"],
}
PARK_LEISURE = {"park", "garden", "nature_reserve", "recreation_ground",
                "common", "dog_park"}
MIN_AREA_SQM = 100.0  # drop slivers / mistagged points-as-polygons


def normalize_name(name):
    n = str(name).strip().lower()
    for token in ("khet ", " district"):
        n = n.replace(token, "")
    return n.strip()


def classify_green(row):
    if str(row.get("leisure")) in PARK_LEISURE:
        return "park"
    return "vegetation"


def green_type(row):
    for key in ("leisure", "landuse", "natural"):
        v = row.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def main():
    print("1. Loading districts...")
    districts = gpd.read_file(DISTRICTS_PATH).to_crs(epsg=UTM47N)
    districts["norm"] = districts["District"].apply(normalize_name)

    print("2. Fetching green space from OSM (city-wide)...")
    ox.settings.timeout = 1800
    ox.settings.use_cache = True
    gdf = ox.features_from_place("Bangkok, Thailand", tags=OSM_GREEN_TAGS)
    gdf = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    for col in ("leisure", "landuse", "natural", "name"):
        if col not in gdf.columns:
            gdf[col] = None
    print("   - {} green polygons before filtering.".format(len(gdf)))

    gdf["green_class"] = gdf.apply(classify_green, axis=1)
    gdf["green_type"] = gdf.apply(green_type, axis=1)
    gdf["name"] = gdf["name"].fillna("")
    gdf = gdf.to_crs(epsg=UTM47N)
    gdf["area_sqm"] = gdf.geometry.area
    gdf = gdf[gdf["area_sqm"] >= MIN_AREA_SQM].copy()

    print("3. Clipping to districts (centroid-in)...")
    cent = gpd.GeoDataFrame(gdf[["green_type"]].copy(),
                            geometry=gdf.geometry.centroid, crs=UTM47N)
    hit = gpd.sjoin(cent, districts[["District", "geometry"]],
                    how="left", predicate="within")
    hit = hit[~hit.index.duplicated(keep="first")]
    gdf["district"] = hit["District"].values
    gdf = gdf[gdf["district"].notna()].copy()
    gdf = gdf.reset_index(drop=True)
    gdf["green_id"] = gdf.index

    print("4. Writing output...")
    out = gdf[["green_id", "green_class", "green_type", "name", "district",
               "area_sqm", "geometry"]].to_crs(epsg=4326)
    out.to_file(OUT_PATH, driver="GeoJSON")

    parks = gdf[gdf["green_class"] == "park"]
    veg = gdf[gdf["green_class"] == "vegetation"]
    print("   - {}".format(OUT_PATH))
    print("   - {} green features: {} park ({:.2f} sq km), {} vegetation ({:.2f} sq km).".format(
        len(gdf), len(parks), parks["area_sqm"].sum() / 1e6,
        len(veg), veg["area_sqm"].sum() / 1e6))
    print("\nTop green types by area:")
    print(gdf.groupby("green_type")["area_sqm"].agg(["count", "sum"])
          .sort_values("sum", ascending=False).head(10).to_string())
    print("\nDone. Backbone for per-site access + per-district per-capita green.")


if __name__ == "__main__":
    main()
