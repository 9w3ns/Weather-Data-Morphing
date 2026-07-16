"""Infer which Bangkok land parcels are under BMA ownership, and size the sites.

Third stage of the BMA land pipeline. Joins:
    fetch_bma_parcels.py     -> real cadastral boundaries, no owner attribute
    fetch_bma_facilities.py  -> things the city operates, no boundary
into a single answer: the parcels underneath a BMA-operated facility, dissolved
into whole sites with real areas -- i.e. a map of the city's land holdings, for
siting the civic centre.

THIS IS AN INFERENCE, NOT A TITLE SEARCH. It assumes the operator of a facility
owns the land under it. That is usually true and never guaranteed -- BMA leases
some sites. Nothing here is legal evidence; confirm with สำนักการคลัง or the
Department of Lands before committing to a site. See
docs/bma_land_sourcing_notes.md.

WHERE THAT ASSUMPTION BREAKS, MEASURED: real runs produced two classes of false
positive, both now demoted by flag_ownership_risks() --
  - all five Bang Rak "BMA schools" were วัด schools in temple compounds (54-93%
    temple overlap); the city runs the school, the wat owns the ground.
  - Khlong Toei's "BMA school" claimed a 240,000 sqm parcel that is really the
    Port Authority estate (ท่าเรือกรุงเทพ), shared with housing-authority flats, a
    mosque and a railway.
Both are the same lesson: "BMA operates it" != "BMA owns it". Assume the gap also
exists for classes we cannot detect (leased offices, ราชพัสดุ land BMA occupies).
A `high` rating means "no disqualifier found", NOT "title confirmed".

THE BIG BLIND SPOT: this can only find BMA land with a BMA facility ON it. Vacant
city land has no facility to seed from and is therefore INVISIBLE here. What this
does find is UNDERUSED city sites -- district office car parks, tired markets,
school grounds -- which is the stronger civic-centre premise anyway: you activate
a known public asset instead of inventing a plot. For vacant BMA land the one
public lead is the สวน 15 นาที programme (greener.bangkok.go.th), not yet wired up.

HOW FACILITIES CLAIM PARCELS: OSM usually maps the BUILDING, not the site, so a
facility footprint normally sits INSIDE one larger parcel rather than covering
several. But a big school's grounds can span many small ones (Bang Rak's median
parcel is ~61 sqm). Both directions are handled -- see match_polygon_facilities.
The parcel is what we want, not the footprint: the building is not the land.

Deliberately does NOT feed rank_score in fetch_vacant_plots_osm.py: those five
weights sum to 1.0 by design, and BMA ownership is a different question from OSM
vacancy. This is a parallel layer.

Run from the repo root.

Outputs:
    data/gis/bangkok_bma_land.geojson   (EPSG:4326)
    data/gis/bangkok_bma_land_scored.csv
    docs/bangkok_bma_land_map.png
"""
import argparse
import glob
import warnings

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

warnings.filterwarnings("ignore")

# --- Configuration ---------------------------------------------------------
UTM47N = 32647
MIN_PARCEL_COVER = 0.5       # fraction of a parcel that must sit inside a facility
DEFAULT_MIN_AREA_SQM = 2000.0  # a civic centre needs real land; drop slivers
DEFAULT_MIN_CONF = "high"
CONF_RANK = {"low": 0, "medium": 1, "high": 2}
TEMPLE_OVERLAP_MAX = 0.25    # above this share of a site, call it temple land
# A seed only justifies claiming land commensurate with the facility. Past these,
# the facility is a tenant on somebody's estate -- see flag_ownership_risks().
MAX_PARCEL_TO_SEED_RATIO = 10.0    # polygon seeds: parcel vs footprint
POINT_SEED_MAX_AREA_SQM = 20000.0  # point seeds: no footprint, so cap absolutely


def normalize_name(name):
    n = str(name).strip().lower()
    for token in ("khet ", " district"):
        n = n.replace(token, "")
    return n.strip()


def load_parcels():
    paths = sorted(glob.glob("data/gis/bangkok_parcels_*.geojson"))
    if not paths:
        raise SystemExit("No parcel files found. Run fetch_bma_parcels.py first.")
    frames = [gpd.read_file(p) for p in paths]
    parcels = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True),
                               crs=frames[0].crs)
    print("   - {} parcels from {} district file(s): {}".format(
        len(parcels), len(paths), ", ".join(sorted(parcels["district"].unique()))))
    return parcels.to_crs(epsg=UTM47N)


def match_polygon_facilities(fac, parcels):
    """Parcels that a facility footprint sits on.

    A parcel qualifies two ways, because OSM footprints and cadastral parcels
    nest in opposite directions depending on what got mapped:

      - the facility covers >= MIN_PARCEL_COVER of the PARCEL. A big site (school
        grounds) spanning many small parcels claims each one outright.
      - the parcel holds the largest share of the FACILITY. This is the common
        case and the one a parcel-only rule misses: OSM usually maps just the
        BUILDING, which sits well inside a larger parcel. Bang Rak District
        Office's building is 1053 sqm on a ~2100 sqm parcel -- 49% of it, so a
        naive 50%-of-parcel test drops the single most certain BMA site in the
        district.

    Every facility therefore claims at least one parcel. Note the parcel, not the
    footprint, is the thing we want: the building is not the land.
    """
    poly = fac[fac.geom_type.isin(["Polygon", "MultiPolygon"])]
    empty = pd.DataFrame(columns=["parcel_id", "facility_id", "cover"])
    if poly.empty:
        return empty
    inter = gpd.overlay(parcels[["parcel_id", "area_sqm", "geometry"]],
                        poly[["facility_id", "geometry"]], how="intersection")
    if inter.empty:
        return empty

    shared_sqm = inter.geometry.area
    inter["cover"] = shared_sqm / inter["area_sqm"]  # share of the parcel
    fac_area = poly.set_index("facility_id").geometry.area
    inter["fac_share"] = shared_sqm / inter["facility_id"].map(fac_area)

    spans_parcel = inter["cover"] >= MIN_PARCEL_COVER
    primary = inter.index.isin(
        inter.sort_values("fac_share", ascending=False)
             .drop_duplicates("facility_id").index)
    keep = inter[spans_parcel | primary]
    return keep[["parcel_id", "facility_id", "cover"]].copy()


def match_point_facilities(fac, parcels):
    """The single parcel containing a facility point.

    Point seeds under-measure: a school mapped as one point claims one parcel,
    not its whole grounds. site_area_sqm for these is a LOWER BOUND.
    """
    pts = fac[fac.geom_type == "Point"]
    empty = pd.DataFrame(columns=["parcel_id", "facility_id", "cover"])
    if pts.empty:
        return empty
    hit = gpd.sjoin(pts[["facility_id", "geometry"]], parcels[["parcel_id", "geometry"]],
                    how="inner", predicate="within")
    if hit.empty:
        return empty
    return pd.DataFrame({"parcel_id": hit["parcel_id"].values,
                         "facility_id": hit["facility_id"].values,
                         "cover": 1.0})


def flag_ownership_risks(sites, fac):
    """Demote sites where "BMA operates it" stops implying "BMA owns it".

    Two failure modes, both found on real runs rather than imagined:

    1. TEMPLE LAND. BMA runs hundreds of วัด schools built inside temple grounds.
       The city operates the school; the temple owns the ground (ธรณีสงฆ์). On the
       first Bang Rak run ALL FIVE "BMA school" sites came back 54-93% covered by
       a temple compound, while the district office had 0%.

    2. OVERSIZED PARCEL. A seed only justifies claiming land commensurate with the
       facility. Where the containing parcel dwarfs the footprint, the facility is
       a TENANT on somebody's estate. Khlong Toei's "BMA school" claimed a single
       240,000 sqm parcel that is really the Port Authority estate (ท่าเรือกรุงเทพ)
       -- the same parcel holds the National Housing Authority flats, a mosque, a
       railway and other schools. PAT is a state enterprise; that land is not the
       city's. NOT_BMA_PATTERNS could not catch it because the operator tag is
       simply absent, which is why this geometric guard exists: it needs no tags.

    Demote rather than delete -- the evidence (overlap %, ratio) should be visible
    and arguable, not silently dropped.
    """
    sites = sites.reset_index(drop=True)
    risks = [[] for _ in range(len(sites))]

    try:
        temples = gpd.read_file("data/gis/bangkok_temple_land.geojson").to_crs(epsg=UTM47N)
        overlap = (sites.geometry.intersection(temples.geometry.union_all()).area
                   / sites.geometry.area)
        sites["temple_overlap_pct"] = (overlap * 100).round(1)
        for i, h in enumerate(overlap >= TEMPLE_OVERLAP_MAX):
            if h:
                risks[i].append("temple_land")
    except Exception as exc:
        print("   ! temple layer unavailable ({}); skipping that check. "
              "Re-run fetch_bma_facilities.py.".format(exc))
        sites["temple_overlap_pct"] = float("nan")

    # Points have zero area, so they get an absolute cap instead of a ratio.
    seed_area = sites["facility_id"].map(
        fac.set_index("facility_id").geometry.area).fillna(0.0)
    ratio = sites["site_area_sqm"] / seed_area.replace(0.0, float("nan"))
    sites["seed_area_sqm"] = seed_area.round(1)
    sites["parcel_to_seed_ratio"] = ratio.round(1)
    oversized = ((ratio > MAX_PARCEL_TO_SEED_RATIO)
                 | ((seed_area <= 0) & (sites["site_area_sqm"] > POINT_SEED_MAX_AREA_SQM)))
    for i, h in enumerate(oversized.fillna(False)):
        if h:
            risks[i].append("oversized_parcel")

    sites["land_owner_risk"] = [";".join(r) if r else "none" for r in risks]
    hit = sites["land_owner_risk"] != "none"
    sites.loc[hit, "ownership_confidence"] = "low"
    if hit.any():
        counts = pd.Series([r for rs in risks for r in rs]).value_counts()
        print("   - {} site(s) demoted to 'low': {}".format(
            int(hit.sum()), counts.to_dict()))
    return sites


def attach_context(sites):
    """District UHI / intercept / transit, reusing fetch_vacant_plots_osm.py's joins."""
    cent = sites.copy()
    cent["geometry"] = sites.geometry.centroid

    nodes = pd.read_csv("data/gis/bangkok_transit_nodes.csv")
    stations = gpd.GeoDataFrame(
        nodes[["Name"]],
        geometry=gpd.points_from_xy(nodes["Lon"], nodes["Lat"]),
        crs=4326,
    ).to_crs(epsg=UTM47N)
    near = gpd.sjoin_nearest(cent[["site_id", "geometry"]], stations,
                             how="left", distance_col="dist_to_station_m")
    near = near.drop_duplicates("site_id").set_index("site_id")
    sites["dist_to_station_m"] = sites["site_id"].map(near["dist_to_station_m"])
    sites["nearest_station"] = sites["site_id"].map(near["Name"])

    scores = pd.read_csv("data/gis/bangkok_intercept_scores.csv")
    score_by_norm = {normalize_name(r["District"]): r["Intercept_Score_Pct"]
                     for _, r in scores.iterrows()}
    sites["intercept_score"] = sites["district"].apply(
        lambda d: score_by_norm.get(normalize_name(d), 0.0))

    uhi = pd.read_csv("data/gis/bangkok_uhi_data.csv")
    uhi_by_norm = {normalize_name(r["District"]): (r["UHII_HotDry_Evening_C"],
                                                   r["LST_Mean_C"])
                   for _, r in uhi.iterrows()}

    def lookup_uhi(dname, idx):
        v = uhi_by_norm.get(normalize_name(dname))
        return v[idx] if v else float("nan")

    sites["uhii_hotdry_evening_c"] = sites["district"].apply(lambda d: lookup_uhi(d, 0))
    sites["lst_mean_c"] = sites["district"].apply(lambda d: lookup_uhi(d, 1))
    return sites


def build(min_area, min_conf):
    fac_path = "data/gis/bangkok_bma_facilities.geojson"
    out_geojson = "data/gis/bangkok_bma_land.geojson"
    out_csv = "data/gis/bangkok_bma_land_scored.csv"
    out_map = "docs/bangkok_bma_land_map.png"

    print("1. Loading parcels...")
    parcels = load_parcels()

    print("2. Loading BMA facility seeds...")
    fac = gpd.read_file(fac_path).to_crs(epsg=UTM47N)
    floor = CONF_RANK[min_conf]
    before = len(fac)
    fac = fac[fac["ownership_confidence"].map(CONF_RANK) >= floor].copy()
    print("   - {} of {} facilities at confidence >= '{}'.".format(
        len(fac), before, min_conf))
    if fac.empty:
        raise SystemExit("No facilities at that confidence. Try --min-confidence medium.")

    print("3. Matching facilities to parcels...")
    poly_m = match_polygon_facilities(fac, parcels)
    pt_m = match_point_facilities(fac, parcels)
    print("   - {} parcel matches from footprints, {} from points.".format(
        len(poly_m), len(pt_m)))
    matches = pd.concat([poly_m, pt_m], ignore_index=True)
    if matches.empty:
        raise SystemExit("No parcels sit under any BMA facility. Are the parcel "
                         "districts and the facilities in the same place?")

    # One parcel -> one site. Overlapping facilities (a school inside a park) would
    # otherwise double-count the same land; the better-covered facility wins.
    dupes = int(matches.duplicated("parcel_id").sum())
    matches = matches.sort_values("cover", ascending=False).drop_duplicates("parcel_id")
    if dupes:
        print("   - {} parcel(s) claimed by >1 facility; kept the best-covering one.".format(dupes))

    print("4. Dissolving parcels into sites...")
    sel = parcels.merge(matches, on="parcel_id")
    sites = sel.dissolve(by="facility_id", aggfunc={"area_sqm": "sum"})
    sites = sites.join(sel.groupby("facility_id").size().rename("n_parcels"))
    sites = sites.join(sel.groupby("facility_id")["district"].first())
    sites = sites.rename(columns={"area_sqm": "site_area_sqm"}).reset_index()

    attrs = fac.set_index("facility_id")[
        ["name", "category", "operator_raw", "ownership_confidence", "source"]]
    sites = sites.join(attrs, on="facility_id")
    sites["seed_geom"] = sites["facility_id"].map(
        fac.set_index("facility_id").geom_type)
    sites["site_id"] = range(len(sites))
    print("   - {} sites from {} parcels.".format(len(sites), len(sel)))

    print("5. Checking ownership risks (temple land, oversized parcels)...")
    sites = flag_ownership_risks(sites, fac)

    print("6. Attaching UHI / intercept / transit context...")
    sites = attach_context(sites)

    print("7. Filtering (area >= {:.0f} sqm, confidence >= '{}')...".format(
        min_area, min_conf))
    before = len(sites)
    sites = sites[sites["site_area_sqm"] >= min_area].copy()
    # Re-apply the confidence floor: flag_temple_land demotes sites AFTER the
    # facility-level filter, so this is what actually drops wat land from a
    # --min-confidence high run.
    sites = sites[sites["ownership_confidence"].map(CONF_RANK) >= CONF_RANK[min_conf]]
    sites = sites.sort_values("site_area_sqm", ascending=False).reset_index(drop=True)
    print("   - {} of {} sites kept.".format(len(sites), before))
    if sites.empty:
        raise SystemExit("No sites survived. Try --min-area 0 or "
                         "--min-confidence low (and read land_owner_risk).")

    print("8. Writing outputs...")
    cols = ["site_id", "district", "name", "category", "ownership_confidence",
            "land_owner_risk", "temple_overlap_pct", "parcel_to_seed_ratio",
            "n_parcels", "site_area_sqm", "seed_geom", "dist_to_station_m",
            "nearest_station", "intercept_score", "uhii_hotdry_evening_c",
            "lst_mean_c", "operator_raw", "source"]
    out = sites[cols + ["geometry"]].to_crs(epsg=4326)
    out.to_file(out_geojson, driver="GeoJSON")
    sites[cols].to_csv(out_csv, index=False, encoding="utf-8-sig")
    print("   - {}\n   - {}".format(out_geojson, out_csv))

    print("9. Rendering map...")
    districts = gpd.read_file("data/gis/bangkok_districts.geojson")
    scope = districts[districts["District"].isin(sites["district"].unique())]
    fig, ax = plt.subplots(figsize=(14, 14))
    scope.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=0.8, alpha=0.5)
    parcels.to_crs(epsg=4326).plot(ax=ax, facecolor="none", edgecolor="grey",
                                   linewidth=0.15, alpha=0.5)
    colours = {"high": "#1a9850", "medium": "#fdae61", "low": "#d73027"}
    for conf, grp in out.groupby("ownership_confidence"):
        grp.plot(ax=ax, color=colours.get(conf, "blue"), alpha=0.85,
                 label="{} ({})".format(conf, len(grp)))
    ax.legend(title="Inferred BMA ownership", loc="upper right")
    ax.set_title("Bangkok: inferred BMA-owned land\n"
                 "cadastral parcels (BMA GIS) under BMA-operated facilities\n"
                 "INFERRED FROM OPERATION, NOT A TITLE SEARCH -- verify before use",
                 fontsize=14)
    plt.tight_layout()
    plt.savefig(out_map, dpi=200)
    print("   - {}".format(out_map))

    print("\nTop 10 BMA sites by area:")
    show = ["site_id", "district", "category", "ownership_confidence",
            "n_parcels", "site_area_sqm", "dist_to_station_m"]
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(sites[show].head(10).to_string(index=False))
    print("\nBy category:")
    print(sites.groupby("category")["site_area_sqm"].agg(["count", "median", "sum"]).to_string())
    print("\nDone. Point-seeded sites (seed_geom == 'Point') are LOWER BOUNDS on area "
          "--\nthey claim only the parcel under the point, not the whole grounds.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--min-area", type=float, default=DEFAULT_MIN_AREA_SQM,
                    help="Drop sites below this area in sqm (default: %(default)s).")
    ap.add_argument("--min-confidence", choices=["low", "medium", "high"],
                    default=DEFAULT_MIN_CONF,
                    help="Lowest ownership confidence to include (default: %(default)s). "
                         "Anything below 'high' needs manual verification.")
    args = ap.parse_args()
    build(args.min_area, args.min_confidence)
