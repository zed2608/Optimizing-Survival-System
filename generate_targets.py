import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point
import numpy as np
from pathlib import Path

# 1. Load the Land Use data and filter for valid zones (same as before)
data_folder = Path("data")
gdf = gpd.read_file(data_folder / "LandUses.shp")

valid_zones = [
    'Parks and Recreation Zone', 'Buffer Zone', 'General Institutional Zone',
    'Institutional Research Zone', 'Forest Zone', 'General Institutional Zonec',
    'Medium Density Residential Zone', 'High Density Residential - Mixed Use Zone',
    'Socialized Housing Zone', 'Agricultural Zone', 'Cemetery Zone'
]
valid_areas = gdf[gdf['DESCRIPTIO'].isin(valid_zones)]

# 2. Determine the bounding box of the valid areas
minx, miny, maxx, maxy = valid_areas.total_bounds

# 3. Create a grid of points (0.002 degrees is roughly 200 meters apart)
print("Generating candidate planting grid...")
spacing = 0.002
x_coords = np.arange(minx, maxx, spacing)
y_coords = np.arange(miny, maxy, spacing)

# Create Shapely Point objects
grid_points = [Point(x, y) for x in x_coords for y in y_coords]
grid_gdf = gpd.GeoDataFrame(geometry=grid_points, crs=valid_areas.crs)

# 4. The Magic Step: Keep ONLY the points that fall inside the valid green zones
print("Filtering points to ensure legal compliance...")
target_plot_points = gpd.sjoin(grid_gdf, valid_areas, predicate='within')

print(f"Success! Generated {len(target_plot_points)} legal target planting points.")

# 5. Plot the result
fig, ax = plt.subplots(figsize=(12, 12))
valid_areas.plot(ax=ax, color='mediumseagreen', alpha=0.5)
target_plot_points.plot(ax=ax, color='black', markersize=2, label="Target Plot Points (Set V)")

plt.title("San Mateo: Candidate Target Plot Points")
plt.legend()
plt.show()