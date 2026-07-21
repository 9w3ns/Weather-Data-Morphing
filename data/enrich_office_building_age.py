"""Join district_office_building_age.csv onto bangkok_bma_land.geojson.

Adds three properties to each site feature so gh_bma_land.py can colour the
district offices by building lifecycle era on the Grasshopper canvas:
    building_year_ce   : int as string ("" if unknown / not an office)
    building_year_type : construction / opening / relocation / leased / unknown
    building_era       : coarse lifecycle bucket used for colouring --
                         "Pre-1970 (historic)", "1970-1999", "2000-present",
                         "Leased (not BMA bldg)", "Unknown", or "" (non-office)

Idempotent: re-run after build_bma_land_layer.py (which rewrites the geojson).
Run from the repo root.
"""
import csv
import json
import os

GEOJSON = "data/gis/bangkok_bma_land.geojson"
AGE_CSV = "data/gis/district_office_building_age.csv"

# Era order (for a matching Colour Swatch list in Grasshopper). Keep in sync with
# the note in gh_bma_land.py.
ERA_ORDER = ["Pre-1970 (historic)", "1970-1999", "2000-present",
             "Leased (not BMA bldg)", "Unknown"]


def era_for(year_ce, year_type):
    t = (year_type or "").strip().lower()
    if t.startswith("leased"):
        return "Leased (not BMA bldg)"
    if not year_ce or t in ("relocation", "unknown", ""):
        # relocation is a move-in year, not a build year -> not a true age
        return "Unknown"
    y = int(year_ce)
    if y < 1970:
        return "Pre-1970 (historic)"
    if y < 2000:
        return "1970-1999"
    return "2000-present"


def load_age():
    ages = {}
    with open(AGE_CSV, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                sid = int(float(row["site_id"]))
            except (KeyError, ValueError):
                continue
            yr = (row.get("building_year_CE") or "").strip()
            yr = str(int(float(yr))) if yr else ""
            ages[sid] = (yr, (row.get("year_type") or "").strip())
    return ages


def main():
    if not os.path.exists(AGE_CSV):
        raise SystemExit("Missing {} -- run the building-age research first.".format(AGE_CSV))
    ages = load_age()
    with open(GEOJSON, "r", encoding="utf-8") as f:
        gj = json.load(f)

    matched = 0
    era_counts = {}
    for feat in gj.get("features", []):
        props = feat.setdefault("properties", {})
        try:
            sid = int(float(props.get("site_id")))
        except (TypeError, ValueError):
            sid = None
        if sid is not None and sid in ages:
            yr, ytype = ages[sid]
            era = era_for(yr, ytype)
            matched += 1
        else:
            yr, ytype, era = "", "", ""   # non-office / not researched
        props["building_year_ce"] = yr
        props["building_year_type"] = ytype
        props["building_era"] = era
        if era:
            era_counts[era] = era_counts.get(era, 0) + 1

    with open(GEOJSON, "w", encoding="utf-8") as f:
        json.dump(gj, f, ensure_ascii=False)

    print("Enriched {} of {} features with building-age fields.".format(
        matched, len(gj.get("features", []))))
    print("Era distribution (offices):")
    for era in ERA_ORDER:
        if era in era_counts:
            print("  {:<24} {}".format(era, era_counts[era]))
    print("Wrote {}".format(GEOJSON))


if __name__ == "__main__":
    main()
