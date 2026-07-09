#! python 3
# GHPython Script: Match District UHI Data to Geometry
#
# Inputs:
#     District_Names : List of String, one name per district (same order as
#                       the Curves you built natively on the canvas -- this
#                       script does not touch geometry at all).
#     CSV_Path       : String, absolute path to 'bangkok_uhi_data.csv'.
# Outputs:
#     UHI_Risk       : List of UHI Risk categories, aligned 1:1 with
#                       District_Names (use "No Data" placeholder if unmatched).
#     Death_Risk     : List of Death Risk values (Float, -1 if unmatched).
#     LCZ_Category   : List of dominant LCZ classes ("No Data" if unmatched).
#     Report         : String summary / error log.
#
# Deliberately does NOT take or return Curve geometry: lists of Curve
# objects don't reliably survive the round-trip out of this Script
# component in this environment. Pair this output with your existing
# native Curves list by index instead (both are in District_Names order,
# nothing is filtered out, so the indices always line up 1:1).
import csv
import traceback

# Initialize outputs
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


if not (CSV_Path and District_Names):
    Report = "Provide CSV_Path and District_Names."
else:
    try:
        # Strip stray quotes/whitespace -- GH panels/sliders with no type
        # hint on the input can pass the path wrapped in literal quote chars.
        clean_csv_path = str(CSV_Path).strip().strip('"').strip("'")
        district_data = read_csv_data(clean_csv_path)
        unmatched = []

        for name in District_Names:
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
                UHI_Risk.append(match['UHI_Risk'])
                Death_Risk.append(match['Death_Risk'])
                LCZ_Category.append(match['Dominant_LCZ'])
            else:
                UHI_Risk.append("No Data")
                Death_Risk.append(-1.0)
                LCZ_Category.append("No Data")
                unmatched.append(str(name))

        matched_count = len(District_Names) - len(unmatched)
        Report = "Matched {} out of {} districts.".format(matched_count, len(District_Names))
        if unmatched:
            Report += "\nNo match found for: " + ", ".join(unmatched)

    except Exception:
        Report = "ERROR:\n" + traceback.format_exc()
