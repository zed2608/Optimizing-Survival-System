import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib
from pathlib import Path

def train_suitability_model():
    print("Initializing Random Forest Training Module...")
    data_folder = Path("data")
    
    # 1. Generate Synthetic Historical Training Data
    # (Simulating past LGU planting records to teach the model)
    num_samples = 1500
    species_list = ['Narra', 'Mahogany', 'Ilang-Ilang', 'Banaba', 'Molave']
    soil_types = ['Clay Loam', 'Sandy Loam', 'Silty Clay', 'Loam']
    hazard_levels = ['Low', 'Moderate', 'High']
    
    np.random.seed(42)
    df = pd.DataFrame({
        'species': np.random.choice(species_list, num_samples),
        'soil_type': np.random.choice(soil_types, num_samples),
        'slope_percentage': np.random.uniform(0.0, 35.0, num_samples),
        'landslide_hazard': np.random.choice(hazard_levels, num_samples)
    })
    
    # 2. Simulate Ecological Survival Rules 
    # (Teaching the model that certain conditions cause failure)
    def determine_survival(row):
        score = 0.5 
        if row['species'] == 'Narra' and row['slope_percentage'] < 15: score += 0.3
        if row['species'] == 'Mahogany' and row['soil_type'] in ['Clay Loam', 'Loam']: score += 0.2
        if row['landslide_hazard'] == 'High': score -= 0.4
        if row['slope_percentage'] > 25: score -= 0.3
        
        probability = max(0.05, min(0.95, score))
        return np.random.binomial(1, probability)

    df['survived'] = df.apply(determine_survival, axis=1)
    
    # 3. Preprocess Data (Convert text to numbers for the math engine)
    X = pd.get_dummies(df[['species', 'soil_type', 'slope_percentage', 'landslide_hazard']])
    y = df['survived']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 4. Train the Random Forest
    print("Training Random Forest Classifier on historical data...")
    rf_model = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=10)
    rf_model.fit(X_train, y_train)
    
    # 5. Evaluate Performance
    y_pred = rf_model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"Model Accuracy: {acc * 100:.2f}%")
    
    # 6. Save the Model
    joblib.dump(rf_model, data_folder / "rf_suitability_model.pkl")
    joblib.dump(X.columns.tolist(), data_folder / "rf_model_columns.pkl")
    print("Success! Random Forest model exported as .pkl file.")

if __name__ == "__main__":
    train_suitability_model()