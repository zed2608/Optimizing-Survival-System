import pandas as pd
import rasterio
from pyproj import Transformer
from pathlib import Path

def build_master_environment():
    print("==================================================")
    print(" STARTING MASTER ENVIRONMENTAL PIPELINE")
    print("==================================================")
    
    # 1. Load the clean, original coordinates
    df = pd.read_csv("data/san_mateo_farmland_coordinates.csv")
    coords_latlon = [(x, y) for x, y in zip(df['longitude'], df['latitude'])]
    
    # 2. Extract Elevation (NASA Map uses Lat/Lon)
    print(" -> Extracting Elevation (Meters)...")
    with rasterio.open(r"C:\Users\user\Downloads\n14_e121_1arc_v3.tif") as src:
        df['elevation_m'] = [val[0] for val in src.sample(coords_latlon)]

    # 3. Extract Slope (QGIS Map uses UTM Meters)
    print(" -> Translating GPS to UTM and Extracting Slope (%)...")
    # This translates Lat/Lon to UTM Zone 51N
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32651", always_xy=True)
    coords_utm = [transformer.transform(x, y) for x, y in coords_latlon]
    
    with rasterio.open(r"C:\Users\user\Downloads\san_mateo_slope.tif") as src:
        df['slope_percentage'] = [val[0] for val in src.sample(coords_utm)]

    # 4. Extract Soil (FAO Map uses Lat/Lon)
    print(" -> Extracting Soil Classification...")
    with rasterio.open(r"C:\Users\user\Downloads\HWSD2_Raster\HWSD2.bil") as src:
        df['soil_type_id'] = [val[0] for val in src.sample(coords_latlon)]

    # Save the fresh, corrected environmental dataset
    output_path = Path("data/san_mateo_farmland_environmental.csv")
    df.to_csv(output_path, index=False)
    
    print("==================================================")
    print(" PIPELINE COMPLETE: Dataset is clean and ready.")
    print("==================================================")

if __name__ == "__main__":
    build_master_environment()