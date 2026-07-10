"""
Phase 1 of docs/uhi_data_sourcing_plan.md: real per-district Land Surface
Temperature (LST) for Bangkok, computed on Google Earth Engine from a
multi-year, dry-season, cloud-masked Landsat 8/9 Collection 2 Level 2
composite, then reduced to zonal statistics over the real district
boundaries in data/gis/bangkok_districts.geojson.

Requires: `pip install earthengine-api`, and a Cloud project registered
for Earth Engine (see docs/uhi_data_sourcing_plan.md Phase 1).
"""
import csv
import json
import os

import ee

EE_PROJECT = "weather-data-morphing"

# Dry season (hottest, most UHI-pronounced period in Bangkok) across
# several years, to smooth out single-scene cloud/noise artifacts.
DRY_SEASON_YEARS = [2019, 2020, 2021, 2022, 2023, 2024]
DRY_SEASON_MONTHS = (3, 5)  # March through May, inclusive

LST_SCALE_M = 100  # native thermal band resolution for Landsat C2 L2


def mask_clouds(image):
    qa = image.select("QA_PIXEL")
    cloud_bit = 1 << 3
    cloud_shadow_bit = 1 << 4
    cirrus_bit = 1 << 2
    mask = (
        qa.bitwiseAnd(cloud_bit).eq(0)
        .And(qa.bitwiseAnd(cloud_shadow_bit).eq(0))
        .And(qa.bitwiseAnd(cirrus_bit).eq(0))
    )
    return image.updateMask(mask)


def to_celsius(image):
    # Landsat Collection 2 Level 2 ST_B10 scale factors (USGS docs):
    # Kelvin = DN * 0.00341802 + 149.0
    lst_c = image.select("ST_B10").multiply(0.00341802).add(149.0).subtract(273.15)
    return lst_c.rename("LST_C").copyProperties(image, ["system:time_start"])


def build_dry_season_composite(region):
    collections = []
    for year in DRY_SEASON_YEARS:
        start = "{}-{:02d}-01".format(year, DRY_SEASON_MONTHS[0])
        end = "{}-{:02d}-01".format(year, DRY_SEASON_MONTHS[1] + 1)
        for collection_id in ("LANDSAT/LC08/C02/T1_L2", "LANDSAT/LC09/C02/T1_L2"):
            collections.append(
                ee.ImageCollection(collection_id)
                .filterBounds(region)
                .filterDate(start, end)
            )

    merged = collections[0]
    for c in collections[1:]:
        merged = merged.merge(c)

    masked = merged.map(mask_clouds).map(to_celsius)
    return masked.median()


def load_district_features(geojson_path):
    with open(geojson_path, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    features = []
    for feat in geojson["features"]:
        name = feat["properties"].get("District", "Unknown")
        geom = ee.Geometry(feat["geometry"])
        features.append(ee.Feature(geom, {"District": name}))
    return ee.FeatureCollection(features)


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    geojson_path = os.path.join(base_dir, "gis", "bangkok_districts.geojson")
    out_path = os.path.join(base_dir, "gis", "bangkok_lst_data.csv")

    print("Initializing Earth Engine (project={})...".format(EE_PROJECT))
    ee.Initialize(project=EE_PROJECT)

    print("Loading district boundaries from {}...".format(geojson_path))
    districts = load_district_features(geojson_path)
    region = districts.geometry()

    print(
        "Building dry-season ({}-{} months, years {}-{}) cloud-masked LST composite...".format(
            DRY_SEASON_MONTHS[0], DRY_SEASON_MONTHS[1], DRY_SEASON_YEARS[0], DRY_SEASON_YEARS[-1]
        )
    )
    lst_composite = build_dry_season_composite(region)

    print("Running zonal statistics per district (scale={}m)...".format(LST_SCALE_M))
    reducer = ee.Reducer.mean().combine(ee.Reducer.max(), sharedInputs=True).combine(
        ee.Reducer.count(), sharedInputs=True
    )
    stats = lst_composite.reduceRegions(
        collection=districts, reducer=reducer, scale=LST_SCALE_M
    )

    results = stats.getInfo()["features"]

    rows = []
    missing = []
    for feat in results:
        props = feat["properties"]
        name = props.get("District", "Unknown")
        mean_c = props.get("mean")
        max_c = props.get("max")
        pixel_count = props.get("count")
        if mean_c is None or pixel_count in (None, 0):
            missing.append(name)
            continue
        rows.append(
            {
                "District": name,
                "LST_Mean_C": round(mean_c, 2),
                "LST_Max_C": round(max_c, 2),
                "Pixel_Count": int(pixel_count),
            }
        )

    rows.sort(key=lambda r: r["LST_Mean_C"], reverse=True)

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["District", "LST_Mean_C", "LST_Max_C", "Pixel_Count"])
        writer.writeheader()
        writer.writerows(rows)

    print("Wrote {} district(s) to {}".format(len(rows), out_path))
    if missing:
        print("WARNING: {} district(s) had no valid pixels (too small/cloudy): {}".format(
            len(missing), ", ".join(missing)
        ))


if __name__ == "__main__":
    main()
