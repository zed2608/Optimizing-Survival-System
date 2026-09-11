import pandas as pd

def run_advanced_suitability_engine(env_csv, rules_csv, output_csv):
    print("==================================================")
    print(" INITIALIZING ADVANCED SUITABILITY ENGINE")
    print("==================================================")
    
    try:
        env_df = pd.read_csv(env_csv)
        rules_df = pd.read_csv(rules_csv)
        print(f" Loaded {len(env_df):,} planting sites.")
        print(f" Loaded {len(rules_df)} LGU species rules.")
    except FileNotFoundError as e:
        print(f"[!] Error finding data: {e}")
        return

    print("\n Running multi-factor biological cross-referencing...")

    # OPTIMIZATION: Convert DataFrame to a list of dictionaries ONCE
    # This stops Python from recalculating data types 340,000 times!
    rules_list = rules_df.to_dict('records')

    def find_suitable_trees(row):
        plot_slope = row['slope_percentage']
        plot_elev = row['elevation_m']
        
        suitable = []
        for tree in rules_list:
            # Constraint 1: Slope
            if plot_slope > tree['max_slope_percent']:
                continue
                
            # Constraint 2: Elevation
            if plot_elev < tree['min_elev_m'] or plot_elev > tree['max_elev_m']:
                continue
            
            suitable.append(tree['species'])
        
        if not suitable:
            return "No Suitable Species - Extreme Hazard Zone"
        
        return ", ".join(suitable)

    # Apply the optimized engine
    env_df['suitable_species'] = env_df.apply(find_suitable_trees, axis=1)
    
    env_df['species_option_count'] = env_df['suitable_species'].apply(
        lambda x: 0 if "No Suitable Species" in x else len(x.split(", "))
    )

    env_df.to_csv(output_csv, index=False)
    
    print("==================================================")
    print(" ADVANCED SUITABILITY MATCHING COMPLETE")
    print(f" Evaluated {len(env_df):,} coordinates against multi-factor constraints.")
    print(f" Results mapped and saved to: {output_csv}")
    print("==================================================")

if __name__ == "__main__":
    ENVIRONMENTAL_DATA = "data/san_mateo_farmland_environmental.csv"
    SPECIES_RULES = "data/san_mateo_species_rules.csv"
    FINAL_MAPPED_DATA = "data/san_mateo_final_recommendations.csv"
    
    run_advanced_suitability_engine(ENVIRONMENTAL_DATA, SPECIES_RULES, FINAL_MAPPED_DATA)