"""
Diagnostic: is LCZ 7 (Lightweight low-rise) genuinely absent from the Demuzere
global LCZ map over Bangkok, or is it being erased by the LCZ_Filter band's
morphological smoothing?

Counts code-7 pixels over the Bangkok district bounding box in BOTH bands:
  - LCZ        (raw Gaussian-filtered classes; keeps small isolated patches)
  - LCZ_Filter (majority-filtered; removes small isolated patches) <- what
                fetch_uhi_lcz.py / fetch_lcz_grid.py currently use

If code 7 shows up in LCZ but not LCZ_Filter, the fix is to switch bands
(or read both). If it's absent from LCZ too, it's a real source limitation and
LCZ 7 pockets must be hand-digitized at Tier 2 (or dropped from the matrix).

Requires: earthengine-api + EE access (same as the other fetch scripts).
"""
import json
import os

import ee

EE_PROJECT = "weather-data-morphing"
SCALE_M = 100  # native map resolution


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    geojson_path = os.path.join(base_dir, "gis", "bangkok_districts.geojson")

    ee.Initialize(project=EE_PROJECT)
    with open(geojson_path, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    feats = [ee.Feature(ee.Geometry(ft["geometry"])) for ft in geojson["features"]]
    bounds = ee.FeatureCollection(feats).geometry().bounds()

    col = ee.ImageCollection("RUB/RUBCLIM/LCZ/global_lcz_map/latest")

    for band in ("LCZ", "LCZ_Filter"):
        img = col.select(band).mosaic().clip(bounds)
        # histogram of class codes over the whole bbox
        hist = img.reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(),
            geometry=bounds,
            scale=SCALE_M,
            maxPixels=1e9,
        ).getInfo()
        counts = hist.get(band, {}) or {}
        counts = {int(float(k)): int(v) for k, v in counts.items()}
        total = sum(counts.values()) or 1
        lcz7 = counts.get(7, 0)
        print("\n=== Band: {} ===".format(band))
        print("  LCZ 7 pixels: {}  ({:.4f}% of {} classified px)".format(
            lcz7, 100.0 * lcz7 / total, total))
        print("  All classes present: {}".format(sorted(counts)))


if __name__ == "__main__":
    main()
