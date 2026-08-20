import geopandas as gpd
import matplotlib.pyplot as plt
from pathlib import Path

# 1. Define paths based EXACTLY on your VS Code folder structure
data_folder = Path("data")
land_use_path = data_folder / "LandUses.shp"
water_path = data_folder / "SMR_WATERBODIES_POLY.shp"

if not land_use_path.exists() or not water_path.exists():
    print("Error: Please ensure both shapefiles are in the data folder.")
else:
    print("Loading Land Use constraints...")
    land_use_gdf = gpd.read_file(land_use_path)
    
    print("Loading Waterbodies constraints...")
    water_gdf = gpd.read_file(water_path)
    
    # Let's print the columns of the Land Use file to see the zoning categories
    print("\nLand Use Data Columns:")
    print(land_use_gdf.columns.tolist())
    
    # 2. Create the visual canvas
    print("\nRendering stacked map...")
    fig, ax = plt.subplots(figsize=(12, 12))
    
    # 3. Plot Layer 1: Land Use (Base layer)
    # We use a light grey color with dark borders for the zoning blocks
    land_use_gdf.plot(ax=ax, color='lightgrey', edgecolor='dimgrey', alpha=0.8)
    
    # 4. Plot Layer 2: River Networks (Overlay)
    # We plot the water bodies on top in bright blue
    water_gdf.plot(ax=ax, color='dodgerblue')
    
    plt.title("San Mateo Constraints: Land Use & Waterbodies")
    plt.show()