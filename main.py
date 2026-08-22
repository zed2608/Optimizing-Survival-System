from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from scipy.optimize import linear_sum_assignment
import joblib
from pathlib import Path
import warnings

# Suppress scikit-learn warnings for cleaner terminal output
warnings.filterwarnings('ignore')

app = FastAPI(title="San Mateo Spatial Optimization API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)

@app.get("/api/optimize-planting")
def get_optimized_planting_sites():
    print("Received request. Running ML optimization...")
    data_folder = Path("data")
    
    # 1. Load Datasets
    supply_df = pd.read_csv(data_folder / "mock_tree_inventory.csv").head(50)
    # Load the synthetic environmental grid we just made
    demand_df = pd.read_csv(data_folder / "mock_environmental_grid.csv").head(50)
    
    # 2. Load the Random Forest Model
    rf_model = joblib.load(data_folder / "rf_suitability_model.pkl")
    model_columns = joblib.load(data_folder / "rf_model_columns.pkl")
    
    num_trees = len(supply_df)
    num_plots = len(demand_df)
    cost_matrix = np.zeros((num_trees, num_plots))
    
    # 3. Predict Suitability & Build Cost Matrix
    for i, tree in supply_df.iterrows():
        for j, plot in demand_df.iterrows():
            
            # Map the exact features expected by the model
            feature_dict = {
                f"species_{tree['species']}": 1,
                f"soil_type_{plot['soil_type']}": 1,
                'slope_percentage': plot['slope_percentage'],
                f"landslide_hazard_{plot['landslide_hazard']}": 1
            }
            
            # Align features with the trained model columns
            row_df = pd.DataFrame([feature_dict])
            row_df = row_df.reindex(columns=model_columns, fill_value=0)
            
            # Predict the probability of survival (class 1)
            prob_survival = rf_model.predict_proba(row_df)[0][1]
            
            # Bipartite matching MINIMIZES cost, but we want to MAXIMIZE survival.
            # Therefore, we invert the probability (Cost = 1.0 - probability)
            cost_matrix[i, j] = 1.0 - prob_survival

    # 4. Execute Weighted Bipartite Matching
    tree_indices, plot_indices = linear_sum_assignment(cost_matrix)
    
    # 5. Format Output for the React Dashboard
    results = []
    for idx in range(len(tree_indices)):
        t_idx = tree_indices[idx]
        p_idx = plot_indices[idx]
        
        # Calculate final percentage for display
        final_probability = (1.0 - cost_matrix[t_idx, p_idx]) * 100
        
        results.append({
            "sapling_id": supply_df.iloc[t_idx]['sapling_id'],
            "species": supply_df.iloc[t_idx]['species'],
            "target_zone": demand_df.iloc[p_idx]['actual_zone'],
            "longitude": float(demand_df.iloc[p_idx]['longitude']),
            "latitude": float(demand_df.iloc[p_idx]['latitude']),
            "suitability_score": round(final_probability, 1)
        })

    return {"status": "success", "total_matches": len(results), "data": results}