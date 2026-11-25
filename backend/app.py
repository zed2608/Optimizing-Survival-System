import os
import math
from flask import Flask, jsonify
from flask_cors import CORS
import pandas as pd

app = Flask(__name__)
CORS(app, resources={r'/api/*': {'origins': os.getenv('MAP_CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',')}})
app.config['POINTS_CSV'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Working_Points.csv')

@app.route('/api/points', methods=['GET'])
def get_points():
    CSV_PATH = app.config['POINTS_CSV']
    try:
        df = pd.read_csv(CSV_PATH)
    except (OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return jsonify({'error': 'Spatial dataset unavailable'}), 503
    if not {'x', 'y'}.issubset(df.columns):
        return jsonify({'error': 'Spatial dataset missing coordinate columns'}), 422
    
    # ==========================================
    # DATA SANITIZATION PIPELINE
    # ==========================================
    
    soil_col = 'soil_type' if 'soil_type' in df.columns else 'soil' if 'soil' in df.columns else None
    
    if soil_col:
        # HWSD v2.0 Translation Dictionary for San Mateo
        soil_lookup = {
            4478: "Gleyic Cambisol (Clay-Loam)",
            4413: "Nitisol (Clay)",
            4546: "Rhodic Nitisol (Red Clay)",
            7001: "Technosol (Urban/Paved)" 
        }

        def fix_soil(val):
            try:
                # Convert the raw CSV value to an integer
                numeric_val = int(float(val))
                return soil_lookup.get(numeric_val, str(val))
            except:
                return str(val)
        
        df[soil_col] = df[soil_col].apply(fix_soil)

    # FIX 2: Correct impossible GIS Slope artifacts (Convert Percent Rise to Degrees)
    slope_col = 'slope_1' if 'slope_1' in df.columns else 'slope' if 'slope' in df.columns else None
    
    if slope_col:
        def fix_slope(val):
            try:
                val = float(val)
                if val > 90:
                    val = math.degrees(math.atan(val / 100))
                return round(val, 2)
            except:
                return 0.0
        df[slope_col] = df[slope_col].apply(fix_slope)

    # ==========================================
    
    offset = 0.000015
    df['left'] = df['x'] - offset
    df['right'] = df['x'] + offset
    df['top'] = df['y'] + offset
    df['bottom'] = df['y'] - offset
    
    df = df.fillna('')
    points = df.to_dict(orient='records')
    
    return jsonify(points)

if __name__ == '__main__':
    app.run(host='127.0.0.1', debug=False, port=5000)