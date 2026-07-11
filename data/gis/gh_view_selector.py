#! python 3
# GHPython Script: View_Name -> per-district R/G/B color strings
#
# Inputs:
#     View_Name      : String, from a native Value List component. One of:
#                       "Tier", "UHII_CoolDry_Night_C", "UHII_CoolDry_Evening_C",
#                       "UHII_HotDry_Night_C", "UHII_HotDry_Evening_C",
#                       "UHII_Wet_Night_C", "UHII_Wet_Evening_C"
#                       (set these as the Value List items' Values; use
#                       friendly Names like "Cool - Night" for display).
#     District_Names : List of String, same order as your (reordered) Curves.
#     CSV_Path       : String, path to bangkok_uhi_data.csv.
# Outputs:
#     R_Strings, G_Strings, B_Strings : FLAT lists of String ("0"-"255"),
#                       one per district, District_Names order.
#     Legend_Text    : String describing the current view's color scale,
#                       for a Panel next to the map.
#     Report         : String summary / error log.
#
# Mirrors the color logic in the reference web artifact:
#   https://claude.ai/code/artifact/725bfedb-128c-4678-ac3e-feaba5a683bf
# "Tier" uses the fixed status palette (Severe/Medium/Low). Any UHII column
# uses a diverging blue<->red scale centered on 0 (negative = urban cool
# island, a real effect the report documents), with a SHARED domain across
# all 6 UHII columns so switching views stays visually comparable.
#
# Only flat String lists are output -- Color/Curve objects and trees don't
# reliably survive this Script component's output boundary. Convert on the
# canvas with native components:
#   R_Strings/G_Strings/B_Strings -> Text to Number (x3) -> Colour (RGB in,
#     Colour out -- search "Colour" or "ARGB" in the component search)
#   -> Custom Preview's Colour input, paired with your (reordered) Curves.
import csv
import traceback

TIER_COLORS = {
    "Severe": (208, 59, 59),    # --critical
    "Medium": (250, 178, 25),   # --warning
    "Low": (12, 163, 12),       # --good
}
POS_POLE = (208, 59, 59)   # red
NEG_POLE = (42, 120, 214)  # blue
NEUTRAL = (240, 239, 236)  # light neutral midpoint

UHII_COLUMNS = [
    "UHII_CoolDry_Night_C", "UHII_CoolDry_Evening_C",
    "UHII_HotDry_Night_C", "UHII_HotDry_Evening_C",
    "UHII_Wet_Night_C", "UHII_Wet_Evening_C",
]

VIEW_LABELS = {
    "Tier": "UHI Tier (Severe/Medium/Low)",
    "UHII_CoolDry_Night_C": "Cool/Dry season, night UHII",
    "UHII_CoolDry_Evening_C": "Cool/Dry season, evening UHII",
    "UHII_HotDry_Night_C": "Hot/Dry season, night UHII",
    "UHII_HotDry_Evening_C": "Hot/Dry season, evening UHII",
    "UHII_Wet_Night_C": "Wet monsoon season, night UHII",
    "UHII_Wet_Evening_C": "Wet monsoon season, evening UHII",
}

# Initialize outputs
R_Strings = []
G_Strings = []
B_Strings = []
Legend_Text = ""
Report = "Awaiting inputs..."


def normalize_name(name):
    n = str(name).strip().lower()
    for token in ("khet ", " district"):
        n = n.replace(token, "")
    return n.strip()


def lerp_rgb(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def diverging_color(value, pos_max, neg_min):
    if value >= 0:
        t = min(1.0, value / pos_max) if pos_max > 0 else 0.0
        return lerp_rgb(NEUTRAL, POS_POLE, t)
    else:
        t = min(1.0, value / neg_min) if neg_min < 0 else 0.0
        return lerp_rgb(NEUTRAL, NEG_POLE, t)


def read_csv_data(filepath):
    data_dict = {}
    with open(filepath, mode='r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            data_dict[normalize_name(row['District'])] = row
    return data_dict


if not (CSV_Path and District_Names and View_Name):
    Report = "Provide CSV_Path, District_Names, and View_Name."
else:
    try:
        clean_csv_path = str(CSV_Path).strip().strip('"').strip("'")
        view = str(View_Name).strip()
        district_data = read_csv_data(clean_csv_path)

        pos_max = neg_min = 0.0
        if view != "Tier":
            all_vals = [
                float(row[col])
                for row in district_data.values()
                for col in UHII_COLUMNS
            ]
            pos_max = max(all_vals + [0.0])
            neg_min = min(all_vals + [0.0])

        unmatched = []
        for name in District_Names:
            clean_name = normalize_name(name)
            match = district_data.get(clean_name)
            if match is None:
                for csv_name, data in district_data.items():
                    if csv_name in clean_name or clean_name in csv_name:
                        match = data
                        break

            if match is None:
                unmatched.append(str(name))
                r, g, b = 200, 200, 200
            elif view == "Tier":
                r, g, b = TIER_COLORS.get(match["UHI_Tier"], (200, 200, 200))
            else:
                r, g, b = diverging_color(float(match[view]), pos_max, neg_min)

            R_Strings.append(str(int(round(r))))
            G_Strings.append(str(int(round(g))))
            B_Strings.append(str(int(round(b))))

        if view == "Tier":
            Legend_Text = "{}\nRed=Severe (18)  Amber=Medium (16)  Green=Low (16)".format(
                VIEW_LABELS.get(view, view))
        else:
            Legend_Text = "{}\nBlue={:.1f}C (cool island)  Neutral=0C  Red=+{:.1f}C".format(
                VIEW_LABELS.get(view, view), neg_min, pos_max)

        Report = "Colored {} districts for view '{}'.".format(len(District_Names), view)
        if unmatched:
            Report += "\nNo match found for: " + ", ".join(unmatched)

    except Exception:
        Report = "ERROR:\n" + traceback.format_exc()
