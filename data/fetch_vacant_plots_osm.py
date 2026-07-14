"""Extract candidate empty / underused land plots in Bangkok (Tier 2).

Sibling of fetch_land_use_osm.py. Pulls OSM vacancy SIGNALS city-wide, tags each
plot with how well it fits the site-selection funnel (work<->home intercept
context, transit proximity, district intercept score), and ranks them so only a
handful of top candidates need manual satellite/Street-View verification.

HONESTY CAVEAT: OSM has no reliable "vacant" tag, and absence of a building in
OSM does NOT mean a plot is empty (it is often just unmapped). These are
CANDIDATES TO VERIFY, not an authoritative vacancy map. grass/scrub in
particular are noisy (mostly landscaping, not buildable) -- they are kept but
flagged low-confidence via `source_class` / `source_confidence` so they can be
filtered downstream.

Signals used (per user decision): explicit vacant tags
(landuse=brownfield/greenfield/construction) + open-vegetation gaps
(landuse=grass, natural=scrub). Surface parking and negative-space heuristics
are deliberately excluded.
"""
import osmnx as ox
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import warnings

warnings.filterwarnings("ignore")

# --- Configuration ---------------------------------------------------------
UTM47N = 32647                 # projected CRS for Bangkok (metres)
MIN_AREA_SQM = 400.0           # buildable floor; drop slivers below this
IDEAL_MAX_AREA_SQM = 20000.0   # above this, likely rural greenfield -> size-penalised
INTERCEPT_BUFFER_M = 200.0     # work-zone buffer, identical to fetch_land_use_osm.py

# source_class -> confidence (explicit vacant tags are trustworthy; vegetation
# tags are noisy landscaping-vs-buildable).
HIGH_CONF = {"brownfield", "greenfield", "construction"}
CONF_HIGH, CONF_LOW = 1.0, 0.4

# rank_score component weights (must sum to 1.0). Easy to re-tune.
W_PROX, W_INTERCEPT, W_SURFACE, W_CONF, W_SIZE = 0.35, 0.25, 0.20, 0.10, 0.10


def normalize_name(name):
    n = str(name).strip().lower()
    for token in ("khet ", " district"):
        n = n.replace(token, "")
    return n.strip()


def classify_source(row):
    """Which signal tag matched this feature (explicit landuse takes priority)."""
    lu = row.get("landuse")
    if lu in ("brownfield", "greenfield", "construction", "grass"):
        return lu
    if row.get("natural") == "scrub":
        return "scrub"
    return None


def build_intercept_surface(res_path, work_path):
    """Rebuild the work<->home intercept surface (residential fabric within 200m
    of a working zone), same construction as fetch_land_use_osm.py. Returns a
    single dissolved geometry in EPSG:32647 (or None if inputs unavailable)."""
    try:
        res = gpd.read_file(res_path).to_crs(epsg=UTM47N)
        work = gpd.read_file(work_path).to_crs(epsg=UTM47N)
    except Exception as e:
        print(f"   ! intercept surface unavailable ({e}); skipping that criterion.")
        return None
    work_buffer = work.geometry.buffer(INTERCEPT_BUFFER_M).union_all()
    res_union = res.geometry.union_all()
    return res_union.intersection(work_buffer)


def norm01(series):
    lo, hi = series.min(), series.max()
    if hi - lo <= 0:
        return pd.Series(0.0, index=series.index)
    return (series - lo) / (hi - lo)


def fetch_and_rank_plots():
    districts_path = "data/gis/bangkok_districts.geojson"
    res_path = "data/gis/bangkok_residential_zones.geojson"
    work_path = "data/gis/bangkok_working_zones.geojson"
    scores_path = "data/gis/bangkok_intercept_scores.csv"
    nodes_path = "data/gis/bangkok_transit_nodes.csv"
    out_geojson = "data/gis/bangkok_vacant_plots.geojson"
    out_csv = "data/gis/bangkok_vacant_plots_scored.csv"
    out_map = "docs/bangkok_vacant_plots_map.png"

    ox.settings.timeout = 1800
    ox.settings.use_cache = True

    print("1. Loading districts...")
    districts = gpd.read_file(districts_path)
    districts_proj = districts.to_crs(epsg=UTM47N)

    print("2. Fetching candidate vacant plots from OSM (city-wide)...")
    tags = {"landuse": ["brownfield", "greenfield", "construction", "grass"],
            "natural": "scrub"}
    gdf = ox.features_from_place("Bangkok, Thailand", tags=tags)
    gdf = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    if "natural" not in gdf.columns:
        gdf["natural"] = None
    if "landuse" not in gdf.columns:
        gdf["landuse"] = None

    gdf["source_class"] = gdf.apply(classify_source, axis=1)
    gdf = gdf[gdf["source_class"].notna()].copy()
    print(f"   - {len(gdf)} candidate polygons fetched.")

    # Project, de-duplicate identical geometries, drop slivers.
    gdf = gdf.to_crs(epsg=UTM47N)
    gdf["_wkb"] = gdf.geometry.apply(lambda g: g.wkb)
    gdf = gdf.drop_duplicates("_wkb").drop(columns="_wkb")
    gdf["area_sqm"] = gdf.geometry.area
    gdf = gdf[gdf["area_sqm"] >= MIN_AREA_SQM].copy()
    gdf = gdf.reset_index(drop=True)
    gdf["plot_id"] = gdf.index
    print(f"   - {len(gdf)} after de-dup + min-area ({MIN_AREA_SQM:.0f} sqm) filter.")

    # Centroids drive all the spatial joins.
    cent = gdf.copy()
    cent["geometry"] = gdf.geometry.centroid

    print("3. Assigning districts (centroid within district)...")
    joined = gpd.sjoin(cent[["plot_id", "geometry"]], districts_proj[["District", "geometry"]],
                       how="left", predicate="within")
    # A centroid on a shared border can match >1 district; keep the first.
    joined = joined.drop_duplicates("plot_id").set_index("plot_id")
    gdf["district"] = gdf["plot_id"].map(joined["District"])

    print("4. Joining district intercept scores...")
    scores = pd.read_csv(scores_path)
    score_by_norm = {normalize_name(r["District"]): (r["Intercept_Score_Pct"],
                                                      r["Intercept_Pct_of_Residential"])
                     for _, r in scores.iterrows()}

    def lookup_score(dname, idx):
        if not isinstance(dname, str):
            return 0.0
        v = score_by_norm.get(normalize_name(dname))
        return v[idx] if v else 0.0

    gdf["intercept_score"] = gdf["district"].apply(lambda d: lookup_score(d, 0))
    gdf["intercept_pct_res"] = gdf["district"].apply(lambda d: lookup_score(d, 1))

    print("5. Distance to nearest transit station...")
    nodes = pd.read_csv(nodes_path)
    stations = gpd.GeoDataFrame(
        nodes[["Name"]],
        geometry=gpd.points_from_xy(nodes["Lon"], nodes["Lat"]),
        crs=4326,
    ).to_crs(epsg=UTM47N)
    near = gpd.sjoin_nearest(cent[["plot_id", "geometry"]], stations,
                             how="left", distance_col="dist_to_station_m")
    near = near.drop_duplicates("plot_id").set_index("plot_id")
    gdf["dist_to_station_m"] = gdf["plot_id"].map(near["dist_to_station_m"])
    gdf["nearest_station"] = gdf["plot_id"].map(near["Name"])

    print("6. Relating plots to the work<->home intercept surface...")
    surface = build_intercept_surface(res_path, work_path)
    if surface is not None and not surface.is_empty:
        gdf["in_intercept_surface"] = gdf.geometry.intersects(surface)
        gdf["dist_to_intercept_m"] = gdf.geometry.distance(surface)
    else:
        gdf["in_intercept_surface"] = False
        gdf["dist_to_intercept_m"] = float("nan")

    print("7. Scoring and ranking...")
    # Proximity: bounded decay, ~0.5 at 500 m from a station.
    prox = 1.0 / (1.0 + gdf["dist_to_station_m"].fillna(gdf["dist_to_station_m"].max()) / 500.0)
    interc = (gdf["intercept_score"] / 100.0).clip(0, 1)
    if gdf["dist_to_intercept_m"].notna().any():
        surf = 1.0 / (1.0 + gdf["dist_to_intercept_m"].fillna(1e9) / INTERCEPT_BUFFER_M)
    else:
        surf = pd.Series(0.0, index=gdf.index)
    conf = gdf["source_class"].isin(HIGH_CONF).map({True: CONF_HIGH, False: CONF_LOW})
    # Size: full credit inside the buildable band, decaying for oversize plots.
    size = gdf["area_sqm"].clip(upper=IDEAL_MAX_AREA_SQM) / gdf["area_sqm"].clip(lower=IDEAL_MAX_AREA_SQM)

    gdf["rank_score"] = (W_PROX * prox + W_INTERCEPT * interc + W_SURFACE * surf
                         + W_CONF * conf + W_SIZE * size)
    gdf = gdf.sort_values("rank_score", ascending=False).reset_index(drop=True)

    print("8. Writing outputs...")
    cols = ["plot_id", "district", "source_class", "area_sqm", "dist_to_station_m",
            "nearest_station", "intercept_score", "intercept_pct_res",
            "in_intercept_surface", "dist_to_intercept_m", "rank_score"]
    # GeoJSON in WGS84 with attributes.
    out = gdf[cols + ["geometry"]].to_crs(epsg=4326)
    out.to_file(out_geojson, driver="GeoJSON")
    gdf[cols].to_csv(out_csv, index=False)
    print(f"   - {out_geojson}\n   - {out_csv}")

    print("9. Rendering map...")
    fig, ax = plt.subplots(figsize=(15, 15))
    districts.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=0.5, alpha=0.4)
    plots_wgs = gdf.to_crs(epsg=4326)
    plots_wgs.plot(ax=ax, column="rank_score", cmap="viridis", markersize=6,
                   legend=True, alpha=0.8,
                   legend_kwds={"label": "Candidate plot rank_score", "shrink": 0.5})
    stations.to_crs(epsg=4326).plot(ax=ax, color="red", markersize=8, alpha=0.7)
    ax.set_title("Bangkok: candidate vacant/underused plots (OSM signals, ranked)\n"
                 "red = transit stations  |  CANDIDATES TO VERIFY, not confirmed vacant",
                 fontsize=16)
    plt.tight_layout()
    plt.savefig(out_map, dpi=200)
    print(f"   - {out_map}")

    # Console summary of the shortlist.
    print("\nTop 10 candidates:")
    show = ["plot_id", "district", "source_class", "area_sqm",
            "dist_to_station_m", "rank_score"]
    with pd.option_context("display.width", 160, "display.max_columns", 20):
        print(gdf[show].head(10).to_string(index=False))
    print("\nDone. Remember: verify the top plots against satellite imagery.")


if __name__ == "__main__":
    fetch_and_rank_plots()
