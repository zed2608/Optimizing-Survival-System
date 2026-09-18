from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
import pandas as pd
import joblib

# Import your new modules
import models
from database import engine, SessionLocal
from clustering import assign_microclimates
from optimization import optimize_planting_layout

# Initialize the SQLite database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="San Mateo Urban Greening API")

# This tells Python to allow your React app to talk to it (DO NOT DELETE)
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

# Database session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Request schemas for validation
class Coordinate(BaseModel):
    lat: float
    lon: float
    elevation: float
    sunlight_hours: float
    soil_ph: float
    water_availability: float

class PlantingRequest(BaseModel):
    event_name: str
    target_hectares: float
    landowner_preference: str
    candidate_species: List[str]
    target_locations: List[Coordinate]
    baseline_trees: List[Coordinate]

# --- THE NEW OPTIMIZATION ENDPOINT ---
@app.post("/api/plan-event")
def plan_planting_event(request: PlantingRequest, db: Session = Depends(get_db)):
    # 1. Save Event Metadata to SQLite
    new_event = models.PlantingEvent(
        event_name=request.event_name,
        target_hectares=request.target_hectares,
        landowner_preference=request.landowner_preference
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)

    # 2. Format Coordinates and Run K-Means Clustering
    df_locations = pd.DataFrame([loc.model_dump() for loc in request.target_locations])
    if not df_locations.empty:
        df_clustered = assign_microclimates(df_locations)
        locations_with_zones = df_clustered.to_dict('records')
    else:
        locations_with_zones = []

    baseline_trees_dict = [tree.model_dump() for tree in request.baseline_trees]

    # 3. Execute Optimization (Bipartite Matching & Constraints)
    optimized_blueprint = optimize_planting_layout(
        candidate_species=request.candidate_species,
        target_locations=locations_with_zones,
        baseline_trees=baseline_trees_dict
    )

    # 4. Save the Optimized Allocations back to SQLite
    for match in optimized_blueprint:
        allocation = models.TreeAllocation(
            event_id=new_event.event_id,
            species_name=match['species'],
            latitude=match['location']['lat'],
            longitude=match['location']['lon'],
            suitability_score=match['suitability_score'],
            is_baseline_tree=False
        )
        db.add(allocation)
    
    db.commit()

    # 5. Return the finalized blueprint
    return {
        "message": "Planting event successfully optimized and saved.",
        "event_id": new_event.event_id,
        "total_trees_allocated": len(optimized_blueprint),
        "blueprint": optimized_blueprint
    }

# --- THE LEGACY ENDPOINT (Kept so your current React map doesn't break) ---
@app.get("/api/optimize-planting")
def get_optimized_sites():
    print("React requested legacy map data. Processing...")
    df = pd.read_csv('data/san_mateo_final_recommendations.csv')
    df_sample = df.dropna().sample(n=1000, random_state=42)
    
    results = []
    for index, row in df_sample.iterrows():
        if "No Suitable Species" in str(row['suitable_species']):
            continue
            
        ai_features = [[
            row['slope_percentage'], 
            row['elevation_m'], 
            2, 2, 2
        ]]
        
        prediction = rf_model.predict(ai_features)
        best_tree = label_encoder.inverse_transform(prediction)[0]
        
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