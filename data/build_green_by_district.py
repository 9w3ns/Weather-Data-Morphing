"""Per-district green-space summary + per-capita, benchmarked against UDDC / WHO.

Reads the OSM green backbone (fetch_green_space_osm.py) and reports, per district:
park area, all-green area, % of district area, and green m2/capita -- the metric
UDDC's "15-minute green city" leads with (Bangkok 7.6 m2/cap vs WHO 9).

POPULATION BASIS (documented assumption, plan decision 1): absolute registered
population per district is estimated as Population_Pct_BMA (from bangkok_uhi_data.csv)
x TOTAL_BMA_POP. This is REGISTERED (ทะเบียนราษฎร) population; Bangkok's de-facto /
daytime population is higher (~8-10M), which would LOWER per-capita green -- so these
figures are an upper bound on per-capita.

Run from the repo root. Output: data/gis/bangkok_green_by_district.csv
"""
import warnings

import geopandas as gpd
import pandas as pd

warnings.filterwarnings("ignore")

UTM47N = 32647
TOTAL_BMA_POP = 5_450_000     # ~registered BMA population; see docstring
UDDC_CITY_PER_CAPITA = 7.6    # m2/cap, uddc.net/scrollytellingminsgreen
WHO_PER_CAPITA = 9.0

GREEN = "data/gis/bangkok_green_space.geojson"
DISTRICTS = "data/gis/bangkok_districts.geojson"
UHI = "data/gis/bangkok_uhi_data.csv"
OUT = "data/gis/bangkok_green_by_district.csv"


def normalize_name(name):
    n = str(name).strip().lower()
    for token in ("khet ", " district"):
        n = n.replace(token, "")
    return n.strip()


def main():
    green = gpd.read_file(GREEN).to_crs(epsg=UTM47N)
    districts = gpd.read_file(DISTRICTS).to_crs(epsg=UTM47N)
    uhi = pd.read_csv(UHI)

    # Population per district from % share x total.
    pop = {normalize_name(r["District"]): r["Population_Pct_BMA"] / 100.0 * TOTAL_BMA_POP
           for _, r in uhi.iterrows()}

    park = green[green["green_class"] == "park"]
    park_by = park.groupby("district")["area_sqm"].sum()
    all_by = green.groupby("district")["area_sqm"].sum()

    rows = []
    for _, d in districts.iterrows():
        name = d["District"]
        norm = normalize_name(name)
        d_area = d.geometry.area
        park_area = float(park_by.get(name, 0.0))
        green_area = float(all_by.get(name, 0.0))
        population = pop.get(norm, float("nan"))
        rows.append({
            "district": name,
            "population_est": None if population != population else int(population),
            "district_area_sqkm": round(d_area / 1e6, 3),
            "park_area_sqkm": round(park_area / 1e6, 3),
            "green_area_sqkm": round(green_area / 1e6, 3),
            "green_pct_of_district": round(100.0 * green_area / d_area, 2) if d_area else None,
            "park_sqm_per_capita": round(park_area / population, 2) if population == population and population else None,
            "green_sqm_per_capita": round(green_area / population, 2) if population == population and population else None,
        })

    df = pd.DataFrame(rows).sort_values("green_sqm_per_capita", ascending=False,
                                        na_position="last")
    df["who_9_gap"] = (WHO_PER_CAPITA - df["green_sqm_per_capita"]).round(2)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")

    tot_park = park["area_sqm"].sum()
    tot_green = green["area_sqm"].sum()
    print("Wrote {} ({} districts).".format(OUT, len(df)))
    print("\nCity-wide (est. pop {:,}):".format(TOTAL_BMA_POP))
    print("  park green   : {:.2f} sq km  -> {:.2f} m2/capita".format(
        tot_park / 1e6, tot_park / TOTAL_BMA_POP))
    print("  all green    : {:.2f} sq km  -> {:.2f} m2/capita".format(
        tot_green / 1e6, tot_green / TOTAL_BMA_POP))
    print("  benchmarks   : UDDC {} | WHO {} m2/capita".format(
        UDDC_CITY_PER_CAPITA, WHO_PER_CAPITA))
    print("\nGreenest / least-green districts (all-green m2/capita):")
    show = df[["district", "green_sqm_per_capita", "park_sqm_per_capita", "green_pct_of_district"]]
    print(show.head(6).to_string(index=False))
    print("  ...")
    print(show.tail(6).to_string(index=False))


if __name__ == "__main__":
    main()
