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
  const [committed, setCommitted] = useState(false);

  // Center the map roughly on San Mateo, Rizal
  const position = [14.698, 121.127];

  useEffect(() => {
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

  // Simulates finalizing the algorithmic assignments
  const handleCommit = () => {
    alert("Optimization schedule committed! Data would now be saved to the LGU database.");
    setCommitted(true);
  };

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', fontFamily: 'sans-serif', margin: 0, padding: 0 }}>
      
      {/* LEFT SIDEBAR PANEL (30% Width) */}
      <div style={{ width: '30%', backgroundColor: '#f4f6f8', borderRight: '1px solid #ddd', display: 'flex', flexDirection: 'column', zIndex: 1000 }}>
        
        {/* Sidebar Header */}
        <div style={{ padding: '25px 20px', backgroundColor: '#1a365d', color: 'white' }}>
          <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 'bold' }}>San Mateo LGU</h2>
          <p style={{ margin: '5px 0 0 0', fontSize: '0.9rem', color: '#a0aec0' }}>Greening Optimization Dashboard</p>
        </div>
        
        {/* Scrollable Data Area */}
        <div style={{ padding: '20px', flexGrow: 1, overflowY: 'auto' }}>
          {loading ? (
            <p style={{ color: '#4a5568' }}>Processing algorithm weights...</p>
          ) : (
            <>
              {/* Key Metrics Card */}
              <div style={{ marginBottom: '25px', padding: '15px', backgroundColor: 'white', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}>
                <h3 style={{ marginTop: 0, marginBottom: '10px', fontSize: '1.1rem', color: '#2d3748', borderBottom: '1px solid #edf2f7', paddingBottom: '5px' }}>
                  Optimization Metrics
                </h3>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.95rem', color: '#4a5568', marginBottom: '8px' }}>
                  <span>Total Assignments:</span>
                  <strong>{plantingSites.length}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.95rem', color: '#4a5568', marginBottom: '8px' }}>
                  <span>Engine:</span>
                  <strong>Bipartite Matching</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.95rem', color: '#4a5568' }}>
                  <span>Status:</span>
                  <strong style={{ color: committed ? '#38a169' : '#d69e2e' }}>
                    {committed ? "Committed" : "Pending Review"}
                  </strong>
                </div>
              </div>

              {/* Dynamic Sapling List */}
              <h3 style={{ fontSize: '1.1rem', color: '#2d3748', marginBottom: '15px' }}>Matched Assignments</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {plantingSites.map((site, index) => (
                  <div key={index} style={{ padding: '12px', backgroundColor: 'white', borderLeft: '4px solid #3182ce', borderRadius: '4px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
                    <div style={{ fontWeight: 'bold', fontSize: '0.95rem', color: '#2d3748' }}>
                      {site.species} <span style={{ fontWeight: 'normal', color: '#a0aec0', fontSize: '0.85rem' }}>({site.sapling_id})</span>
                    </div>
                    <div style={{ fontSize: '0.85rem', color: '#718096', marginTop: '4px' }}>
                      Zone: {site.target_zone}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Action Button Footer */}
        <div style={{ padding: '20px', borderTop: '1px solid #e2e8f0', backgroundColor: 'white' }}>
          <button 
            onClick={handleCommit}
            disabled={loading || committed}
            style={{ 
              width: '100%', 
              padding: '14px', 
              backgroundColor: committed ? '#cbd5e0' : '#3182ce', 
              color: committed ? '#4a5568' : 'white', 
              border: 'none', 
              borderRadius: '6px', 
              fontWeight: 'bold', 
              fontSize: '1rem',
              cursor: committed || loading ? 'not-allowed' : 'pointer',
              transition: 'background-color 0.2s',
              boxShadow: committed ? 'none' : '0 4px 6px rgba(49, 130, 206, 0.2)'
            }}
          >
            {committed ? "Schedule Committed" : "Commit Planting Schedule"}
          </button>
        </div>
      </div>

      {/* RIGHT MAP PANEL (70% Width) */}
      <div style={{ width: '70%', height: '100%' }}>
        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100%', backgroundColor: '#f4f6f8' }}>
            <h2 style={{ color: '#2d3748' }}>Running spatial optimization...</h2>
            <p style={{ color: '#718096' }}>Calculating hybrid cost matrix and drawing boundaries.</p>
          </div>
        ) : (
          <MapContainer center={position} zoom={13} style={{ height: '100%', width: '100%' }}>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            
            {plantingSites.map((site, index) => (
              <Marker key={index} position={[site.latitude, site.longitude]}>
                <Popup>
                  <div style={{ fontFamily: 'sans-serif', margin: 0 }}>
                    <strong style={{ display: 'block', marginBottom: '5px', fontSize: '1.1rem' }}>{site.species}</strong>
                    <span style={{ color: '#4a5568' }}>ID: {site.sapling_id}</span><br />
                    <span style={{ color: '#4a5568' }}>Zone: {site.target_zone}</span>
                  </div>
                </Popup>
              </Marker>
            ))}

          </MapContainer>
        )}
      </div>
    </div>
  );
}

export default App;