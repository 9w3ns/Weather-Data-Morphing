"""
Phase 1 site-selection scoring (docs/SiteSelectionMatrixGemini.md, Tier 1).

Combines the four criteria into a weighted 0-10 ranking of Bangkok's 50
districts for the evening thermal-refuge civic center:

  1. UHI severity (evening peak)   35%  -> UHII_HotDry_Evening_C (primary, 0.7)
                                          + LST_Mean_C (secondary daytime-
                                          storage proxy, 0.3)
  2. Housing vulnerability (equity) 30%  -> Dominant_LCZ ordinal (weight, not gate)
  3. Transit / intercept potential  25%  -> rapid-transit station count
  4. Demographic density            10%  -> Population_Pct_BMA

Continuous metrics are min-max normalized to 0-10 across all 50 districts.
LCZ is mapped to an ordinal score (LCZ 3 target = 10). Final score is the
weighted sum. A sensitivity check re-runs the ranking under equal weights and
+/-10% weight perturbations to test whether the top 3 is stable.

NOTE - Tier 0 (the work<->home intercept land-use gate) is NOT applied here
because it needs the Bangkok Comprehensive Plan land-use map, which we don't
have as data. The 25% transit weight partially proxies intercept potential.
Apply the Tier 0 check manually to the top candidates before locking the site.

Inputs : data/gis/bangkok_uhi_data.csv, data/gis/bangkok_transit_data.csv
Output : data/gis/site_selection_scores.csv
"""
import csv
import os

WEIGHTS = {"uhi": 0.35, "vulnerability": 0.30, "transit": 0.25, "population": 0.10}
UHI_EVENING_SHARE = 0.7   # evening UHII is primary within the UHI criterion
UHI_LST_SHARE = 0.3       # daytime surface LST is the secondary proxy


def lcz_ordinal(lcz_label):
    """Vulnerability score by built form (docs SiteSelectionMatrixGemini.md §3)."""
    if "LCZ 3" in lcz_label:   # compact low-rise -- the target typology
        return 10.0
    if "LCZ 2" in lcz_label:   # compact midrise -- hot but denser/wealthier
        return 6.0
    if "LCZ 8" in lcz_label:   # large low-rise
        return 4.0
    return 2.0                 # open/natural classes


def minmax(values):
    lo, hi = min(values), max(values)
    span = hi - lo
    return [10.0 * (v - lo) / span if span else 0.0 for v in values]


def load_rows():
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gis")
    with open(os.path.join(base, "bangkok_uhi_data.csv"), encoding="utf-8") as f:
        uhi = {r["District"]: r for r in csv.DictReader(f)}
    with open(os.path.join(base, "bangkok_transit_data.csv"), encoding="utf-8") as f:
        transit = {r["District"]: int(r["Transit_Station_Count"]) for r in csv.DictReader(f)}

    rows = []
    for name, r in uhi.items():
        rows.append({
            "District": name,
            "evening": float(r["UHII_HotDry_Evening_C"]),
            "lst": float(r["LST_Mean_C"]),
            "lcz": r["Dominant_LCZ"],
            "pop": float(r["Population_Pct_BMA"]),
            "tier": r["UHI_Tier"],
            "transit": transit.get(name, 0),
        })
    return rows


def score(rows, weights):
    ev = minmax([r["evening"] for r in rows])
    lst = minmax([r["lst"] for r in rows])
    tr = minmax([float(r["transit"]) for r in rows])
    pop = minmax([r["pop"] for r in rows])
    out = []
    for i, r in enumerate(rows):
        uhi = UHI_EVENING_SHARE * ev[i] + UHI_LST_SHARE * lst[i]
        vuln = lcz_ordinal(r["lcz"])
        total = (weights["uhi"] * uhi + weights["vulnerability"] * vuln
                 + weights["transit"] * tr[i] + weights["population"] * pop[i])
        out.append({**r, "s_uhi": uhi, "s_vuln": vuln, "s_transit": tr[i],
                    "s_pop": pop[i], "score": total})
    out.sort(key=lambda r: -r["score"])
    return out


def sensitivity(rows, base_top3):
    """Report whether the top 3 survives equal weights + per-weight +/-10%."""
    scenarios = {"equal": {k: 0.25 for k in WEIGHTS}}
    for k in WEIGHTS:
        for sign, tag in ((1.10, "+10%"), (0.90, "-10%")):
            w = dict(WEIGHTS)
            w[k] = WEIGHTS[k] * sign
            tot = sum(w.values())
            scenarios["{} {}".format(k, tag)] = {kk: vv / tot for kk, vv in w.items()}

    print("\nSensitivity analysis (base top 3: {}):".format(", ".join(base_top3)))
    stable = True
    for tag, w in scenarios.items():
        top3 = [r["District"] for r in score(rows, w)[:3]]
        same = set(top3) == set(base_top3)
        stable = stable and same
        print("  {:<18} top3 {}  {}".format(
            tag, "STABLE" if same else "CHANGED", "" if same else "-> " + ", ".join(top3)))
    print("  => Top 3 is {} across all tested weightings.".format(
        "ROBUST" if stable else "SENSITIVE (treat top tier as ~tied; defer to Tier 2)"))


def main():
    rows = load_rows()
    ranked = score(rows, WEIGHTS)

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "gis", "site_selection_scores.csv")
    fields = ["Rank", "District", "score", "tier", "lcz", "evening", "lst",
              "transit", "pop", "s_uhi", "s_vuln", "s_transit", "s_pop"]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for i, r in enumerate(ranked, 1):
            w.writerow([i, r["District"], round(r["score"], 2), r["tier"], r["lcz"],
                        r["evening"], r["lst"], r["transit"], r["pop"],
                        round(r["s_uhi"], 2), round(r["s_vuln"], 2),
                        round(r["s_transit"], 2), round(r["s_pop"], 2)])

    print("Wrote ranked scores to {}\n".format(out_path))
    print("{:<4}{:<26}{:<7}{:<9}{:<26}{:<7}".format(
        "#", "District", "Score", "Tier", "LCZ", "Stations"))
    for i, r in enumerate(ranked[:10], 1):
        print("{:<4}{:<26}{:<7}{:<9}{:<26}{:<7}".format(
            i, r["District"], round(r["score"], 2), r["tier"], r["lcz"], r["transit"]))

    top3 = [r["District"] for r in ranked[:3]]
    sensitivity(rows, top3)

    # Suggested control: lowest-scoring, non-LCZ-3, Low tier -- a genuinely
    # different urban climate for the morphing contrast pair.
    controls = [r for r in ranked if "LCZ 3" not in r["lcz"] and r["tier"] == "Low"]
    controls.sort(key=lambda r: r["score"])
    if controls:
        c = controls[0]
        print("\nSuggested control district (contrast pair): {} "
              "(Tier {}, {}, score {}).".format(
                  c["District"], c["tier"], c["lcz"], round(c["score"], 2)))


if __name__ == "__main__":
    main()
