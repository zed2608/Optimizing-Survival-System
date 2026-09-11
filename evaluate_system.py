import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from scipy.optimize import linear_sum_assignment
import joblib
from pathlib import Path
import warnings

# Suppress warnings for cleaner terminal output
warnings.filterwarnings('ignore')

def evaluate_system():
    print("==================================================")
    print(" SYSTEM EVALUATION: SAN MATEO GREENING FRAMEWORK  ")
    print("==================================================\n")
    
    data_folder = Path("data")
    
    # --- PART 1: ML PREDICTIVE EVALUATION ---
    print("[1] Evaluating Random Forest Suitability Model...")
    
    # Generate 500 brand-new, unseen records to test the model's true accuracy
    np.random.seed(99)
    species_list = ['Narra', 'Mahogany', 'Ilang-Ilang', 'Banaba', 'Molave']
    soil_types = ['Clay Loam', 'Sandy Loam', 'Silty Clay', 'Loam']
    hazard_levels = ['Low', 'Moderate', 'High']
    
    test_df = pd.DataFrame({
        'species': np.random.choice(species_list, 500),
        'soil_type': np.random.choice(soil_types, 500),
        'slope_percentage': np.random.uniform(0.0, 35.0, 500),
        'landslide_hazard': np.random.choice(hazard_levels, 500)
    })
    
    # Apply the exact same ecological ground truths
    def determine_survival(row):
        score = 0.5 
        if row['species'] == 'Narra' and row['slope_percentage'] < 15: score += 0.3
        if row['species'] == 'Mahogany' and row['soil_type'] in ['Clay Loam', 'Loam']: score += 0.2
        if row['landslide_hazard'] == 'High': score -= 0.4
        if row['slope_percentage'] > 25: score -= 0.3
        probability = max(0.05, min(0.95, score))
        return np.random.binomial(1, probability)

    y_true = test_df.apply(determine_survival, axis=1)
    
    # Load model and prepare test data
    rf_model = joblib.load(data_folder / "rf_suitability_model.pkl")
    model_columns = joblib.load(data_folder / "rf_model_columns.pkl")
    X_test = pd.get_dummies(test_df).reindex(columns=model_columns, fill_value=0)
    
    # Generate Predictions
    y_pred = rf_model.predict(X_test)
    
    # Calculate Metrics
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred)
    rec = recall_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred)
    cm = confusion_matrix(y_true, y_pred)
    
    print(f"    Accuracy:  {acc*100:.2f}%")
    print(f"    Precision: {prec*100:.2f}%")
    print(f"    Recall:    {rec*100:.2f}%")
    print(f"    F1-Score:  {f1*100:.2f}%")
    print(f"    Confusion Matrix:\n       [True Negatives: {cm[0][0]} | False Positives: {cm[0][1]}]\n       [False Negatives: {cm[1][0]} | True Positives: {cm[1][1]}]\n")

    # --- PART 2: OPTIMIZATION EVALUATION ---
    print("[2] Evaluating Spatial Optimization (Bipartite Matching)...")
    
    supply_df = pd.read_csv(data_folder / "mock_tree_inventory.csv").head(50)
    demand_df = pd.read_csv(data_folder / "mock_environmental_grid.csv").head(50)
    
    num_trees = len(supply_df)
    num_plots = len(demand_df)
    cost_matrix = np.zeros((num_trees, num_plots))
    prob_matrix = np.zeros((num_trees, num_plots))
    
    # Build suitability matrix
    for i, tree in supply_df.iterrows():
        for j, plot in demand_df.iterrows():
            feature_dict = {
                f"species_{tree['species']}": 1,
                f"soil_type_{plot['soil_type']}": 1,
                'slope_percentage': plot['slope_percentage'],
                f"landslide_hazard_{plot['landslide_hazard']}": 1
            }
            row_df = pd.DataFrame([feature_dict]).reindex(columns=model_columns, fill_value=0)
            prob = rf_model.predict_proba(row_df)[0][1]
            prob_matrix[i, j] = prob
            cost_matrix[i, j] = 1.0 - prob

    # Simulation A: Random Assignment
    random_assignment = np.random.permutation(num_plots)
    random_score = sum([prob_matrix[i, random_assignment[i]] for i in range(num_trees)])
    
    # Simulation B: Greedy Assignment (Pick the best one by one)
    greedy_score = 0
    available_plots = list(range(num_plots))
    for i in range(num_trees):
        best_plot = max(available_plots, key=lambda j: prob_matrix[i, j])
        greedy_score += prob_matrix[i, best_plot]
        available_plots.remove(best_plot)

    # Simulation C: Optimized Bipartite Matching
    tree_indices, plot_indices = linear_sum_assignment(cost_matrix)
    optimized_score = sum([prob_matrix[t, p] for t, p in zip(tree_indices, plot_indices)])
    
    print(f"    Expected Survival (Random Allocation):   {random_score:.2f} out of 50 trees")
    print(f"    Expected Survival (Greedy Allocation):   {greedy_score:.2f} out of 50 trees")
    print(f"    Expected Survival (Optimized Blueprint): {optimized_score:.2f} out of 50 trees")
    
    improvement = ((optimized_score - random_score) / random_score) * 100
    print(f"\n    Result: Bipartite Matching improved overall expected survival by {improvement:.2f}% compared to standard random allocation.")
    print("==================================================\n")

if __name__ == "__main__":
    evaluate_system()