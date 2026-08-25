import { useState, useEffect } from 'react';
import axios from 'axios';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});
L.Marker.prototype.options.icon = DefaultIcon;

function App() {
  const [plantingSites, setPlantingSites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [committed, setCommitted] = useState(false);

  const position = [14.698, 121.127];
  const averageScore = plantingSites.length
    ? (plantingSites.reduce((sum, site) => sum + (site.suitability_score || 0), 0) / plantingSites.length).toFixed(1)
    : 0;

  useEffect(() => {
    const fetchSites = async () => {
      try {
        const response = await axios.get('http://localhost:8000/api/optimize-planting');
        setPlantingSites(response.data.data || []);
      } catch (error) {
        console.error('Error fetching data from FastAPI:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchSites();
  }, []);

  const handleCommit = () => {
    alert('Optimization schedule committed! Data would now be saved to the LGU database.');
    setCommitted(true);
  };

  return (
    <div
      style={{
        display: 'flex',
        height: '100vh',
        width: '100vw',
        margin: 0,
        padding: 0,
        background: 'linear-gradient(135deg, #eef8f2 0%, #edf3f7 100%)',
        fontFamily: 'Inter, "Segoe UI", sans-serif',
        color: '#12324a',
      }}
    >
      <aside
        style={{
          width: '32%',
          minWidth: '330px',
          background: 'linear-gradient(180deg, #113b4d 0%, #0f2f3f 100%)',
          color: '#edf7f6',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '8px 0 30px rgba(17, 59, 77, 0.12)',
          zIndex: 10,
        }}
      >
        <div style={{ padding: '30px 26px 22px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '16px',
                background: 'linear-gradient(135deg, #6ee7b7 0%, #2dd4bf 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#0d2b36',
                fontWeight: '800',
                fontSize: '1.2rem',
              }}
            >
              S
            </div>
            <div>
              <div style={{ fontSize: '0.7rem', letterSpacing: '0.12em', textTransform: 'uppercase', opacity: 0.72 }}>
                Local government unit
              </div>
              <h2 style={{ margin: '6px 0 0', fontSize: '1.75rem', fontWeight: '700', lineHeight: 1.1 }}>
                San Mateo LGU
              </h2>
            </div>
          </div>

          <div
            style={{
              marginTop: '22px',
              padding: '14px 16px',
              borderRadius: '16px',
              background: 'rgba(255,255,255,0.07)',
              border: '1px solid rgba(255,255,255,0.08)',
            }}
          >
            <div style={{ fontSize: '0.72rem', letterSpacing: '0.12em', textTransform: 'uppercase', opacity: 0.7 }}>
              Greening dashboard
            </div>
            <div style={{ marginTop: '8px', fontSize: '1.1rem', fontWeight: '600' }}>
              Reforestation optimization engine
            </div>
          </div>
        </div>

        <div style={{ padding: '0 22px 24px', flexGrow: 1, overflowY: 'auto' }}>
          {loading ? (
            <div
              style={{
                marginTop: '18px',
                padding: '24px 18px',
                borderRadius: '18px',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: '#d9f2eb',
              }}
            >
              Processing algorithm weights and suitability map...
            </div>
          ) : (
            <>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                  gap: '12px',
                  marginBottom: '18px',
                }}
              >
                <div style={{ padding: '16px', borderRadius: '16px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)' }}>
                  <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.08em', opacity: 0.7 }}>Assignments</div>
                  <div style={{ marginTop: '8px', fontSize: '1.8rem', fontWeight: '700' }}>{plantingSites.length}</div>
                </div>
                <div style={{ padding: '16px', borderRadius: '16px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)' }}>
                  <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.08em', opacity: 0.7 }}>Avg score</div>
                  <div style={{ marginTop: '8px', fontSize: '1.8rem', fontWeight: '700' }}>{averageScore}%</div>
                </div>
              </div>

              <div
                style={{
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '18px',
                  padding: '18px 18px 10px',
                  marginBottom: '18px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <div style={{ fontSize: '0.78rem', letterSpacing: '0.08em', textTransform: 'uppercase', opacity: 0.75 }}>Status</div>
                  <span
                    style={{
                      padding: '6px 10px',
                      borderRadius: '999px',
                      background: committed ? 'rgba(46, 204, 113, 0.18)' : 'rgba(255, 193, 7, 0.18)',
                      color: committed ? '#94f5be' : '#ffd166',
                      fontSize: '0.72rem',
                      fontWeight: '700',
                    }}
                  >
                    {committed ? 'Committed' : 'Pending review'}
                  </span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '6px', opacity: 0.8 }}>
                      <span>Model confidence</span>
                      <span>{averageScore}%</span>
                    </div>
                    <div style={{ height: '8px', borderRadius: '999px', background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
                      <div
                        style={{
                          width: `${Math.min(averageScore, 100)}%`,
                          height: '100%',
                          borderRadius: '999px',
                          background: 'linear-gradient(90deg, #6ee7b7 0%, #38bdf8 100%)',
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div style={{ marginBottom: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ margin: 0, fontSize: '1.08rem', fontWeight: '700' }}>Matched assignments</h3>
                <span style={{ opacity: 0.72, fontSize: '0.75rem' }}>{plantingSites.length} total</span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {plantingSites.map((site, index) => (
                  <div
                    key={index}
                    style={{
                      padding: '14px 14px 12px',
                      borderRadius: '14px',
                      background: 'rgba(255,255,255,0.05)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      boxShadow: '0 10px 18px rgba(15, 47, 63, 0.12)',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px' }}>
                      <div>
                        <div style={{ fontWeight: '700', fontSize: '1rem' }}>{site.species}</div>
                        <div style={{ marginTop: '4px', fontSize: '0.76rem', opacity: 0.72 }}>ID: {site.sapling_id}</div>
                      </div>
                      <div
                        style={{
                          padding: '6px 8px',
                          borderRadius: '999px',
                          background: 'rgba(110, 231, 183, 0.15)',
                          color: '#9ef5d2',
                          fontSize: '0.72rem',
                          fontWeight: '700',
                        }}
                      >
                        {site.suitability_score || 0}%
                      </div>
                    </div>
                    <div style={{ marginTop: '10px', fontSize: '0.82rem', opacity: 0.8 }}>Zone: {site.target_zone}</div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        <div style={{ padding: '0 22px 22px' }}>
          <button
            onClick={handleCommit}
            disabled={loading || committed}
            style={{
              width: '100%',
              border: 'none',
              borderRadius: '14px',
              padding: '16px 18px',
              background: committed ? '#cbd5e1' : 'linear-gradient(135deg, #20c997 0%, #14b8a6 100%)',
              color: committed ? '#2d3748' : '#ffffff',
              fontSize: '1rem',
              fontWeight: '700',
              boxShadow: committed ? 'none' : '0 10px 20px rgba(20, 184, 166, 0.22)',
              cursor: committed || loading ? 'not-allowed' : 'pointer',
            }}
          >
            {committed ? 'Schedule committed' : 'Commit planting schedule'}
          </button>
        </div>
      </aside>

      <main style={{ position: 'relative', flex: 1, minWidth: 0, background: 'linear-gradient(180deg, #f3faf5 0%, #edf3f8 100%)' }}>
        <div
          style={{
            position: 'absolute',
            top: '20px',
            left: '24px',
            right: '24px',
            zIndex: 500,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '14px 18px',
            borderRadius: '18px',
            background: 'rgba(255,255,255,0.82)',
            backdropFilter: 'blur(10px)',
            border: '1px solid rgba(17, 59, 77, 0.08)',
            boxShadow: '0 20px 35px rgba(17, 59, 77, 0.08)',
          }}
        >
          <div>
            <div style={{ fontSize: '0.72rem', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#6b7280' }}>Priority map</div>
            <div style={{ fontSize: '1.3rem', fontWeight: '700', color: '#12324a' }}>Planting suitability view</div>
          </div>
          <div
            style={{
              padding: '8px 12px',
              borderRadius: '999px',
              background: 'rgba(20, 184, 166, 0.12)',
              color: '#0d766e',
              fontWeight: '700',
              fontSize: '0.8rem',
            }}
          >
            {committed ? 'Ready for deployment' : 'Ready for review'}
          </div>
        </div>

        {loading ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'center',
              height: '100%',
              background: 'linear-gradient(180deg, rgba(222, 244, 233, 0.4), rgba(237, 243, 248, 0.85))',
            }}
          >
            <div style={{ fontSize: '2rem', fontWeight: '700', color: '#12324a', marginBottom: '8px' }}>Running spatial optimization...</div>
            <div style={{ fontSize: '1rem', color: '#4b5563' }}>Calculating optimized planting clusters and suitability model.</div>
          </div>
        ) : (
          <div style={{ height: '100%', width: '100%', paddingTop: '96px' }}>
            <MapContainer center={position} zoom={13} style={{ height: 'calc(100% - 96px)', width: '100%' }}>
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              {plantingSites.map((site, index) => (
                <Marker key={index} position={[site.latitude, site.longitude]}>
                  <Popup>
                    <div style={{ fontFamily: 'Inter, sans-serif', margin: 0 }}>
                      <strong style={{ display: 'block', marginBottom: '6px', fontSize: '1.05rem' }}>{site.species}</strong>
                      <span style={{ color: '#4a5568' }}>ID: {site.sapling_id}</span><br />
                      <span style={{ color: '#4a5568' }}>Zone: {site.target_zone}</span><br />
                      <span style={{ color: '#4a5568' }}>Suitability: {site.suitability_score || 0}%</span>
                    </div>
                  </Popup>
                </Marker>
              ))}
            </MapContainer>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;