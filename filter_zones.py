import geopandas as gpd
import matplotlib.pyplot as plt
from pathlib import Path

# 1. Define the path to your Land Use shapefile
data_folder = Path("data")
land_use_path = data_folder / "LandUses.shp"

print("Loading Land Use data...")
gdf = gpd.read_file(land_use_path)

# 2. Define the exact valid zones (Green and Yellow Lights)
# Notice we included 'General Institutional Zonec' to account for the LGU's typo
valid_zones = [
    'Parks and Recreation Zone',
    'Buffer Zone',
    'General Institutional Zone',
    'Institutional Research Zone',
    'Forest Zone',
    'General Institutional Zonec',
    'Medium Density Residential Zone',
    'High Density Residential - Mixed Use Zone',
    'Socialized Housing Zone',
    'Agricultural Zone',
    'Cemetery Zone'
]

# 3. Mathematically filter out the Red Light exclusion zones
print("Applying spatial constraints... removing restricted zones.")
valid_planting_areas = gdf[gdf['DESCRIPTIO'].isin(valid_zones)]

# 4. Create the visual canvas
print("Rendering optimized planting canvas...")
fig, ax = plt.subplots(figsize=(12, 12))

# Plot only the legally permitted areas in a rich green color
valid_planting_areas.plot(ax=ax, color='mediumseagreen', edgecolor='darkgreen', alpha=0.8)

plt.title("San Mateo: Legally Permitted Planting Zones")
plt.show()