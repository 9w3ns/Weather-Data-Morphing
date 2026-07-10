"""
Phase 2 of docs/uhi_data_sourcing_plan.md: real per-district Local Climate
Zone (LCZ) classification for Bangkok, using the global LCZ map
(Demuzere et al. 2022, RUB/RUBCLIM/LCZ/global_lcz_map/latest on Earth
Engine) instead of the hardcoded LCZ-1/3/6 tier assignment in the mock
CSV. No need to run the WUDAPT LCZ Generator training pipeline ourselves
-- Bangkok is already covered by the published global map.

Requires: `pip install earthengine-api` and Earth Engine access (see
docs/uhi_data_sourcing_plan.md Phase 1).
"""
import csv
import json
import os

import ee

EE_PROJECT = "weather-data-morphing"
LCZ_SCALE_M = 100

LCZ_LABELS = {
    1: "LCZ 1 (Compact high-rise)",
    2: "LCZ 2 (Compact midrise)",
    3: "LCZ 3 (Compact low-rise)",
    4: "LCZ 4 (Open high-rise)",
    5: "LCZ 5 (Open midrise)",
    6: "LCZ 6 (Open low-rise)",
    7: "LCZ 7 (Lightweight low-rise)",
    8: "LCZ 8 (Large low-rise)",
    9: "LCZ 9 (Sparsely built)",
    10: "LCZ 10 (Heavy industry)",
    11: "LCZ A (Dense trees)",
    12: "LCZ B (Scattered trees)",
    13: "LCZ C (Bush, scrub)",
    14: "LCZ D (Low plants)",
    15: "LCZ E (Bare rock or paved)",
    16: "LCZ F (Bare soil or sand)",
    17: "LCZ G (Water)",
}


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
    out_path = os.path.join(base_dir, "gis", "bangkok_lcz_data.csv")

    print("Initializing Earth Engine (project={})...".format(EE_PROJECT))
    ee.Initialize(project=EE_PROJECT)

    print("Loading district boundaries from {}...".format(geojson_path))
    districts = load_district_features(geojson_path)
    bounds = districts.geometry().bounds()

    print("Loading global LCZ map (Demuzere et al. 2022)...")
    lcz_col = ee.ImageCollection("RUB/RUBCLIM/LCZ/global_lcz_map/latest")
    lcz_class = lcz_col.select("LCZ_Filter").mosaic().clip(bounds)
    lcz_prob = lcz_col.select("LCZ_Probability").mosaic().clip(bounds)

    print("Running zonal majority-class stats per district (scale={}m)...".format(LCZ_SCALE_M))
    class_stats = lcz_class.reduceRegions(
        collection=districts, reducer=ee.Reducer.mode(), scale=LCZ_SCALE_M
    )
    prob_stats = lcz_prob.reduceRegions(
        collection=districts, reducer=ee.Reducer.mean(), scale=LCZ_SCALE_M
    )

    class_results = {f["properties"]["District"]: f["properties"].get("mode") for f in class_stats.getInfo()["features"]}
    prob_results = {f["properties"]["District"]: f["properties"].get("mean") for f in prob_stats.getInfo()["features"]}

    rows = []
    missing = []
    for name, lcz_code in class_results.items():
        if lcz_code is None:
            missing.append(name)
            continue
        lcz_code = int(lcz_code)
        rows.append(
            {
                "District": name,
                "LCZ_Code": lcz_code,
                "Dominant_LCZ": LCZ_LABELS.get(lcz_code, "Unknown ({})".format(lcz_code)),
                "LCZ_Confidence_Pct": round(prob_results.get(name, 0.0), 1),
            }
        )

    rows.sort(key=lambda r: r["District"])

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["District", "LCZ_Code", "Dominant_LCZ", "LCZ_Confidence_Pct"])
        writer.writeheader()
        writer.writerows(rows)

    print("Wrote {} district(s) to {}".format(len(rows), out_path))
    if missing:
        print("WARNING: {} district(s) had no LCZ classification: {}".format(len(missing), ", ".join(missing)))


if __name__ == "__main__":
    main()
