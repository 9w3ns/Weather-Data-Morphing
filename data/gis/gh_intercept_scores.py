#! python 3
# GHPython Script: Match district intercept scores to geometry (choropleth)
#
# Sibling of gh_data_matcher.py, for the commute-intercept layer. It does NOT
# touch geometry: it returns per-district numbers aligned 1:1 with the
# District_Names list you already built for your curves, so you can colour the
# existing district curves by intercept score.
#
# Inputs:
#   District_Names : List of String, one per district, in the SAME order as the
#                    Curves you built on the canvas (from gh_geojson_to_curves.py).
#   CSV_Path       : String, path to data/gis/bangkok_intercept_scores.csv
#                    (produced by fetch_land_use_osm.py).
# Outputs:
#   Intercept_Score        : List of String, Intercept_Score_Pct per district
#                            (% of DISTRICT area that is intercept fabric),
#                            "-1" if unmatched. Aligned to District_Names.
#   Intercept_Pct_Res      : List of String, Intercept_Pct_of_Residential per
#                            district (% of the district's RESIDENTIAL fabric
#                            that is intercept-adjacent), "-1" if unmatched.
#   Report                 : String summary / error log.
#
# Numbers are emitted as STRINGS on purpose: plain float lists have been
# observed to come back empty from this Script component (see gh_tier_masks.py).
# On the canvas: Intercept_Score -> Text to Number -> Remap Domain
# (source 0..max) -> Gradient -> Custom Preview on the district Curves.
# Pair by index: both this list and your Curves are in District_Names order and
# nothing is filtered, so indices line up 1:1 (unmatched districts get -1 --
# route those to a neutral grey so a data gap never reads as "score 0").
import csv
import traceback

# Initialize outputs
Intercept_Score = []
Intercept_Pct_Res = []
Report = "Awaiting inputs..."


def normalize_name(name):
    n = str(name).strip().lower()
    for token in ("khet ", " district"):
        n = n.replace(token, "")
    return n.strip()


def read_csv_data(filepath):
    data = {}
    with open(filepath, mode='r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            data[normalize_name(row['District'])] = {
                'score': float(row['Intercept_Score_Pct']),
                # Column added by the corrected scorer; tolerate its absence so
                # an older CSV still works.
                'pct_res': float(row.get('Intercept_Pct_of_Residential', -1.0)),
            }
    return data


if not (CSV_Path and District_Names):
    Report = "Provide CSV_Path and District_Names."
else:
    try:
        clean_csv_path = str(CSV_Path).strip().strip('"').strip("'")
        district_data = read_csv_data(clean_csv_path)
        unmatched = []

        for name in District_Names:
            clean_name = normalize_name(name)
            match = district_data.get(clean_name)
            if match is None:
                # Loose substring fallback for spelling variants (e.g. Sathon/Sathorn).
                for csv_name, data in district_data.items():
                    if csv_name in clean_name or clean_name in csv_name:
                        match = data
                        break

            if match is not None:
                Intercept_Score.append("{:.4f}".format(match['score']))
                Intercept_Pct_Res.append("{:.4f}".format(match['pct_res']))
            else:
                Intercept_Score.append("-1")
                Intercept_Pct_Res.append("-1")
                unmatched.append(str(name))

        matched = len(District_Names) - len(unmatched)
        Report = "Matched {} of {} districts.".format(matched, len(District_Names))
        if unmatched:
            Report += "\nNo match (emitted -1): " + ", ".join(unmatched)

    except Exception:
        Report = "ERROR:\n" + traceback.format_exc()
