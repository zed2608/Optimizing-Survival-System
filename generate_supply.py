import pandas as pd
import numpy as np
import random
from pathlib import Path

# 1. Define standard native species suitable for urban greening and forestry
species_list = ['Narra', 'Molave', 'Banaba', 'Ilang-Ilang', 'Mahogany']

# 2. Generate a mock inventory of 1,000 saplings
num_saplings = 1000
print(f"Generating mock inventory of {num_saplings} saplings...")

data = {
    'sapling_id': [f"SAP-{str(i).zfill(4)}" for i in range(1, num_saplings + 1)],
    'species': [random.choice(species_list) for _ in range(num_saplings)],
    # Simulate an attribute that will affect the matching weight (e.g., drought tolerance)
    'drought_tolerance': [random.choice(['High', 'Medium', 'Low']) for _ in range(num_saplings)],
    # Simulate which zoning category this specific tree thrives best in
    'preferred_zone': [random.choice([
        'Parks and Recreation Zone', 
        'Forest Zone', 
        'Buffer Zone', 
        'Medium Density Residential Zone'
    ]) for _ in range(num_saplings)]
}

supply_df = pd.DataFrame(data)

# 3. Save the inventory to a CSV file in your data folder
data_folder = Path("data")
output_path = data_folder / "mock_tree_inventory.csv"

supply_df.to_csv(output_path, index=False)

print(f"Success! Mock tree inventory saved to {output_path}")
print("\nSample of the generated supply:")
print(supply_df.head())