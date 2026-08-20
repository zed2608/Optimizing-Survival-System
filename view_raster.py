import rasterio
from rasterio.plot import show
from rasterio.enums import Resampling
import matplotlib.pyplot as plt
from pathlib import Path

# 1. Define the cross-platform path
data_folder = Path("data")
raster_path = data_folder / "SAN MATEO WGS TIFF.tif"

if not raster_path.exists():
    print(f"Error: Could not find the file at {raster_path}")
else:
    print(f"Loading Metadata from: {raster_path}...")
    
    with rasterio.open(raster_path) as dataset:
        print(f"Original Size: {dataset.width} x {dataset.height} pixels")
        
        # 2. Set a scaling factor to shrink the massive 4GB image
        # A factor of 10 means the image will be 1/10th the size (saving massive RAM)
        scale_factor = 10 
        
        print(f"Downsampling map by a factor of {scale_factor} for safe viewing...")
        
        # 3. Read the data at a lower resolution
        thumbnail = dataset.read(
            out_shape=(
                dataset.count,
                int(dataset.height / scale_factor),
                int(dataset.width / scale_factor)
            ),
            resampling=Resampling.bilinear
        )
        
        # 4. Plot the smaller, safe-to-view image
        fig, ax = plt.subplots(figsize=(10, 10))
        show(thumbnail, ax=ax, title="San Mateo GeoTIFF (Downsampled)")
        
        print("Success! Displaying map window.")
        plt.show()