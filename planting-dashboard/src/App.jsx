import { useState, useEffect } from 'react';
import axios from 'axios';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Fix for default Leaflet icons in React
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

function App() {
  const [plantingSites, setPlantingSites] = useState([]);
  const [loading, setLoading] = useState(true);

  // Center the map roughly on San Mateo, Rizal
  const position = [14.698, 121.127];

  useEffect(() => {
    // This function talks to your Python FastAPI backend
    const fetchSites = async () => {
      try {
        const response = await axios.get('http://localhost:8000/api/optimize-planting');
        setPlantingSites(response.data.data);
        setLoading(false);
      } catch (error) {
        console.error("Error fetching data from FastAPI:", error);
        setLoading(false);
      }
    };

    fetchSites();
  }, []);

  return (
    <div style={{ height: '100vh', width: '100vw' }}>
      {loading ? (
        <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
          <h2>Running spatial optimization algorithm...</h2>
          <p>Please wait while the server calculates the hybrid cost matrix.</p>
        </div>
      ) : (
        <MapContainer center={position} zoom={13} style={{ height: '100%', width: '100%' }}>
          {/* Base map layer from OpenStreetMap */}
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          
          {/* Loop through your Python data and drop a pin for every tree */}
          {plantingSites.map((site, index) => (
            <Marker key={index} position={[site.latitude, site.longitude]}>
              <Popup>
                <div style={{ fontFamily: 'sans-serif' }}>
                  <strong>Species:</strong> {site.species} <br />
                  <strong>Sapling ID:</strong> {site.sapling_id} <br />
                  <strong>Assigned Zone:</strong> {site.target_zone}
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      )}
    </div>
  );
}

export default App;