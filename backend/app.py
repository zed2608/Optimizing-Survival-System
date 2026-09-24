import os
from flask import Flask, jsonify
from flask_cors import CORS
import pandas as pd

app = Flask(__name__)
CORS(app)

@app.route('/api/points', methods=['GET'])
def get_points():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    CSV_PATH = os.path.join(BASE_DIR, 'Working_Points.csv')

    df = pd.read_csv(CSV_PATH)
    
    # Define the grid size (0.000015 degrees is roughly 1.5 meters)
    offset = 0.000015
    
    # Mathematically rebuild the grid bounds around your correct San Mateo WGS84 points
    df['left'] = df['x'] - offset
    df['right'] = df['x'] + offset
    df['top'] = df['y'] + offset
    df['bottom'] = df['y'] - offset
    
    # Clean up and send to React
    df = df.fillna('')
    points = df.to_dict(orient='records')
    
    return jsonify(points)

if __name__ == '__main__':
    app.run(debug=True, port=5000)