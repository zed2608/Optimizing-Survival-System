import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import Point
from scipy.optimize import linear_sum_assignment
from pathlib import Path
import random

# 1. Load the Tree Supply (Set U)
# We will take a small sample of 50 trees for this rapid test
data_folder = Path("data")
supply_df = pd.read_csv(data_folder / "mock_tree_inventory.csv").head(50)

# 2. Re-generate a matching Demand (Set V)
# We need exactly 50 valid planting points
gdf = gpd.read_file(data_folder / "LandUses.shp")
valid_zones = ['Parks and Recreation Zone', 'Buffer Zone', 'Forest Zone', 'Medium Density Residential Zone']
valid_areas = gdf[gdf['DESCRIPTIO'].isin(valid_zones)]

minx, miny, maxx, maxy = valid_areas.total_bounds
points = []
while len(points) < 50:
    p = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
    # Check if the point falls inside a valid zone, and record the zone name
    for idx, row in valid_areas.iterrows():
        if p.within(row['geometry']):
            points.append({'geometry': p, 'actual_zone': row['DESCRIPTIO']})
            break

demand_df = gpd.GeoDataFrame(points, crs=valid_areas.crs)

# Define a hypothetical Central Nursery coordinate (using the center of the map)
nursery_location = Point(valid_areas.unary_union.centroid.x, valid_areas.unary_union.centroid.y)

# 3. Build the Cost Matrix
print("Calculating Hybrid Optimization Cost Matrix...")
num_trees = len(supply_df)
num_plots = len(demand_df)
cost_matrix = np.zeros((num_trees, num_plots))

for i, tree in supply_df.iterrows():
    for j, plot in demand_df.iterrows():
        # A. Logistical Cost: Distance from nursery to the plot
        distance_cost = nursery_location.distance(plot['geometry']) * 1000 # scaling factor
        
        # B. Ecological Cost: Penalty if zones don't match
        if tree['preferred_zone'] == plot['actual_zone']:
            mismatch_penalty = 0     # Perfect ecological match
        else:
            mismatch_penalty = 5000  # Massive penalty to discourage this pairing
            
        # Hybrid Cost Calculation
        cost_matrix[i, j] = distance_cost + mismatch_penalty

# 4. Execute the Hungarian Algorithm (Weighted Bipartite Matching)
print("Executing Hungarian Algorithm...")
tree_indices, plot_indices = linear_sum_assignment(cost_matrix)

# 5. Display the Results
print("\n--- OPTIMIZATION RESULTS (Top 5 Matches) ---")
total_cost = 0
for idx in range(5):
    t_idx = tree_indices[idx]
    p_idx = plot_indices[idx]
    
    sapling_id = supply_df.iloc[t_idx]['sapling_id']
    species = supply_df.iloc[t_idx]['species']
    pref_zone = supply_df.iloc[t_idx]['preferred_zone']
    actual_zone = demand_df.iloc[p_idx]['actual_zone']
    match_cost = cost_matrix[t_idx, p_idx]
    total_cost += match_cost
    
    print(f"Match {idx+1}: {sapling_id} ({species}) -> Assigned to: {actual_zone}")
    print(f"   [Preferred: {pref_zone} | Match Cost: {match_cost:.2f}]")

print(f"\nOptimization complete. Total Cost Score for all 50 matches: {cost_matrix[tree_indices, plot_indices].sum():.2f}")