import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import joblib
from pathlib import Path

def train_suitability_model():
    print("==================================================")
    print(" INITIALIZING RANDOM FOREST AI TRAINING")
    print("==================================================")
    
    # 1. Load the Biological Constraints
    rules_path = "data/san_mateo_species_rules.csv"
    try:
        rules_df = pd.read_csv(rules_path)
    except FileNotFoundError:
        print(f"[!] Could not find {rules_path}")
        return

    print(" -> Synthesizing historical training data from biological rules...")
    
    # 2. Generate Synthetic Training Data
    # We create 500 virtual planting scenarios for each species to teach the AI
    training_data = []
    
    for _, tree in rules_df.iterrows():
        for _ in range(500):
            # Generate optimal and edge-case environments based on the tree's limits
            simulated_slope = np.random.uniform(0, tree['max_slope_percent'])
            simulated_elev = np.random.uniform(tree['min_elev_m'], tree['max_elev_m'])
            
            # Convert categorical rules into numerical ML weights
            soil_weight = 1 if "Any" in tree['soil_pref'] else 2
            drought_weight = 3 if tree['drought_tolerance'] == "High" else (2 if tree['drought_tolerance'] == "Medium" else 1)
            shade_weight = 3 if tree['shade_tolerance'] == "High" else (2 if tree['shade_tolerance'] == "Medium" else 1)
            
            training_data.append({
                'slope_percentage': simulated_slope,
                'elevation_m': simulated_elev,
                'soil_compatibility': soil_weight,
                'drought_survival': drought_weight,
                'shade_survival': shade_weight,
                'target_species': tree['species']
            })

    train_df = pd.DataFrame(training_data)
    
    # 3. Prepare Features (X) and Target (y)
    X = train_df[['slope_percentage', 'elevation_m', 'soil_compatibility', 'drought_survival', 'shade_survival']]
    y = train_df['target_species']
    
    # Encode the tree names into numbers for the AI
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)
    
    print(f" -> Training Random Forest on {len(train_df):,} simulated environments...")
    
    # 4. Train the Random Forest Algorithm
    # 100 decision trees voting on the best outcome
    rf_model = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=10)
    rf_model.fit(X, y_encoded)
    
    # 5. Export the Trained Model and Encoder
    joblib.dump(rf_model, 'data/rf_suitability_model.pkl')
    joblib.dump(le, 'data/rf_label_encoder.pkl')
    
    print("==================================================")
    print(" MODEL TRAINING COMPLETE & SAVED")
    print(" -> rf_suitability_model.pkl (The Brain)")
    print(" -> rf_label_encoder.pkl (The Translator)")
    print("==================================================")

if __name__ == "__main__":
    train_suitability_model()