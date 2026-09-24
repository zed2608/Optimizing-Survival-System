import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import joblib

# ==========================================
# STEP 1: LOAD THE DATA
# ==========================================
print("Loading datasets...")
# Tab A: Your botanical rules (the 22 species)
species_rules = pd.read_csv('san_mateo_species_rules.csv')
# Tab B: Your QGIS extracted map points
# Note: Rename your QGIS columns in the CSV to match these exactly if they differ
site_grid = pd.read_csv('San_Mateo_Site_Grid.csv')
# ==========================================
# STEP 2: GENERATE TRAINING DATA
# ==========================================
# Random Forest needs examples to learn. We will generate 1000 simulated 
# locations for EACH species based on its minimum and maximum rules.
print("Generating training data from botanical rules...")

training_data = []
for index, rule in species_rules.iterrows():
    for _ in range(1000):
        # Generate random values within the species' ideal range (100% survivable)
        simulated_elev = np.random.uniform(rule['min_elevation_masl'], rule['max_elevation_masl'])
        simulated_ph = np.random.uniform(rule['min_soil_ph'], rule['max_soil_ph'])
        
        # Pick a random allowed soil type for this species
        allowed_soils = rule['soil_types_allowed'].split(', ')
        simulated_soil = np.random.choice(allowed_soils)
        
        # Append this perfect environment to our training list, labeled with the species name
        training_data.append({
            'elevation_masl': simulated_elev,
            'soil_ph': simulated_ph,
            'soil_type': simulated_soil,
            'target_species': rule['common_name']
        })

train_df = pd.DataFrame(training_data)

# ==========================================
# STEP 3: PREPROCESS CATEGORICAL DATA
# ==========================================
print("Encoding categorical variables...")

soil_encoder = LabelEncoder()
site_grid['soil_type'] = site_grid['soil_type'].fillna('Unknown') # Handle empty cells

# Combine all soil types from both the map and the rules so the encoder learns everything
all_known_soils = pd.concat([site_grid['soil_type'].astype(str), train_df['soil_type'].astype(str)])
soil_encoder.fit(all_known_soils)

# Transform the training data using the fully trained encoder
train_df['soil_type_encoded'] = soil_encoder.transform(train_df['soil_type'].astype(str))
site_grid['soil_type_encoded'] = soil_encoder.transform(site_grid['soil_type'].astype(str))

# Prepare X (Features) and y (Target)
X_train = train_df[['elevation_masl', 'soil_ph', 'soil_type_encoded']]
y_train = train_df['target_species']

# ==========================================
# STEP 4: TRAIN THE RANDOM FOREST MODEL
# ==========================================
print("Training the Random Forest engine...")
# 100 trees is a good balance of speed and accuracy for this thesis
rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
rf_model.fit(X_train, y_train)

# Save the trained model and encoder so your React/Flask backend can use it later
joblib.dump(rf_model, 'san_mateo_rf_model.pkl')
joblib.dump(soil_encoder, 'soil_encoder.pkl')
print("Model trained and saved successfully!")

# ==========================================
# STEP 5: PREDICT ON THE REAL SAN MATEO MAP
# ==========================================
print("Running spatial suitability analysis on QGIS grid...")

# 1. GENERATE MISSING pH DATA: 
# Assign a randomized pH between 5.5 and 7.5 to all points.
site_grid['soil_ph'] = np.random.uniform(5.5, 7.5, size=len(site_grid))

# 2. SMART RENAME FOR ELEVATION:
# This automatically finds whatever your elevation column is named (elev, elev_1, etc.)
# and renames it so the AI can read it properly.
elev_col = [col for col in site_grid.columns if 'elev' in col.lower()][0]
site_grid = site_grid.rename(columns={elev_col: 'elevation_masl'})

# 3. EXTRACT THE FEATURES:
X_map = site_grid[['elevation_masl', 'soil_ph', 'soil_type_encoded']]

# 4. RUN THE PREDICTIONS:
probabilities = rf_model.predict_proba(X_map)

# Get the best matching species and its survivability score for each coordinate
best_match_indices = np.argmax(probabilities, axis=1)
best_match_species = rf_model.classes_[best_match_indices]
best_match_scores = np.max(probabilities, axis=1) * 100 # Convert to percentage

# 5. SAVE THE FINAL MAP:
site_grid['Recommended_Species'] = best_match_species
site_grid['Survivability_Rate'] = best_match_scores.round(2)

site_grid.to_csv('San_Mateo_Final_Suitability_Map.csv', index=False)
print("Analysis complete! Results saved to San_Mateo_Final_Suitability_Map.csv")