"""Fetch BMA's สวน 15 นาที (15-minute park) programme list from Open Data Bangkok.

The greener.bangkok.go.th map (529 gardens) exposes no static export, but the
Open Data Bangkok CKAN portal (data.bangkok.go.th) publishes the underlying
programme list as a CSV: dataset "สวน 15 นาที" -> env_park15_min.csv.

This is the one public handle on the BMA 15-minute-park effort -- the same
programme flagged in bma_land_sourcing_notes.md as the lead for VACANT city land
that the facility-seeded BMA land layer cannot see. Kept as a parallel lead layer.

WHAT IT HAS: district (Thai), park name, area (rai/ngan/wa -> m2), whether it is a
renovation of an existing space or a new build, and completion month/year.
WHAT IT LACKS: coordinates (so not directly mappable) and an explicit ownership
field -- these are programme parks, not a title register. Treat as leads.

Run from the repo root.
Output: data/gis/bangkok_15min_parks.csv + a printed per-district summary.
"""
import io

import pandas as pd
import requests

CKAN = "https://data.bangkok.go.th/api/3/action/package_search"
USER_AGENT = "thesis-site-selection/1.0 (academic research)"
OUT = "data/gis/bangkok_15min_parks.csv"

RAI, NGAN, WA = 1600.0, 400.0, 4.0  # m2 per Thai land unit
THAI_MON = {"ม.ค.": 1, "ก.พ.": 2, "มี.ค.": 3, "เม.ย.": 4, "พ.ค.": 5, "มิ.ย.": 6,
            "ก.ค.": 7, "ส.ค.": 8, "ก.ย.": 9, "ต.ค.": 10, "พ.ย.": 11, "ธ.ค.": 12}


def parse_completed(s):
    """'ก.พ.-66' -> (2, 2023). Best-effort; returns (None, None) if unparseable."""
    s = str(s or "").strip()
    if not s or s == "0" or "-" not in s:
        return None, None
    mon, _, yr = s.partition("-")
    month = THAI_MON.get(mon.strip())
    try:
        be = int(yr.strip())
        be = be + 2500 if be < 100 else be   # 2-digit BE year -> 25xx
        return month, be - 543               # -> CE
    except ValueError:
        return month, None


def main():
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    pkgs = s.get(CKAN, params={"q": "สวน 15 นาที", "rows": 10}, timeout=60).json()
    target = next((p for p in pkgs["result"]["results"]
                   if p.get("title", "").strip() == "สวน 15 นาที"),
                  pkgs["result"]["results"][0])
    res = next((r for r in target["resources"]
                if "csv" in (r.get("format", "").lower())
                or r.get("url", "").lower().endswith(".csv")), target["resources"][0])
    print("Source: '{}' -> {}".format(target.get("title"), res.get("url")))

    raw = s.get(res["url"], timeout=120).content.decode("utf-8-sig", errors="replace")
    df = pd.read_csv(io.StringIO(raw))
    df.columns = [c.strip() for c in df.columns]

    def num(col):
        return pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0)

    out = pd.DataFrame({
        "id": df.get("id"),
        "district_th": df.get("Dis_trict", "").astype(str).str.strip(),
        "name_th": df.get("na_me", "").astype(str).str.strip(),
        "area_sqm": (num("Rai") * RAI + num("Ngan") * NGAN + num("Sqaure Wa") * WA).round(1),
    })
    ren = df.get("Renovate original", "").astype(str).str.strip()
    new = df.get("Develop new", "").astype(str).str.strip()
    out["status"] = ["renovation" if r == "/" else "new_build" if n == "/" else ""
                     for r, n in zip(ren, new)]
    parsed = [parse_completed(v) for v in df.get("Month Year Completed", "")]
    out["completed_month"] = [p[0] for p in parsed]
    out["completed_year_ce"] = [p[1] for p in parsed]
    out["source"] = "data.bangkok.go.th (สวน 15 นาที / env_park15_min.csv)"

    out.to_csv(OUT, index=False, encoding="utf-8-sig")

    total_ha = out["area_sqm"].sum() / 1e4
    print("\nWrote {} -- {} parks, {:.1f} ha total.".format(OUT, len(out), total_ha))
    print("Status: {}".format(out["status"].value_counts().to_dict()))
    by = (out.groupby("district_th")
          .agg(parks=("id", "count"), area_sqm=("area_sqm", "sum"))
          .sort_values("area_sqm", ascending=False))
    print("\nTop districts by 15-min-park area:")
    print(by.head(12).to_string())
    print("\nNOTE: district-level only (no coordinates), no ownership field -- leads, "
          "not a title register. Complements the facility-seeded BMA land layer, which "
          "cannot see vacant city land.")


if __name__ == "__main__":
    main()
