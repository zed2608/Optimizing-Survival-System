# Research integrity review

Baseline: `6e0ab7b39b88fa3b1ae751ef8dda7da5e915a76d`. This revision preserves the dataset files, trained model artifacts, training scripts, evaluation script, optimizer, clustering and GIS scripts byte-for-byte. The dashboard's existing numerical score rules are unchanged. Only explanatory UI wording, transport configuration and map API error behavior are revised.

## What the source actually implements

| Path | Implementation | Research interpretation |
| --- | --- | --- |
| frontend/src/App.jsx | Hand-authored ecological penalties, species/site mode, minimum combined score | Rule-based index; not a Random Forest inference or observed survival probability |
| backend/app.py | Working_Points.csv with soil code translation, slope handling, display cell bounds | GIS display service; no RF or matching endpoint |
| train_model.py | Generates 500 rule-derived cases per species; five-feature multiclass RF, encoded species labels | Species classification confidence, not calibrated survival probability |
| train_suitability_model.py | Generates 1,000 simulated cases per species; elevation, pH and encoded soil; map pH randomized | Separate experimental classifier with different inputs/artifact paths |
| api.py + optimization.py | Five-feature class probability; fixed values for soil/drought/shade; default slope if absent; Hungarian assignment; 0.50 threshold; 5 m exclusion around baseline trees | Prototype allocation; no confirmed calibration, no inter-new-tree spacing or explicit per-species inventory unless candidates repeat |
| main.py + evaluate_system.py | Binary survival workflow using one-hot mock data and model columns | Separate synthetic experiment; incompatible with the multiclass feature contract unless the corresponding binary model artifact is recovered |
| run_matching.py | Mock supply, randomly sampled zones and distance/zone penalty | Separate logistics demonstration |

## Critical questions before defense

1. Establish which exact pipeline and model artifact represent the approved thesis methodology. The dashboard currently fetches only the Flask /api/points endpoint; it does not invoke the FastAPI optimization endpoint. Do not describe the visible map as proof of integrated Random Forest optimization.
2. Verify the model's feature names, class labels, label encoder and provenance. The binary evaluation expects class 1 and one-hot columns, while train_model.py writes a multiclass classifier at the same artifact filename. Do not overwrite or retrain the tracked artifact until the approved pipeline is established. No accuracy, precision, recall, F1, or survival improvement claim is made from the repository alone.
3. Rule-derived synthetic outcomes are not field-observed survival labels. Classification probabilities, heuristic scores and simulated expected survival are different quantities. Field validation, calibrated probabilities and spatial holdout testing require separately designed evidence.
4. Confirm coordinate reference systems and slope units. The Flask code converts slope values above 90 using atan(percent/100), but does not convert all percent-rise values. The frontend assumes degrees; preserve this behavior until the underlying layer units are verified. Missing pH/elevation/slope use defaults in the UI; the other training path randomizes pH. Document all assumptions.
5. Verify botanical sources, species aliases/counts, zoning permissions, inventory quantities, baseline-tree exclusions, landowner constraints and actual planting capacity. The API records target hectares and preference but does not use them in the matching objective. The optimizer matches candidate entries to locations one-to-one and excludes sites near baseline trees only.
6. Check the rights and terms for municipal spatial data, imagery, and externally hosted geocoding. Some coordinates are sent to ArcGIS for reverse geocoding; no new external service was added.

## Verification boundary

The integrity manifest and read-only audit identify source and dataset bytes. They do not establish the model's validity. Automated tests exercise a synthetic map API fixture and frontend compilation, not scientific accuracy. Preserve original results and approved manuscript; any methodological revision requires team/adviser approval and documented re-evaluation.
