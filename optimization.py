import numpy as np
import joblib
from scipy.optimize import linear_sum_assignment
from math import radians, cos, sin, asin, sqrt

# 1. Load the trained Random Forest AI model and Label Encoder
rf_model = joblib.load('data/rf_suitability_model.pkl')
label_encoder = joblib.load('data/rf_label_encoder.pkl')

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates the distance in meters between two GPS coordinates."""
    R = 6371000  # Earth radius in meters
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    a = sin(dLat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2)**2
    return 2 * R * asin(sqrt(a))

def get_rf_probability(species_name: str, location_dict: dict) -> float:
    """
    Uses the trained Random Forest model to predict the suitability probability 
    of a specific tree species for a given coordinate's environmental traits.
    """
    # Check if the requested species exists in the model's training labels
    species_classes = list(label_encoder.classes_)
    if species_name not in species_classes:
        return 0.0
    
    species_idx = species_classes.index(species_name)

    # Features expected by your trained model:
    # [slope_percentage, elevation_m, soil_compatibility, drought, shade]
    elevation = float(location_dict.get('elevation', 50.0))
    slope = float(location_dict.get('slope_percentage', 5.0))
    
    features = [[
        slope,
        elevation,
        2,  # Standard soil baseline
        2,  # Medium drought baseline
        2   # Medium shade baseline
    ]]

    # Compute probability distribution across all species classes
    probabilities = rf_model.predict_proba(features)[0]
    return float(probabilities[species_idx])

def optimize_planting_layout(candidate_species, target_locations, baseline_trees):
    """
    Executes Weighted Bipartite Matching while enforcing:
    1. 5-meter exclusion zones around baseline trees
    2. 50% Random Forest survival probability threshold
    """
    valid_locations = []
    
    # 1. Enforce the 5-meter Exclusion Zone Constraint
    for loc in target_locations:
        collision = False
        for tree in baseline_trees:
            dist = haversine_distance(loc['lat'], loc['lon'], tree['lat'], tree['lon'])
            if dist < 5.0:
                collision = True
                break
        if not collision:
            valid_locations.append(loc)

    # Edge Case Guard: If no valid points or candidate species exist
    if not valid_locations or not candidate_species:
        return []

    # 2. Build the Cost Matrix
    # linear_sum_assignment minimizes cost, so negative probability maximizes survival
    cost_matrix = np.zeros((len(candidate_species), len(valid_locations)))
    
    for i, species in enumerate(candidate_species):
        for j, loc in enumerate(valid_locations):
            prob = get_rf_probability(species, loc)
            
            # --- NEW: Print the AI's exact math to your VS Code terminal ---
            print(f"AI evaluated {species} at Elev {loc.get('elevation')}m: {prob*100:.2f}% survival")
            
            # --- CHANGED: Temporarily lowered threshold to 1% for testing ---
            if prob < 0.50: 
                cost_matrix[i, j] = 1000.0  # Prohibitive cost prevents assignment
            else:
                cost_matrix[i, j] = -prob   # Negative weight for maximization

    # 4. Execute Weighted Bipartite Matching (Hungarian Algorithm)
    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    
    # 5. Extract the final optimized blueprint
    optimized_blueprint = []
    for i, j in zip(row_ind, col_ind):
        # Ignore matches that hit the threshold penalty
        if cost_matrix[i, j] < 500:
            optimized_blueprint.append({
                "species": candidate_species[i],
                "location": valid_locations[j],
                "suitability_score": round(float(-cost_matrix[i, j]), 4)
            })
            
    return optimized_blueprint