import pandas as pd
import geopandas as gpd
import osmnx as ox
from shapely.geometry import Point

def enforce_lgu_boundaries(input_csv, output_csv):
    print("==================================================")
    print(" INITIATING POINT-IN-POLYGON BOUNDARY CLIPPING")
    print("==================================================")
    
    # 1. Fetch the exact geometric boundary of San Mateo
    print(" -> Downloading official San Mateo polygon from OpenStreetMap...")
    try:
        san_mateo_polygon = ox.geocode_to_gdf("San Mateo, Rizal, Philippines")
    except Exception as e:
        print(f"[!] Error fetching boundary: {e}")
        return

    # 2. Load your current predicted dataset
    print(" -> Loading coordinate dataset...")
    df = pd.read_csv(input_csv)
    original_count = len(df)
    
    # 3. Convert standard Pandas DataFrame into a Spatial GeoDataFrame
    geometry = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
    gdf_points = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
    
    # 4. The Intersect: Keep ONLY points that fall mathematically inside the polygon
    print(" -> Executing spatial intersect...")
    clipped_gdf = gpd.sjoin(gdf_points, san_mateo_polygon, predicate='within')
    
    # 5. Clean up the dataframe and save it, overwriting the old file
    columns_to_drop = [col for col in clipped_gdf.columns if col not in df.columns]
    final_df = pd.DataFrame(clipped_gdf.drop(columns=columns_to_drop))
    
    final_df.to_csv(output_csv, index=False)
    
    print("==================================================")
    print(" BOUNDARY ENFORCEMENT COMPLETE")
    print(f" Original Points: {original_count:,}")
    print(f" Points Inside LGU: {len(final_df):,}")
    print(f" Deleted Spillover: {original_count - len(final_df):,} points removed.")
    print("==================================================")

if __name__ == "__main__":
    TARGET_CSV = "data/san_mateo_final_recommendations.csv"
    enforce_lgu_boundaries(TARGET_CSV, TARGET_CSV)