# Optimizing Survival

**A Random Forest-Based Species-Site Suitability Modeling and Weighted Bipartite Matching Spatial Optimization Framework for Community-Led Urban Greening in San Mateo, Rizal**

Undergraduate thesis project (CS 307, Technological Institute of the Philippines – Quezon City) that helps local government units and community groups decide **which tree species to plant where**, based on real environmental and spatial data instead of guesswork.

## What it does

Urban greening programs often fail because the wrong species get planted in the wrong locations. This system turns raw environmental data into a concrete, ranked planting plan:

1. **Species-site suitability modeling** — a Random Forest classifier trained on environmental and botanical data (elevation, slope, soil texture, land use, climate, and species tolerance rules) scores how well each tree species fits a given site.
2. **Spatial optimization** — a weighted bipartite matching algorithm allocates species to planting sites across the municipality, balancing suitability scores against planting constraints and site capacity.
3. **Interactive mapping** — results are served through a web dashboard so planners can explore recommended species-site pairings on a live map of San Mateo, Rizal.

## Tech stack

- **Backend:** Python, FastAPI, scikit-learn (Random Forest), NetworkX, GeoPandas, OSMnx, SQLAlchemy
- **Frontend:** React, Vite, Leaflet (interactive mapping)
- **Data:** San Mateo land-use datasets, botanical species suitability rules, elevation/slope rasters, zoning data

## Project structure

```
backend/        FastAPI backend (app.py)
frontend/       React + Vite + Leaflet dashboard
data/           Datasets and trained model artifacts
cache/          Cached intermediate data
api.py          Main API entry point
train_model.py / train_suitability_model.py   Model training scripts
optimization.py                               Weighted bipartite matching logic
clustering.py                                 Microclimate clustering
match_species.py / run_matching.py            Species-site matching pipeline
evaluate_system.py                            Model/system evaluation
```

## Authors

Cyrus Austin G. Andal, Charles Joseph S. Peralta, Ayzhiedy Jee D. Reyes, Angelo Genesis N. Talastas
Computer Science Department, Technological Institute of the Philippines – Quezon City
