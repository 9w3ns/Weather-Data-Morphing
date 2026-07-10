"""
Phase 4 of docs/uhi_data_sourcing_plan.md: merge the real per-district
datasets into data/gis/bangkok_uhi_data.csv, replacing the mock 3-tier
placeholder that used to live there.

Sources:
  - bangkok_worldbank_uhii.csv: Table A1.1 from the World Bank report
    "Modeling Spatio-Temporal Characteristics of Urban Heat in Bangkok"
    (research/*.pdf) -- real WRF-modeled nighttime Urban Heat Island
    Intensity (UHII, air temperature vs rural reference) for the cool/dry
    season (Dec 2019), the report's own headline "most pronounced UHI"
    result, plus each district's real % share of BMA population.
  - bangkok_lst_data.csv: real Landsat-derived daytime surface temperature
    (data/fetch_uhi_lst.py).
  - bangkok_lcz_data.csv: real Local Climate Zone classification
    (data/fetch_uhi_lcz.py).

UHI_Tier (Severe/Medium/Low) is derived from UHII_Night_DecC tertiles --
the real WRF air-temperature metric, not LST -- since that's the
actual "urban heat island" quantity as classically defined and the one
relevant to health risk (the report ties nighttime air temperature, not
daytime surface temperature, to heat-mortality risk). LST/LCZ are kept as
separate labeled columns: LST is real, but reflects daytime surface
temperature, which this same report documents as an "urban cool island"
period for Bangkok's compact high-rise core -- the two datasets disagree
on which districts are "hottest" because they measure genuinely different
physical phenomena, not because either is wrong.

Death_Risk_Index (mortality) is intentionally NOT included -- no district
level mortality data was found; Population_Pct_BMA is the real, sourced
substitute for now (see docs/uhi_data_sourcing_plan.md Phase 3).
"""
import csv
import os

# The World Bank report and our OSM-derived district names sometimes use
# different transliterations for the same district.
NAME_ALIASES = {
    "watthana": "vadhana",
    "phra khanon": "phra khanong",
}


def normalize(name):
    n = name.strip().lower().replace(" district", "")
    return NAME_ALIASES.get(n, n)


def read_csv_by_district(path):
    with open(path, "r", encoding="utf-8") as f:
        return {normalize(row["District"]): row for row in csv.DictReader(f)}


def tertile_tier(value, sorted_values):
    n = len(sorted_values)
    lower_cut = sorted_values[n // 3]
    upper_cut = sorted_values[(2 * n) // 3]
    if value >= upper_cut:
        return "Severe"
    if value >= lower_cut:
        return "Medium"
    return "Low"


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    gis_dir = os.path.join(base_dir, "gis")
    uhii_path = os.path.join(gis_dir, "bangkok_worldbank_uhii.csv")
    lst_path = os.path.join(gis_dir, "bangkok_lst_data.csv")
    lcz_path = os.path.join(gis_dir, "bangkok_lcz_data.csv")
    out_path = os.path.join(gis_dir, "bangkok_uhi_data.csv")

    uhii_data = read_csv_by_district(uhii_path)
    lst_data = read_csv_by_district(lst_path)
    lcz_data = read_csv_by_district(lcz_path)

    missing = [name for name in lst_data if name not in uhii_data or name not in lcz_data]
    if missing:
        raise SystemExit("Districts missing from one of the sources: {}".format(missing))

    uhii_values = sorted(float(row["UHII_Night_DecC"]) for row in uhii_data.values())

    rows = []
    for name, lst_row in lst_data.items():
        uhii_row = uhii_data[name]
        lcz_row = lcz_data[name]
        uhii_night = float(uhii_row["UHII_Night_DecC"])
        # Use the original (non-aliased) District spelling from the LST/geojson
        # source, since that's what the Grasshopper matcher's District_Names
        # will actually contain.
        rows.append(
            {
                "District": lst_row["District"],
                "UHII_Night_DecC": uhii_night,
                "Population_Pct_BMA": float(uhii_row["Population_Pct_BMA"]),
                "UHI_Tier": tertile_tier(uhii_night, uhii_values),
                "LST_Mean_C": float(lst_row["LST_Mean_C"]),
                "LST_Max_C": float(lst_row["LST_Max_C"]),
                "Dominant_LCZ": lcz_row["Dominant_LCZ"],
                "LCZ_Confidence_Pct": float(lcz_row["LCZ_Confidence_Pct"]),
            }
        )

    rows.sort(key=lambda r: r["UHII_Night_DecC"], reverse=True)

    fieldnames = [
        "District", "UHII_Night_DecC", "Population_Pct_BMA", "UHI_Tier",
        "LST_Mean_C", "LST_Max_C", "Dominant_LCZ", "LCZ_Confidence_Pct",
    ]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    tier_counts = {}
    for row in rows:
        tier_counts[row["UHI_Tier"]] = tier_counts.get(row["UHI_Tier"], 0) + 1

    print("Wrote {} district(s) to {}".format(len(rows), out_path))
    print("UHI_Tier distribution (from real WRF nighttime UHII):", tier_counts)


if __name__ == "__main__":
    main()
