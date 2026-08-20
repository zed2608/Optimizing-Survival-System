import geopandas as gpd
from pathlib import Path

# 1. Define the path to the Land Use file
data_folder = Path("data")
land_use_path = data_folder / "LandUses.shp"

print("Reading Land Use data...")
land_use_gdf = gpd.read_file(land_use_path)

# 2. Extract and print all unique zoning categories found in the shapefile
print("\n--- San Mateo Zoning Categories ---")
unique_zones = land_use_gdf['DESCRIPTIO'].unique()

for zone in unique_zones:
    print(f"- {zone}")