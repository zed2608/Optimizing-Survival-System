import pandas as pd
from pathlib import Path

def build_advanced_botanical_dictionary(output_path):
    print("==================================================")
    print(" BUILDING ADVANCED BOTANICAL CONSTRAINTS DICTIONARY")
    print("==================================================")
    
    # Augmented Dataset: LGU Policy Constraints + Scientific Biological Constraints
    tree_data = [
        {"species": "Narra", "type": "Native", "max_slope_percent": 30, "min_elev_m": 0, "max_elev_m": 1300, "drought_tolerance": "Medium", "shade_tolerance": "Low", "soil_pref": "Loam/Clay", "use_case": "Reforestation, watershed, parks"},
        {"species": "Molave", "type": "Native", "max_slope_percent": 60, "min_elev_m": 0, "max_elev_m": 700, "drought_tolerance": "High", "shade_tolerance": "Low", "soil_pref": "Limestone/Loam", "use_case": "Upland, slopes, watershed"},
        {"species": "Dao", "type": "Native", "max_slope_percent": 45, "min_elev_m": 0, "max_elev_m": 1000, "drought_tolerance": "Medium", "shade_tolerance": "Medium", "soil_pref": "Clay/Loam", "use_case": "Forest restoration, watershed"},
        {"species": "Banaba", "type": "Native", "max_slope_percent": 15, "min_elev_m": 0, "max_elev_m": 400, "drought_tolerance": "Low", "shade_tolerance": "Low", "soil_pref": "Clay/Loam", "use_case": "Roadsides, parks, open spaces"},
        {"species": "Bitaog", "type": "Native", "max_slope_percent": 20, "min_elev_m": 0, "max_elev_m": 500, "drought_tolerance": "High", "shade_tolerance": "Low", "soil_pref": "Sandy/Loam", "use_case": "Riparian/open areas"},
        {"species": "Kalumpit", "type": "Native", "max_slope_percent": 45, "min_elev_m": 0, "max_elev_m": 1000, "drought_tolerance": "Medium", "shade_tolerance": "Medium", "soil_pref": "Clay/Loam", "use_case": "Forest restoration, river/watershed"},
        {"species": "Duhat", "type": "Native", "max_slope_percent": 30, "min_elev_m": 0, "max_elev_m": 1200, "drought_tolerance": "High", "shade_tolerance": "Low", "soil_pref": "Any", "use_case": "Watershed, parks, agroforestry"},
        {"species": "Kamagong", "type": "Native", "max_slope_percent": 45, "min_elev_m": 0, "max_elev_m": 800, "drought_tolerance": "Medium", "shade_tolerance": "Medium", "soil_pref": "Loam/Clay", "use_case": "Biodiversity restoration"},
        {"species": "Katmon", "type": "Native", "max_slope_percent": 45, "min_elev_m": 0, "max_elev_m": 1000, "drought_tolerance": "Low", "shade_tolerance": "Medium", "soil_pref": "Loam", "use_case": "Forest restoration, biodiversity"},
        {"species": "Batikuling", "type": "Native", "max_slope_percent": 45, "min_elev_m": 0, "max_elev_m": 1000, "drought_tolerance": "Medium", "shade_tolerance": "Medium", "soil_pref": "Loam/Clay", "use_case": "Forest restoration"},
        {"species": "Palosapis", "type": "Native", "max_slope_percent": 45, "min_elev_m": 0, "max_elev_m": 1000, "drought_tolerance": "Medium", "shade_tolerance": "Low", "soil_pref": "Loam/Clay", "use_case": "Forest/watershed restoration"},
        {"species": "Talisay", "type": "Native", "max_slope_percent": 15, "min_elev_m": 0, "max_elev_m": 800, "drought_tolerance": "High", "shade_tolerance": "Low", "soil_pref": "Sandy/Loam", "use_case": "Parks, roadsides"},
        {"species": "Bamboo", "type": "Native", "max_slope_percent": 70, "min_elev_m": 0, "max_elev_m": 1500, "drought_tolerance": "High", "shade_tolerance": "Low", "soil_pref": "Any", "use_case": "Riverbanks, erosion control"},
        {"species": "Langka", "type": "Fruit tree", "max_slope_percent": 25, "min_elev_m": 0, "max_elev_m": 1000, "drought_tolerance": "Medium", "shade_tolerance": "Medium", "soil_pref": "Loam", "use_case": "Agroforestry/community planting"},
        {"species": "Guyabano", "type": "Fruit tree", "max_slope_percent": 25, "min_elev_m": 0, "max_elev_m": 1000, "drought_tolerance": "Low", "shade_tolerance": "Medium", "soil_pref": "Loam", "use_case": "Community/agroforestry"},
        {"species": "Atsuete", "type": "Native/introduced", "max_slope_percent": 25, "min_elev_m": 0, "max_elev_m": 800, "drought_tolerance": "Medium", "shade_tolerance": "Low", "soil_pref": "Loam/Clay", "use_case": "Agroforestry"},
        {"species": "Cacao", "type": "Cultivated", "max_slope_percent": 20, "min_elev_m": 0, "max_elev_m": 800, "drought_tolerance": "Low", "shade_tolerance": "High", "soil_pref": "Loam/Clay", "use_case": "Agroforestry"},
        {"species": "Rambutan", "type": "Fruit tree", "max_slope_percent": 20, "min_elev_m": 0, "max_elev_m": 600, "drought_tolerance": "Low", "shade_tolerance": "Medium", "soil_pref": "Loam/Clay", "use_case": "Agroforestry"},
        {"species": "Kasoy", "type": "Introduced/cultivated", "max_slope_percent": 25, "min_elev_m": 0, "max_elev_m": 800, "drought_tolerance": "High", "shade_tolerance": "Low", "soil_pref": "Sandy/Loam", "use_case": "Agroforestry"},
        {"species": "Sampalok", "type": "Cultivated", "max_slope_percent": 25, "min_elev_m": 0, "max_elev_m": 1500, "drought_tolerance": "High", "shade_tolerance": "Low", "soil_pref": "Any", "use_case": "Parks/agroforestry"}
    ]
    
    df = pd.DataFrame(tree_data)
    
    output_file = Path(output_path)
    df.to_csv(output_file, index=False)
    
    print(f" Successfully added biological constraints for {len(df)} LGU-approved species.")
    print(f" Saved augmented rule dictionary to: {output_file.resolve()}")
    print("==================================================")

if __name__ == "__main__":
    OUTPUT_CSV = "data/san_mateo_species_rules.csv"
    build_advanced_botanical_dictionary(OUTPUT_CSV)