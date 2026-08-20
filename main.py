from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # <-- This is the line that was missing
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import Point
from scipy.optimize import linear_sum_assignment
from pathlib import Path
import random

# Initialize the FastAPI "Waiter"
app = FastAPI(title="San Mateo Spatial Optimization API")

# Configure CORS so React can talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)

@app.get("/api/optimize-planting")
def get_optimized_planting_sites():
    """
    This endpoint runs the bipartite matching and returns the coordinates 
    as JSON data for the React frontend.
    """
    # 1. Load Data
    data_folder = Path("data")
    supply_df = pd.read_csv(data_folder / "mock_tree_inventory.csv").head(50)
    
    gdf = gpd.read_file(data_folder / "LandUses.shp")
    valid_zones = ['Parks and Recreation Zone', 'Buffer Zone', 'Forest Zone', 'Medium Density Residential Zone']
    valid_areas = gdf[gdf['DESCRIPTIO'].isin(valid_zones)]
    
    # 2. Generate Demand Points
    minx, miny, maxx, maxy = valid_areas.total_bounds
    points = []
    while len(points) < 50:
        p = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
        for idx, row in valid_areas.iterrows():
            if p.within(row['geometry']):
                points.append({'geometry': p, 'actual_zone': row['DESCRIPTIO']})
                break
    demand_df = gpd.GeoDataFrame(points, crs=valid_areas.crs)
    nursery_location = Point(valid_areas.union_all().centroid.x, valid_areas.union_all().centroid.y)

    # 3. Calculate Cost Matrix
    num_trees = len(supply_df)
    num_plots = len(demand_df)
    cost_matrix = np.zeros((num_trees, num_plots))

    for i, tree in supply_df.iterrows():
        for j, plot in demand_df.iterrows():
            distance_cost = nursery_location.distance(plot['geometry']) * 1000
            mismatch_penalty = 0 if tree['preferred_zone'] == plot['actual_zone'] else 5000
            cost_matrix[i, j] = distance_cost + mismatch_penalty

    # 4. Execute Hungarian Algorithm
    tree_indices, plot_indices = linear_sum_assignment(cost_matrix)

    # 5. Package the Results into JSON format
    results = []
    for idx in range(len(tree_indices)):
        t_idx = tree_indices[idx]
        p_idx = plot_indices[idx]
        
        results.append({
            "sapling_id": supply_df.iloc[t_idx]['sapling_id'],
            "species": supply_df.iloc[t_idx]['species'],
            "target_zone": demand_df.iloc[p_idx]['actual_zone'],
            "longitude": demand_df.iloc[p_idx]['geometry'].x,
            "latitude": demand_df.iloc[p_idx]['geometry'].y
        })

    return {"status": "success", "total_matches": len(results), "data": results}