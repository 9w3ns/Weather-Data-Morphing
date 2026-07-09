#! python 3
"""
GHPython Script: Match District UHI Data to Geometry
Author: Antigravity

Inputs:
    Curves         : List of Curve, district boundary curves (from gh_geojson_to_curves.py).
    District_Names : List of String, district name aligned 1:1 with Curves.
    CSV_Path       : String, absolute path to 'bangkok_uhi_data.csv'.
Outputs:
    Matched_Curves : The curves that successfully matched a CSV row.
    UHI_Risk       : List of UHI Risk categories (Low, Medium, Severe).
    Death_Risk     : List of Death Risk values (Float).
    LCZ_Category   : List of dominant LCZ classes.
    Report         : String summary / error log.
"""
import csv
import traceback

# Initialize outputs
Matched_Curves = []
UHI_Risk = []
Death_Risk = []
LCZ_Category = []
Report = "Awaiting inputs..."


def normalize_name(name):
    n = str(name).strip().lower()
    for token in ("khet ", " district"):
        n = n.replace(token, "")
    return n.strip()


def read_csv_data(filepath):
    data_dict = {}
    with open(filepath, mode='r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            district = normalize_name(row['District'])
            data_dict[district] = {
                'UHI_Risk': row['UHI_Risk'],
                'Death_Risk': float(row['Death_Risk_Index']),
                'Dominant_LCZ': row['Dominant_LCZ']
            }
    return data_dict


if not (CSV_Path and Curves and District_Names):
    Report = "Provide CSV_Path, Curves, and District_Names."
else:
    try:
        district_data = read_csv_data(CSV_Path)
        unmatched = []

        for i, name in enumerate(District_Names):
            clean_name = normalize_name(name)

            # Exact match first; fall back to a loose substring match for
            # slight spelling differences (e.g. Sathon vs Sathorn).
            match = district_data.get(clean_name)
            if match is None:
                for csv_name, data in district_data.items():
                    if csv_name in clean_name or clean_name in csv_name:
                        match = data
                        break

            if match is not None:
                Matched_Curves.append(Curves[i])
                UHI_Risk.append(match['UHI_Risk'])
                Death_Risk.append(match['Death_Risk'])
                LCZ_Category.append(match['Dominant_LCZ'])
            else:
                unmatched.append(str(name))

        Report = "Matched {} out of {} districts.".format(len(Matched_Curves), len(District_Names))
        if unmatched:
            Report += "\nNo match found for: " + ", ".join(unmatched)

    except Exception:
        Report = "ERROR:\n" + traceback.format_exc()
