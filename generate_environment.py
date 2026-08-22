import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import Point
from pathlib import Path
import random

def generate_environmental_grid(num_sites=100):
    print("Initializing GIS simulation for San Mateo...")
    
    # 1. Setup Data Paths
    data_folder = Path("data")
    data_folder.mkdir(exist_ok=True)
    
    # 2. Load Valid Zones from Shapefile
    try:
        gdf = gpd.read_file(data_folder / "LandUses.shp")
        valid_zones = ['Parks and Recreation Zone', 'Buffer Zone', 'Forest Zone', 'Medium Density Residential Zone']
        valid_areas = gdf[gdf['DESCRIPTIO'].isin(valid_zones)]
    except Exception as e:
        print(f"Error loading Shapefile: {e}. Please ensure LandUses.shp is in the /data folder.")
        return

    # 3. Generate Target Coordinates
    print("Generating random target coordinates within valid CLUP zones...")
    minx, miny, maxx, maxy = valid_areas.total_bounds
    points = []
    
    while len(points) < num_sites:
        p = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
        for idx, row in valid_areas.iterrows():
            if p.within(row['geometry']):
                points.append({
                    'site_id': f"SITE-{len(points)+1:04d}",
                    'longitude': p.x,
                    'latitude': p.y,
                    'actual_zone': row['DESCRIPTIO']
                })
                break

    # 4. Inject Environmental Variables
    print("Simulating environmental and topological data...")
    df = pd.DataFrame(points)
    
    soil_types = ['Clay Loam', 'Sandy Loam', 'Silty Clay', 'Loam']
    df['soil_type'] = np.random.choice(soil_types, size=num_sites, p=[0.4, 0.3, 0.2, 0.1])
    
    df['slope_percentage'] = np.round(np.random.uniform(0.0, 35.0, size=num_sites), 2)
    
    hazard_levels = ['Low', 'Moderate', 'High']
    df['landslide_hazard'] = np.where(
        df['actual_zone'] == 'Forest Zone',
        np.random.choice(hazard_levels, size=num_sites, p=[0.2, 0.5, 0.3]),
        np.random.choice(hazard_levels, size=num_sites, p=[0.7, 0.2, 0.1])
    )
    
    # 5. Export to CSV
    output_path = data_folder / "mock_environmental_grid.csv"
    df.to_csv(output_path, index=False)
    
    print(f"Success! Generated {num_sites} environmentally-tagged sites.")
    print(f"Data saved to: {output_path}")

if __name__ == "__main__":
    generate_environmental_grid()