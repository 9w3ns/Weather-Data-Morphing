"""
Transcribes all 6 per-district UHII tables (Annex 1, Tables A1.1-A1.6) from
the World Bank report "Modeling Spatio-Temporal Characteristics of Urban
Heat in Bangkok" (research/*.pdf) into a single wide CSV:
data/gis/bangkok_worldbank_uhii_full.csv

Columns: District, Population_Pct_BMA, then one UHII column per
season x time-of-day combination (6 total). Table A1.1 (cool/dry season,
night) is the report's own headline "most pronounced UHI" result and is
what data/merge_uhi_data.py already uses for UHI_Tier -- the other 5
tables add the fuller seasonal/diurnal picture for comparison.
"""
import csv
import os

# Each table: list of (District, UHII_C, Population_Pct_BMA) rows, exactly
# as printed in the report's Annex 1. Population is identical across all 6
# tables (same population, tabulated once per table in the source) -- kept
# per-table here only for transcription fidelity, deduplicated at merge time.

TABLE_A1_1_COOL_NIGHT = [
    ("Pom Prap Sattru Phai", 4.8, 0.72), ("Samphanthawong", 4.8, 0.37), ("Ratchathewi", 4.7, 1.21),
    ("Phra Nakhon", 4.7, 0.76), ("Bang Rak", 4.7, 0.80), ("Phaya Thai", 4.7, 1.19),
    ("Din Daeng", 4.7, 2.02), ("Khlong San", 4.6, 1.21), ("Pathum Wan", 4.6, 0.74),
    ("Thon Buri", 4.5, 1.81), ("Bangkok Yai", 4.5, 1.12), ("Sathon", 4.5, 1.32),
    ("Bang Sue", 4.5, 2.17), ("Dusit", 4.5, 1.43), ("Bang Phlat", 4.4, 1.59),
    ("Bang Kho Laem", 4.3, 1.44), ("Chatuchak", 4.3, 2.80), ("Watthana", 4.3, 1.47),
    ("Bangkok Noi", 4.2, 1.81), ("Huai Khwang", 4.2, 1.52), ("Wang Thonglang", 4.2, 1.90),
    ("Chom Thong", 4.2, 2.61), ("Rat Burana", 4.0, 1.39), ("Khlong Toei", 4.0, 1.65),
    ("Yan Nawa", 4.0, 1.35), ("Lak Si", 4.0, 1.83), ("Lat Phrao", 4.0, 2.08),
    ("Phasi Charoen", 3.9, 2.22), ("Bang Na", 3.8, 1.57), ("Phra Khanon", 3.8, 1.57),
    ("Suan Luang", 3.7, 2.23), ("Bang Kapi", 3.6, 2.57), ("Bueng Kum", 3.5, 2.51),
    ("Taling Chan", 3.3, 1.85), ("Don Mueang", 3.2, 3.03), ("Bang Bon", 3.1, 1.84),
    ("Bang Khae", 3.0, 3.50), ("Thung Khru", 3.0, 2.25), ("Bang Khen", 2.9, 3.37),
    ("Prawet", 2.8, 3.33), ("Khan Na Yao", 2.8, 1.74), ("Bang Khun Thian", 2.8, 3.36),
    ("Saphan Sung", 2.6, 1.75), ("Nong Khaem", 2.6, 2.83), ("Sai Mai", 2.3, 3.80),
    ("Thawi Watthana", 1.6, 1.44), ("Min Buri", 0.9, 2.57), ("Lat Krabang", 0.7, 3.25),
    ("Khlong Sam Wa", 0.6, 3.81), ("Nong Chok", -0.2, 3.30),
]

TABLE_A1_2_COOL_EVENING = [
    ("Ratchathewi", 4.1, 1.21), ("Phaya Thai", 4.0, 1.19), ("Din Daeng", 4.0, 2.02),
    ("Pom Prap Sattru Phai", 4.0, 0.72), ("Samphanthawong", 4.0, 0.37), ("Phra Nakhon", 3.9, 0.76),
    ("Bang Sue", 3.9, 2.17), ("Bang Rak", 3.9, 0.80), ("Bangkok Yai", 3.9, 1.12),
    ("Pathum Wan", 3.9, 0.74), ("Bang Phlat", 3.8, 1.59), ("Sathon", 3.8, 1.32),
    ("Dusit", 3.8, 1.43), ("Chatuchak", 3.8, 2.80), ("Khlong San", 3.7, 1.21),
    ("Wang Thonglang", 3.7, 1.90), ("Bangkok Noi", 3.7, 1.81), ("Watthana", 3.7, 1.47),
    ("Thon Buri", 3.7, 1.81), ("Huai Khwang", 3.6, 1.52), ("Lat Phrao", 3.6, 2.08),
    ("Phasi Charoen", 3.6, 2.22), ("Lak Si", 3.5, 1.83), ("Bang Kho Laem", 3.4, 1.44),
    ("Taling Chan", 3.4, 1.85), ("Suan Luang", 3.4, 2.23), ("Bang Kapi", 3.4, 2.57),
    ("Bueng Kum", 3.4, 2.51), ("Khlong Toei", 3.3, 1.65), ("Phra Khanon", 3.3, 1.57),
    ("Chom Thong", 3.2, 2.61), ("Bang Na", 3.2, 1.57), ("Yan Nawa", 3.2, 1.35),
    ("Bang Khae", 3.1, 3.50), ("Don Mueang", 2.9, 3.03), ("Rat Burana", 2.9, 1.39),
    ("Bang Khen", 2.9, 3.37), ("Khan Na Yao", 2.8, 1.74), ("Nong Khaem", 2.7, 2.83),
    ("Saphan Sung", 2.6, 1.75), ("Sai Mai", 2.6, 3.80), ("Bang Bon", 2.6, 1.84),
    ("Prawet", 2.6, 3.33), ("Thawi Watthana", 2.0, 1.44), ("Bang Khun Thian", 1.6, 3.36),
    ("Thung Khru", 1.5, 2.25), ("Min Buri", 1.2, 2.57), ("Khlong Sam Wa", 0.9, 3.81),
    ("Lat Krabang", 0.8, 3.25), ("Nong Chok", 0.2, 3.30),
]

TABLE_A1_3_HOT_NIGHT = [
    ("Lak Si", 2.0, 1.83), ("Bang Sue", 2.0, 2.17), ("Chatuchak", 2.0, 2.80),
    ("Phaya Thai", 1.9, 1.19), ("Ratchathewi", 1.9, 1.21), ("Din Daeng", 1.9, 2.02),
    ("Pom Prap Sattru Phai", 1.8, 0.72), ("Don Mueang", 1.8, 3.03), ("Lat Phrao", 1.8, 2.08),
    ("Bang Rak", 1.7, 0.80), ("Bang Phlat", 1.7, 1.59), ("Wang Thonglang", 1.7, 1.90),
    ("Samphanthawong", 1.7, 0.37), ("Dusit", 1.7, 1.43), ("Phra Nakhon", 1.7, 0.76),
    ("Bueng Kum", 1.7, 2.51), ("Pathum Wan", 1.7, 0.74), ("Sathon", 1.6, 1.32),
    ("Bang Khen", 1.6, 3.37), ("Bang Kapi", 1.6, 2.57), ("Huai Khwang", 1.6, 1.52),
    ("Suan Luang", 1.6, 2.23), ("Bangkok Yai", 1.6, 1.12), ("Khlong San", 1.6, 1.21),
    ("Watthana", 1.5, 1.47), ("Sai Mai", 1.5, 3.80), ("Bangkok Noi", 1.5, 1.81),
    ("Phra Khanon", 1.5, 1.57), ("Bang Na", 1.5, 1.57), ("Phasi Charoen", 1.5, 2.22),
    ("Thon Buri", 1.4, 1.81), ("Taling Chan", 1.4, 1.85), ("Bang Kho Laem", 1.4, 1.44),
    ("Khan Na Yao", 1.4, 1.74), ("Yan Nawa", 1.4, 1.35), ("Chom Thong", 1.3, 2.61),
    ("Khlong Toei", 1.3, 1.65), ("Bang Khae", 1.3, 3.50), ("Rat Burana", 1.2, 1.39),
    ("Saphan Sung", 1.2, 1.75), ("Prawet", 1.2, 3.33), ("Nong Khaem", 1.0, 2.83),
    ("Bang Bon", 1.0, 1.84), ("Thawi Watthana", 0.9, 1.44), ("Thung Khru", 0.8, 2.25),
    ("Bang Khun Thian", 0.8, 3.36), ("Min Buri", 0.6, 2.57), ("Khlong Sam Wa", 0.5, 3.81),
    ("Lat Krabang", 0.4, 3.25), ("Nong Chok", -0.2, 3.30),
]

TABLE_A1_4_HOT_EVENING = [
    ("Don Mueang", 3.7, 3.03), ("Lak Si", 3.6, 1.83), ("Sai Mai", 3.5, 3.80),
    ("Bang Khen", 3.3, 3.37), ("Bang Sue", 3.2, 2.17), ("Chatuchak", 3.1, 2.80),
    ("Bueng Kum", 3.1, 2.51), ("Lat Phrao", 3.1, 2.08), ("Khan Na Yao", 2.8, 1.74),
    ("Phaya Thai", 2.8, 1.19), ("Bang Kapi", 2.7, 2.57), ("Wang Thonglang", 2.7, 1.90),
    ("Din Daeng", 2.7, 2.02), ("Dusit", 2.6, 1.43), ("Ratchathewi", 2.6, 1.21),
    ("Bang Phlat", 2.5, 1.59), ("Pom Prap Sattru Phai", 2.5, 0.72), ("Pathum Wan", 2.4, 0.74),
    ("Suan Luang", 2.4, 2.23), ("Huai Khwang", 2.3, 1.52), ("Bang Rak", 2.3, 0.80),
    ("Khlong Sam Wa", 2.3, 3.81), ("Phra Nakhon", 2.3, 0.76), ("Samphanthawong", 2.3, 0.37),
    ("Saphan Sung", 2.2, 1.75), ("Bangkok Noi", 2.1, 1.81), ("Sathon", 2.0, 1.32),
    ("Phra Khanon", 2.0, 1.57), ("Watthana", 2.0, 1.47), ("Min Buri", 2.0, 2.57),
    ("Khlong San", 1.9, 1.21), ("Bangkok Yai", 1.9, 1.12), ("Taling Chan", 1.9, 1.85),
    ("Bang Na", 1.9, 1.57), ("Prawet", 1.8, 3.33), ("Thon Buri", 1.7, 1.81),
    ("Bang Kho Laem", 1.6, 1.44), ("Thawi Watthana", 1.6, 1.44), ("Khlong Toei", 1.5, 1.65),
    ("Phasi Charoen", 1.5, 2.22), ("Yan Nawa", 1.5, 1.35), ("Nong Chok", 1.5, 3.30),
    ("Bang Khae", 1.4, 3.50), ("Lat Krabang", 1.4, 3.25), ("Rat Burana", 1.2, 1.39),
    ("Chom Thong", 1.1, 2.61), ("Nong Khaem", 1.1, 2.83), ("Bang Bon", 0.9, 1.84),
    ("Thung Khru", 0.7, 2.25), ("Bang Khun Thian", 0.6, 3.36),
]

TABLE_A1_5_WET_NIGHT = [
    ("Pom Prap Sattru Phai", 3.3, 0.72), ("Bang Rak", 3.2, 0.80), ("Samphanthawong", 3.2, 0.37),
    ("Ratchathewi", 3.2, 1.21), ("Phra Nakhon", 3.2, 0.76), ("Phaya Thai", 3.2, 1.19),
    ("Pathum Wan", 3.1, 0.74), ("Khlong San", 3.1, 1.21), ("Din Daeng", 3.1, 2.02),
    ("Sathon", 3.1, 1.32), ("Bangkok Yai", 3.1, 1.12), ("Thon Buri", 3.0, 1.81),
    ("Bang Sue", 3.0, 2.17), ("Dusit", 3.0, 1.43), ("Bang Phlat", 3.0, 1.59),
    ("Bang Kho Laem", 2.9, 1.44), ("Bangkok Noi", 2.9, 1.81), ("Phasi Charoen", 2.9, 2.22),
    ("Chatuchak", 2.8, 2.80), ("Chom Thong", 2.8, 2.61), ("Watthana", 2.8, 1.47),
    ("Huai Khwang", 2.7, 1.52), ("Wang Thonglang", 2.7, 1.90), ("Yan Nawa", 2.7, 1.35),
    ("Rat Burana", 2.7, 1.39), ("Taling Chan", 2.7, 1.85), ("Khlong Toei", 2.6, 1.65),
    ("Bang Khae", 2.6, 3.50), ("Lat Phrao", 2.6, 2.08), ("Bang Na", 2.6, 1.57),
    ("Lak Si", 2.5, 1.83), ("Phra Khanon", 2.5, 1.57), ("Bang Bon", 2.5, 1.84),
    ("Suan Luang", 2.5, 2.23), ("Nong Khaem", 2.4, 2.83), ("Bang Kapi", 2.4, 2.57),
    ("Bang Khun Thian", 2.3, 3.36), ("Bueng Kum", 2.3, 2.51), ("Thung Khru", 2.1, 2.25),
    ("Thawi Watthana", 2.0, 1.44), ("Prawet", 2.0, 3.33), ("Don Mueang", 1.9, 3.03),
    ("Bang Khen", 1.8, 3.37), ("Khan Na Yao", 1.8, 1.74), ("Saphan Sung", 1.8, 1.75),
    ("Sai Mai", 1.3, 3.80), ("Lat Krabang", 0.7, 3.25), ("Min Buri", 0.7, 2.57),
    ("Khlong Sam Wa", 0.4, 3.81), ("Nong Chok", -0.1, 3.30),
]

TABLE_A1_6_WET_EVENING = [
    ("Din Daeng", 2.8, 2.02), ("Ratchathewi", 2.7, 1.21), ("Phaya Thai", 2.7, 1.19),
    ("Pom Prap Sattru Phai", 2.7, 0.72), ("Bang Rak", 2.7, 0.80), ("Bang Sue", 2.7, 2.17),
    ("Wang Thonglang", 2.6, 1.90), ("Pathum Wan", 2.6, 0.74), ("Samphanthawong", 2.6, 0.37),
    ("Phra Nakhon", 2.5, 0.76), ("Chatuchak", 2.5, 2.80), ("Bang Phlat", 2.5, 1.59),
    ("Dusit", 2.5, 1.43), ("Lat Phrao", 2.5, 2.08), ("Huai Khwang", 2.5, 1.52),
    ("Sathon", 2.4, 1.32), ("Watthana", 2.4, 1.47), ("Bang Kapi", 2.4, 2.57),
    ("Bueng Kum", 2.4, 2.51), ("Suan Luang", 2.4, 2.23), ("Khlong San", 2.3, 1.21),
    ("Bangkok Yai", 2.3, 1.12), ("Bangkok Noi", 2.3, 1.81), ("Thon Buri", 2.2, 1.81),
    ("Lak Si", 2.2, 1.83), ("Bang Na", 2.2, 1.57), ("Phra Khanon", 2.2, 1.57),
    ("Bang Kho Laem", 2.1, 1.44), ("Phasi Charoen", 2.1, 2.22), ("Yan Nawa", 2.0, 1.35),
    ("Taling Chan", 2.0, 1.85), ("Khlong Toei", 2.0, 1.65), ("Bang Khen", 2.0, 3.37),
    ("Khan Na Yao", 1.9, 1.74), ("Saphan Sung", 1.9, 1.75), ("Chom Thong", 1.9, 2.61),
    ("Prawet", 1.8, 3.33), ("Bang Khae", 1.8, 3.50), ("Rat Burana", 1.8, 1.39),
    ("Don Mueang", 1.8, 3.03), ("Sai Mai", 1.6, 3.80), ("Nong Khaem", 1.6, 2.83),
    ("Bang Bon", 1.6, 1.84), ("Bang Khun Thian", 1.4, 3.36), ("Thawi Watthana", 1.3, 1.44),
    ("Thung Khru", 1.2, 2.25), ("Min Buri", 0.9, 2.57), ("Lat Krabang", 0.7, 3.25),
    ("Khlong Sam Wa", 0.5, 3.81), ("Nong Chok", 0.0, 3.30),
]

TABLES = {
    "UHII_CoolDry_Night_C": TABLE_A1_1_COOL_NIGHT,
    "UHII_CoolDry_Evening_C": TABLE_A1_2_COOL_EVENING,
    "UHII_HotDry_Night_C": TABLE_A1_3_HOT_NIGHT,
    "UHII_HotDry_Evening_C": TABLE_A1_4_HOT_EVENING,
    "UHII_Wet_Night_C": TABLE_A1_5_WET_NIGHT,
    "UHII_Wet_Evening_C": TABLE_A1_6_WET_EVENING,
}


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(base_dir, "gis", "bangkok_worldbank_uhii_full.csv")

    all_districts = set()
    for rows in TABLES.values():
        all_districts.update(name for name, _, _ in rows)

    for col, rows in TABLES.items():
        names = [name for name, _, _ in rows]
        if len(names) != 50 or len(set(names)) != 50:
            raise SystemExit("{}: expected 50 unique districts, got {} rows / {} unique".format(
                col, len(names), len(set(names))))
        missing = all_districts - set(names)
        if missing:
            raise SystemExit("{}: missing districts {}".format(col, missing))

    by_district = {name: {"Population_Pct_BMA": pop} for name, _, pop in TABLE_A1_1_COOL_NIGHT}
    for col, rows in TABLES.items():
        for name, val, pop in rows:
            by_district[name][col] = val
            existing_pop = by_district[name]["Population_Pct_BMA"]
            if abs(existing_pop - pop) > 0.01:
                raise SystemExit("{} population mismatch across tables: {} vs {}".format(name, existing_pop, pop))

    fieldnames = ["District", "Population_Pct_BMA"] + list(TABLES.keys())
    rows_out = []
    for name in sorted(by_district):
        row = {"District": name, "Population_Pct_BMA": by_district[name]["Population_Pct_BMA"]}
        row.update({col: by_district[name][col] for col in TABLES})
        rows_out.append(row)

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    print("Wrote {} districts x {} UHII columns to {}".format(len(rows_out), len(TABLES), out_path))


if __name__ == "__main__":
    main()
