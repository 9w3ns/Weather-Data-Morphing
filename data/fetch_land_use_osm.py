import osmnx as ox
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

def fetch_and_map_zones():
    # Setup paths
    districts_path = "data/gis/bangkok_districts.geojson"
    out_map_path = "docs/bangkok_zoning_map.png"
    out_res_path = "data/gis/bangkok_residential_zones.geojson"
    out_work_path = "data/gis/bangkok_working_zones.geojson"
    out_score_path = "data/gis/bangkok_intercept_scores.csv"

    # Configure OSMnx
    ox.settings.timeout = 1800
    ox.settings.use_cache = True

    print("1. Loading Bangkok districts...")
    districts = gpd.read_file(districts_path)

    print("2. Fetching Residential Zones from OSM...")
    tags_res = {'landuse': 'residential'}
    try:
        res_gdf = ox.features_from_place('Bangkok, Thailand', tags=tags_res)
        # Keep only polygons/multipolygons
        res_gdf = res_gdf[res_gdf.geom_type.isin(['Polygon', 'MultiPolygon'])]
        # Ensure CRS is projected for accurate area/buffer calculations (EPSG:32647 for UTM 47N / Bangkok)
        res_gdf_proj = res_gdf.to_crs(epsg=32647)
    except Exception as e:
        print(f"Error fetching residential: {e}")
        res_gdf = gpd.GeoDataFrame()
        res_gdf_proj = gpd.GeoDataFrame()
        
    print("3. Fetching Working Zones from OSM...")
    tags_work = {'landuse': ['commercial', 'retail', 'industrial'], 'building': 'office'}
    try:
        work_gdf = ox.features_from_place('Bangkok, Thailand', tags=tags_work)
        work_gdf = work_gdf[work_gdf.geom_type.isin(['Polygon', 'MultiPolygon'])]
        work_gdf_proj = work_gdf.to_crs(epsg=32647)
    except Exception as e:
        print(f"Error fetching working zones: {e}")
        work_gdf = gpd.GeoDataFrame()
        work_gdf_proj = gpd.GeoDataFrame()

    print("4. Calculating Boundary Intercept Scores per District...")
    districts_proj = districts.to_crs(epsg=32647)
    
    scores = []

    # If we successfully fetched both datasets
    if not res_gdf_proj.empty and not work_gdf_proj.empty:
        # OSM landuse polygons overlap and duplicate each other, so summing the
        # area of individual polygons double-counts overlaps (that is what pushed
        # some districts past a physically-impossible 100%). Dissolve each layer
        # into a single geometry FIRST, then all area math is on non-overlapping
        # surfaces and the score is bounded to [0, 100].
        print("   - Dissolving working zones and buffering by 200m...")
        # Buffer working zones by 200m to define the "intercept threshold",
        # then dissolve the buffers into one geometry.
        work_buffer = work_gdf_proj.geometry.buffer(200).union_all()

        print("   - Dissolving residential zones and intersecting...")
        res_union = res_gdf_proj.geometry.union_all()
        # Residential fabric lying within 200m of any working zone == the
        # commute-intercept surface. Single dissolved geometry, no double count.
        intercept_union = res_union.intersection(work_buffer)

        print("   - Calculating scores per district...")
        for idx, district in districts_proj.iterrows():
            d_name = district['District']
            d_geom = district.geometry

            # Area of district
            d_area = d_geom.area

            # Clip the dissolved intercept surface to this district. Because both
            # sides are single (non-self-overlapping) geometries, the clipped
            # area can never exceed the district area.
            intercept_area = intercept_union.intersection(d_geom).area
            # Residential surface inside the district (for context / an alternate
            # normalisation) -- also dissolved, so no double counting.
            res_area = res_union.intersection(d_geom).area

            # Score is the percentage of district area that acts as an intercept zone
            score = (intercept_area / d_area) * 100 if d_area else 0.0
            # Share of the district's residential fabric that is intercept-adjacent.
            res_intercept_pct = (intercept_area / res_area) * 100 if res_area else 0.0

            scores.append({
                'District': d_name,
                'Intercept_Area_sqm': intercept_area,
                'Residential_Area_sqm': res_area,
                'District_Area_sqm': d_area,
                'Intercept_Score_Pct': score,
                'Intercept_Pct_of_Residential': res_intercept_pct
            })

        scores_df = pd.DataFrame(scores)
        scores_df = scores_df.sort_values('Intercept_Score_Pct', ascending=False)
        scores_df.to_csv(out_score_path, index=False)
        print(f"Saved scores to {out_score_path}")
    
    print("5. Generating Map...")
    fig, ax = plt.subplots(figsize=(15, 15))
    
    # Plot districts outline
    districts.plot(ax=ax, facecolor='none', edgecolor='black', linewidth=0.5, alpha=0.5)
    
    if not res_gdf.empty:
        # Save for GH
        res_gdf.to_crs(epsg=4326).reset_index(drop=True)[['geometry']].to_file(out_res_path, driver='GeoJSON')
        res_gdf.plot(ax=ax, color='orange', alpha=0.5, label='Residential')
    
    if not work_gdf.empty:
        # Save for GH
        work_gdf.to_crs(epsg=4326).reset_index(drop=True)[['geometry']].to_file(out_work_path, driver='GeoJSON')
        work_gdf.plot(ax=ax, color='red', alpha=0.7, label='Working/Commercial')
        
    # Custom legend
    import matplotlib.patches as mpatches
    res_patch = mpatches.Patch(color='orange', alpha=0.5, label='Residential')
    work_patch = mpatches.Patch(color='red', alpha=0.7, label='Working/Commercial')
    plt.legend(handles=[res_patch, work_patch], loc='upper right', fontsize=12)
    
    ax.set_title("Bangkok: Residential vs. Working Zones (OSM Data)", fontsize=20)
    plt.tight_layout()
    plt.savefig(out_map_path, dpi=300)
    print(f"Saved map to {out_map_path}")
    
    print("Done!")

if __name__ == "__main__":
    fetch_and_map_zones()
