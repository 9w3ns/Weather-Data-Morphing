"""Add green-space ACCESS attributes to each BMA candidate site.

Green access is a siting metric (and a UHI-relevant amenity): how close is a
candidate civic-centre site to usable green, per UDDC's 15-minute-walk logic.
Uses PARK-class green only (green_class == "park") -- recreational, people-usable,
not forest/scrub cover.

Adds to data/gis/bangkok_bma_land_scored.csv AND bangkok_bma_land.geojson:
    dist_to_nearest_park_m     : metres from site centroid to nearest park polygon
    park_area_within_800m_sqm  : park area inside an 800 m walk buffer (15-min)
    green_15min                : "yes" if a park is within 800 m, else "no"

Idempotent; re-run after build_bma_land_layer.py. Run from the repo root.
"""
import warnings

import geopandas as gpd
import pandas as pd

warnings.filterwarnings("ignore")

UTM47N = 32647
WALK_15MIN_M = 800.0   # UDDC 15-minute walk ~ 800 m

SITES = "data/gis/bangkok_bma_land.geojson"
GREEN = "data/gis/bangkok_green_space.geojson"
SCORED = "data/gis/bangkok_bma_land_scored.csv"


def main():
    sites = gpd.read_file(SITES).to_crs(epsg=UTM47N)
    green = gpd.read_file(GREEN).to_crs(epsg=UTM47N)
    parks = green[green["green_class"] == "park"].copy()
    if parks.empty:
        raise SystemExit("No park-class green found. Run fetch_green_space_osm.py first.")

    cent = gpd.GeoDataFrame(sites[["site_id"]].copy(),
                            geometry=sites.geometry.centroid, crs=UTM47N)

    # 1. Distance to nearest park.
    near = gpd.sjoin_nearest(cent, parks[["green_id", "geometry"]],
                             how="left", distance_col="dist_to_nearest_park_m")
    near = near.drop_duplicates("site_id").set_index("site_id")
    sites["dist_to_nearest_park_m"] = sites["site_id"].map(
        near["dist_to_nearest_park_m"]).round(1)

    # 2. Park area within an 800 m walk buffer.
    buf = cent.copy()
    buf["geometry"] = cent.geometry.buffer(WALK_15MIN_M)
    inter = gpd.overlay(buf[["site_id", "geometry"]],
                        parks[["green_id", "geometry"]], how="intersection")
    if inter.empty:
        area_by_site = pd.Series(dtype=float)
    else:
        inter["a"] = inter.geometry.area
        area_by_site = inter.groupby("site_id")["a"].sum()
    sites["park_area_within_800m_sqm"] = sites["site_id"].map(area_by_site).fillna(0.0).round(1)

    sites["green_15min"] = (sites["dist_to_nearest_park_m"] <= WALK_15MIN_M).map(
        {True: "yes", False: "no"})

    new_cols = ["dist_to_nearest_park_m", "park_area_within_800m_sqm", "green_15min"]

    # Write geojson back.
    sites.to_crs(epsg=4326).to_file(SITES, driver="GeoJSON")

    # Merge into the scored CSV.
    scored = pd.read_csv(SCORED)
    add = sites[["site_id"] + new_cols]
    scored = scored.drop(columns=[c for c in new_cols if c in scored.columns], errors="ignore")
    scored = scored.merge(add, on="site_id", how="left")
    scored.to_csv(SCORED, index=False, encoding="utf-8-sig")

    n_yes = int((sites["green_15min"] == "yes").sum())
    print("Added green-access columns to {} sites.".format(len(sites)))
    print("  within 15-min walk of a park (<= {:.0f} m): {} of {} ({:.0f}%)".format(
        WALK_15MIN_M, n_yes, len(sites), 100.0 * n_yes / len(sites)))
    print("  median distance to nearest park: {:.0f} m".format(
        sites["dist_to_nearest_park_m"].median()))
    print("Wrote:\n  {}\n  {}".format(SITES, SCORED))

    # District offices, sorted by green access (the siting-relevant subset).
    off = sites[sites["category"] == "district_office"].copy()
    off = off.sort_values("dist_to_nearest_park_m")
    off["d"] = off["district"].str.replace(" District", "", regex=False)
    print("\nDistrict offices by distance to nearest park:")
    print(off[["d", "dist_to_nearest_park_m", "park_area_within_800m_sqm", "green_15min"]]
          .head(12).to_string(index=False))


if __name__ == "__main__":
    main()
