from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import joblib

app = FastAPI()

# This tells Python to allow your React app (running on a different port) to talk to it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the AI Brain and Translator
print("Loading Random Forest AI...")
rf_model = joblib.load('data/rf_suitability_model.pkl')
label_encoder = joblib.load('data/rf_label_encoder.pkl')

@app.get("/api/optimize-planting")
def get_optimized_sites():
    print("React requested optimization data. Processing...")
    
    # 1. Load the pre-filtered environmental data
    df = pd.read_csv('data/san_mateo_final_recommendations.csv')
    
    # For performance on the dashboard, let's just map a sample of 150 points 
    # (Loading 17,000 points on a web map at once will crash the browser)
    df_sample = df.dropna().sample(n=1000, random_state=42)
    
    results = []
    
    # 2. Run the AI prediction for each coordinate
    for index, row in df_sample.iterrows():
        # If the plot is unplantable, skip it
        if "No Suitable Species" in str(row['suitable_species']):
            continue
            
        # We assume standard LGU planting conditions (e.g., standard soil prep)
        # to feed the AI the 5 features it was trained on
        ai_features = [[
            row['slope_percentage'], 
            row['elevation_m'], 
            2, # Average soil compatibility
            2, # Medium drought survival assumption
            2  # Medium shade assumption
        ]]
        
        # The AI predicts the absolute best tree
        prediction = rf_model.predict(ai_features)
        best_tree = label_encoder.inverse_transform(prediction)[0]
        
        # 3. Format exactly how React expects it
        results.append({
            "latitude": row['latitude'],
            "longitude": row['longitude'],
            "species": best_tree,
            "sapling_id": f"SPL-{index+1000}",
            "target_zone": f"Zone {int(row['elevation_m'] / 100)}A"
        })
        
    return {"data": results}

if __name__ == "__main__":
    import uvicorn
    # This runs the server exactly where React is looking: localhost:8000
    uvicorn.run(app, host="0.0.0.0", port=8000)