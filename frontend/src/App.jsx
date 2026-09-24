import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, Tooltip, useMap, useMapEvents } from 'react-leaflet';
import * as turf from '@turf/turf';
import axios from 'axios';

import 'leaflet/dist/leaflet.css';
import 'leaflet-draw/dist/leaflet.draw.css';

import L from 'leaflet';
window.L = L;
import 'leaflet-draw';

// 1. CURSOR TRACKER
function CursorTracker() {
  useMapEvents({
    mousemove(e) {
      const display = document.getElementById('cursor-display');
      if (display) display.innerText = `${e.latlng.lat.toFixed(5)}, ${e.latlng.lng.toFixed(5)}`;
    },
    mouseout() {
      const display = document.getElementById('cursor-display');
      if (display) display.innerText = 'Hover over map...';
    }
  });
  return null;
}

// 2. PROGRAMMATIC MAP TOOL CONTROLLER
function MapToolController({ isDrawingPolygon, setIsDrawingPolygon, drawnZone, setDrawnZone, isEditingZone, setIsEditingZone }) {
  const map = useMap();
  const drawnItemsRef = useRef(new L.FeatureGroup());

  useEffect(() => {
    const layerGroup = drawnItemsRef.current;
    map.addLayer(layerGroup);
    return () => { map.removeLayer(layerGroup); };
  }, [map]);

  useEffect(() => {
    if (!drawnZone) {
      drawnItemsRef.current.clearLayers();
    } else if (drawnItemsRef.current.getLayers().length === 0) {
      const geoJsonLayer = L.geoJSON(drawnZone, {
        style: { color: '#3182ce', weight: 2, fillOpacity: 0.2 },
        interactive: false
      });
      const layer = geoJsonLayer.getLayers()[0];
      if (layer) drawnItemsRef.current.addLayer(layer);
    }
  }, [drawnZone]);

  useEffect(() => {
    if (!isDrawingPolygon) return;
    const polygonDrawer = new L.Draw.Polygon(map, {
      showArea: true,
      shapeOptions: { color: '#3182ce', weight: 2, fillOpacity: 0.2, interactive: false }
    });
    
    polygonDrawer.enable();

    const onDrawCreated = (e) => {
      e.layer.options.interactive = false; 
      drawnItemsRef.current.clearLayers();
      drawnItemsRef.current.addLayer(e.layer);
      setDrawnZone(e.layer.toGeoJSON());
      setIsDrawingPolygon(false);
    };

    map.on(L.Draw.Event.CREATED, onDrawCreated);
    return () => {
      polygonDrawer.disable();
      map.off(L.Draw.Event.CREATED, onDrawCreated);
    };
  }, [isDrawingPolygon, map, setDrawnZone, setIsDrawingPolygon]);

  useEffect(() => {
    const layer = drawnItemsRef.current.getLayers()[0];
    if (!layer) return;

    if (isEditingZone) {
      layer.editing.enable();
    } else {
      if (layer.editing.enabled()) {
        layer.editing.disable();
        setDrawnZone(layer.toGeoJSON());
      }
    }
  }, [isEditingZone, setDrawnZone]);

  return null;
}

// 3. STRICT DSS SCORING ENGINE (Incorporating Soil, Drought, & Flood Rules)
const speciesRules = {
  "Narra": { minElev: 0, maxElev: 1000, maxSlope: 30, minPh: 5.0, maxPh: 7.5, soil: "Alluvial Clay, Clay-Loam", drought: "High", water: "Medium" },
  "Molave": { minElev: 0, maxElev: 700, maxSlope: 60, minPh: 6.0, maxPh: 8.5, soil: "Limestone-Based, Sandy-Clay", drought: "High", water: "Low" },
  "Dao": { minElev: 0, maxElev: 800, maxSlope: 45, minPh: 5.5, maxPh: 7.5, soil: "Alluvial Clay, Volcanic Loam", drought: "Medium", water: "High" },
  "Banaba": { minElev: 0, maxElev: 800, maxSlope: 15, minPh: 5.0, maxPh: 7.0, soil: "Clay-Loam, Alluvial Clay", drought: "Medium", water: "High" },
  "Bitaog": { minElev: 0, maxElev: 500, maxSlope: 20, minPh: 5.5, maxPh: 8.0, soil: "Sandy-Clay, Alluvial Clay", drought: "High", water: "High" },
  "Kalumpit": { minElev: 0, maxElev: 600, maxSlope: 45, minPh: 5.0, maxPh: 7.5, soil: "Clay-Loam, Ridge Clay", drought: "Medium", water: "Medium" },
  "Duhat": { minElev: 0, maxElev: 1200, maxSlope: 30, minPh: 5.5, maxPh: 7.5, soil: "Alluvial Clay, Clay-Loam", drought: "High", water: "High" },
  "Kamagong": { minElev: 0, maxElev: 800, maxSlope: 45, minPh: 5.5, maxPh: 7.5, soil: "Ridge Clay, Volcanic Loam", drought: "High", water: "Low" },
  "Katmon": { minElev: 0, maxElev: 800, maxSlope: 45, minPh: 5.0, maxPh: 6.5, soil: "Clay-Loam, Volcanic Loam", drought: "Low", water: "Medium" },
  "Batikuling": { minElev: 100, maxElev: 1000, maxSlope: 45, minPh: 5.5, maxPh: 7.0, soil: "Volcanic Loam, Clay-Loam", drought: "Medium", water: "Low" },
  "Palosapis": { minElev: 0, maxElev: 1000, maxSlope: 45, minPh: 5.0, maxPh: 6.5, soil: "Ridge Clay, Volcanic Loam", drought: "Low", water: "Low" },
  "Talisay": { minElev: 0, maxElev: 400, maxSlope: 15, minPh: 5.5, maxPh: 8.5, soil: "Sandy-Clay, Alluvial Clay", drought: "High", water: "High" },
  "Bamboo": { minElev: 0, maxElev: 1000, maxSlope: 70, minPh: 5.0, maxPh: 8.0, soil: "Alluvial Clay, Clay-Loam", drought: "High", water: "High" },
  "Langka": { minElev: 0, maxElev: 1000, maxSlope: 25, minPh: 5.5, maxPh: 7.5, soil: "Volcanic Loam, Clay-Loam", drought: "Medium", water: "Low" },
  "Guyabano": { minElev: 0, maxElev: 1000, maxSlope: 25, minPh: 5.5, maxPh: 6.5, soil: "Clay-Loam, Sandy-Clay", drought: "Medium", water: "Low" },
  "Atsuete": { minElev: 0, maxElev: 1000, maxSlope: 25, minPh: 5.5, maxPh: 7.5, soil: "Clay-Loam, Volcanic Loam", drought: "High", water: "Low" },
  "Cacao": { minElev: 0, maxElev: 800, maxSlope: 20, minPh: 5.0, maxPh: 7.5, soil: "Volcanic Loam, Clay-Loam", drought: "Low", water: "Low" },
  "Rambutan": { minElev: 0, maxElev: 600, maxSlope: 20, minPh: 5.0, maxPh: 6.5, soil: "Clay-Loam, Volcanic Loam", drought: "Low", water: "Low" },
  "Kasoy": { minElev: 0, maxElev: 700, maxSlope: 25, minPh: 5.0, maxPh: 8.0, soil: "Sandy-Clay, Limestone-Based", drought: "High", water: "Low" },
  "Sampalok": { minElev: 0, maxElev: 1000, maxSlope: 25, minPh: 5.5, maxPh: 8.5, soil: "Sandy-Clay, Clay-Loam", drought: "High", water: "Low" },
  "Yakal": { minElev: 100, maxElev: 800, maxSlope: 45, minPh: 5.0, maxPh: 6.5, soil: "Ridge Clay, Volcanic Loam", drought: "Low", water: "Low" },
  "Mango": { minElev: 0, maxElev: 1200, maxSlope: 25, minPh: 5.5, maxPh: 7.5, soil: "Volcanic Loam, Clay-Loam, Alluvial Clay", drought: "High", water: "Medium" }
};

const calculateSuitability = (species, pt) => {
  const elev = parseFloat(pt.elevation_) || parseFloat(pt.elevation) || 0;
  const ph = parseFloat(pt.soil_ph) || 7;
  const slope = parseFloat(pt.slope_1) || parseFloat(pt.slope) || 0;
  
  // Safely extract the point's soil type
  const ptSoil = String(pt.soil_type || pt.soil || 'Unknown').trim();

  let score = 100;
  let reasons = []; 
  
  const rules = speciesRules[species];
  if (!rules) return { score: 0, elev, ph, slope, soil: ptSoil, reasons: ["Species data missing."]};

  // 1. ELEVATION CHECK
  if (elev < rules.minElev) {
      score -= 25; reasons.push(`Elevation too low (Min: ${rules.minElev}m) (-25%)`);
  } else if (elev > rules.maxElev) {
      score -= 25; reasons.push(`Elevation too high (Max: ${rules.maxElev}m) (-25%)`);
  } else if (elev > rules.maxElev * 0.8) {
      score -= 10; reasons.push(`Elevation near upper limit (-10%)`);
  }

  // 2. DROUGHT CHECK (High elevation + Low Drought Tolerance = Penalty)
  if (elev > 400 && rules.drought === "Low") {
      score -= 20; reasons.push(`High-elevation drought risk for this species (-20%)`);
  }

  // 3. SLOPE CHECK
  if (slope > rules.maxSlope) {
      score -= 30; reasons.push(`Slope too steep (Max: ${rules.maxSlope}°) (-30%)`);
  } else if (slope > rules.maxSlope * 0.75) {
      score -= 10; reasons.push(`Moderate slope limitation (-10%)`); // Reduced from 15 to 10
  }

  // 4. FLOOD / WATERLOGGING CHECK (Flat area + Low Waterlogging Tolerance = Penalty)
  if (slope < 5 && rules.water === "Low") {
      score -= 25; reasons.push(`High root-rot risk in flat terrain (-25%)`);
  }

  // 5. pH CHECK
  if (ph < rules.minPh || ph > rules.maxPh) {
      score -= 15; reasons.push(`Suboptimal pH (Ideal: ${rules.minPh}-${rules.maxPh}) (-15%)`);
  }

  // 6. SMARTER SOIL TYPE CHECK (Innocent until proven incompatible)
  const ptSoilLower = ptSoil.toLowerCase();
  const allowedSoilsLower = rules.soil.toLowerCase();
  
  if (ptSoilLower === 'unknown' || ptSoilLower === '') {
      score -= 10; reasons.push(`Unknown soil type safety penalty (-10%)`);
  } else {
      // Check for direct texture conflicts
      const isPointClay = ptSoilLower.includes('clay');
      const isPointSand = ptSoilLower.includes('sand');
      const isPointLoam = ptSoilLower.includes('loam');
      
      const needsClay = allowedSoilsLower.includes('clay');
      const needsSand = allowedSoilsLower.includes('sand');
      const needsLoam = allowedSoilsLower.includes('loam');

      // Only apply the brutal -30% penalty if there is a definitive, proven contradiction
      let hasConflict = false;
      if (isPointSand && !needsSand && (needsClay || needsLoam)) hasConflict = true;
      if (isPointClay && !needsClay && (needsSand)) hasConflict = true;

      if (hasConflict) {
          score -= 30; reasons.push(`Definitive soil conflict: ${ptSoil} (-30%)`);
      } 
      // If it's just a local name (like "Antipolo Soils") and doesn't explicitly conflict, give a minor unverified penalty
      else if (!isPointClay && !isPointSand && !isPointLoam) {
          score -= 10; reasons.push(`Unverified local soil texture (${ptSoil}) (-10%)`);
      }
  }

  if (reasons.length === 0) reasons.push("✓ Perfect environmental match.");
  score = Math.max(0, Math.min(100, score));

  return { score, elev, ph, slope, soil: ptSoil, reasons };
};

// 4. MULTI-SPECIES MATRIX EVALUATOR
const evaluateMultiSpecies = (speciesArray, pt) => {
  if (!speciesArray || speciesArray.length === 0) return null;

  let minScore = 100;
  let combinedResults = [];
  let envStats = {};

  speciesArray.forEach((species, i) => {
    const analysis = calculateSuitability(species, pt);
    if (i === 0) {
      envStats = { elev: analysis.elev, ph: analysis.ph, slope: analysis.slope, soil: analysis.soil };
    }
    if (analysis.score < minScore) minScore = analysis.score;
    
    combinedResults.push({
      species,
      score: analysis.score,
      reasons: analysis.reasons
    });
  });

  let color = '#f44336'; 
  let status = 'Poor / High Risk';
  if (minScore >= 80) { color = '#00e676'; status = 'Optimal (S1)'; }
  else if (minScore >= 50) { color = '#ffeb3b'; status = 'Moderate / Plantable (S2)'; }

  return { score: minScore, color, status, ...envStats, breakdown: combinedResults };
};

const sanMateoBounds = [
  [14.4500, 120.9000], 
  [14.9500, 121.4500]  
];

function App() {
  const [points, setPoints] = useState([]);
  const [loading, setLoading] = useState(true);
  
  const [stats, setStats] = useState({ verified: 0, rejected: 0 });
  const [pointStatuses, setPointStatuses] = useState({}); 
  
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [drawnZone, setDrawnZone] = useState(null);
  const [isEditingZone, setIsEditingZone] = useState(false); 

  const [eventDetails, setEventDetails] = useState({
    campaignName: '', startDate: '', endDate: '', targetSpecies: [], personnel: ''
  });
  const [isEventActive, setIsEventActive] = useState(false);

  const [zoneMode, setZoneMode] = useState('draw'); 
  const [isDrawingPolygon, setIsDrawingPolygon] = useState(false);
  const [manualFields, setManualFields] = useState([
    { lat: '', lng: '' }, { lat: '', lng: '' }, { lat: '', lng: '' }
  ]);

  const availableSpecies = Object.keys(speciesRules).sort();

  useEffect(() => {
    axios.get('http://127.0.0.1:5000/api/points')
      .then((response) => {
        const dataWithStableIds = response.data.map((pt, i) => ({
          ...pt,
          stableId: (pt.fid !== undefined && pt.fid !== null) ? pt.fid : `pt_${i}`
        }));
        setPoints(dataWithStableIds);
        setLoading(false);
      })
      .catch((error) => {
        console.error("Error fetching points:", error);
        setLoading(false);
      });
  }, []);

  const hasSpeciesSelected = Array.isArray(eventDetails.targetSpecies) && eventDetails.targetSpecies.length > 0;

  const activePoints = points.map(pt => {
    const lat = parseFloat(pt.Y ?? pt.y ?? pt.lat ?? pt.latitude);
    const lng = parseFloat(pt.X ?? pt.x ?? pt.lon ?? pt.longitude);
    if (isNaN(lat) || isNaN(lng)) return null;

    if (drawnZone) {
      const turfPoint = turf.point([lng, lat]);
      if (!turf.booleanPointInPolygon(turfPoint, drawnZone)) return null;
    }

    if (hasSpeciesSelected) {
      const analysis = evaluateMultiSpecies(eventDetails.targetSpecies, pt);
      if (!analysis || analysis.score === 0) return null; 
      return { ...pt, lat, lng, analysis };
    } else {
      return { 
        ...pt, lat, lng, 
        analysis: { 
          score: 'N/A', color: '#a0aec0', status: 'Select Species',
          elev: parseFloat(pt.elevation_) || parseFloat(pt.elevation) || 0,
          slope: parseFloat(pt.slope_1) || parseFloat(pt.slope) || 0,
          ph: parseFloat(pt.soil_ph) || 7,
          soil: String(pt.soil_type || pt.soil || 'Unknown').trim(),
          breakdown: []
        } 
      };
    }
  }).filter(Boolean);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setEventDetails(prev => ({ ...prev, [name]: value }));
  };

  const handleSpeciesCheckbox = (species) => {
    setEventDetails(prev => {
      let currentArr = Array.isArray(prev.targetSpecies) ? prev.targetSpecies : [];
      if (currentArr.includes(species)) {
        return { ...prev, targetSpecies: currentArr.filter(s => s !== species) };
      } else {
        return { ...prev, targetSpecies: [...currentArr, species] };
      }
    });
  };

  const handleStartCampaign = (e) => {
    e.preventDefault();
    if (!hasSpeciesSelected) {
      alert("Please select at least one species by clicking the checkboxes.");
      return;
    }
    setIsEventActive(true);
  };

  const handlePointVerification = (point, newStatus) => {
    const ptId = point.stableId;
    const prevStatus = pointStatuses[ptId];
    
    if (prevStatus === newStatus) return; 

    setPointStatuses(prev => ({ ...prev, [ptId]: newStatus }));

    setStats(prev => {
      let { verified, rejected } = prev;
      if (prevStatus === 'verified') verified -= 1;
      if (prevStatus === 'rejected') rejected -= 1;
      
      if (newStatus === 'verified') verified += 1;
      if (newStatus === 'rejected') rejected += 1;
      
      return { verified, rejected };
    });
  };

  const updateManualField = (index, field, value) => {
    const newFields = [...manualFields];
    newFields[index][field] = value;
    setManualFields(newFields);
  };
  const addManualField = () => setManualFields([...manualFields, { lat: '', lng: '' }]);
  const removeManualField = (index) => {
    if (manualFields.length > 3) setManualFields(manualFields.filter((_, i) => i !== index));
  };
  const handleManualZoneSubmit = () => {
    if (manualFields.some(f => !f.lat || !f.lng)) {
      alert("Please fill all coordinate fields or remove empty ones.");
      return;
    }
    try {
      const coordsArray = manualFields.map(f => [parseFloat(f.lng), parseFloat(f.lat)]); 
      const first = coordsArray[0];
      const last = coordsArray[coordsArray.length - 1];
      if (first[0] !== last[0] || first[1] !== last[1]) coordsArray.push([...first]);
      const polygon = turf.polygon([coordsArray]);
      setDrawnZone(polygon);
      setZoneMode('draw'); 
    } catch (err) {
      alert("Invalid coordinates entered.");
    }
  };
  const handleClearZone = () => {
    setDrawnZone(null);
    setIsDrawingPolygon(false);
    setIsEditingZone(false);
  };

  const handleExportCSV = () => {
    if (!isEventActive) {
      alert("Start a campaign first to process the data.");
      return;
    }
    if (activePoints.length === 0) {
      alert("No valid points to export.");
      return;
    }
    
    const exportData = activePoints.map((pt) => {
      const ptId = pt.stableId;
      const currentStatus = pointStatuses[ptId];
      
      let statusLabel = "Pending Verification";
      if (currentStatus === 'verified') statusLabel = "✅ VERIFIED PLANTABLE";
      if (currentStatus === 'rejected') statusLabel = "❌ FLAGGED PAVED (SKIP)";
      
      return {
        Point_ID: typeof ptId === 'string' ? ptId.replace('pt_', '') : ptId,
        Site_Status: statusLabel, 
        Latitude: pt.lat.toFixed(6),
        Longitude: pt.lng.toFixed(6),
        Elevation_m: pt.analysis.elev.toFixed(1),
        Slope_deg: pt.analysis.slope.toFixed(1),
        Soil_pH: pt.analysis.ph.toFixed(2),
        Soil_Type: pt.analysis.soil,
        Target_Species: Array.isArray(eventDetails.targetSpecies) ? eventDetails.targetSpecies.join(' + ') : '',
        Agroforestry_Viability: `${pt.analysis.score}%`,
        Campaign: eventDetails.campaignName ? eventDetails.campaignName : 'Unnamed_Campaign'
      };
    });

    const headers = Object.keys(exportData[0]).join(",");
    const rows = exportData.map(row => 
      Object.values(row).map(val => `"${val}"`).join(",")
    ).join("\n");
    
    const csvContent = `${headers}\n${rows}`;
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `${eventDetails.campaignName || 'San_Mateo'}_Field_Export.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div style={{ position: 'relative', height: '100vh', width: '100vw', margin: 0, padding: 0, overflow: 'hidden' }}>
      
      <button 
        onClick={() => setIsSidebarOpen(!isSidebarOpen)}
        style={{
          position: 'absolute', top: '15px', left: isSidebarOpen ? '335px' : '15px', zIndex: 1001,
          background: '#2d3748', color: 'white', border: 'none', borderRadius: '4px', padding: '10px 15px',
          cursor: 'pointer', transition: 'left 0.3s ease', boxShadow: '0 2px 5px rgba(0,0,0,0.3)'
        }}
      >
        ☰ {isSidebarOpen ? 'Hide' : 'Menu'}
      </button>

      <div style={{
        position: 'absolute', top: 0, left: isSidebarOpen ? 0 : '-320px', zIndex: 1000,
        width: '320px', height: '100vh', background: 'rgba(255, 255, 255, 0.98)',
        boxShadow: '4px 0 15px rgba(0,0,0,0.15)', transition: 'left 0.3s ease',
        overflowY: 'auto', padding: '60px 20px 20px 20px', boxSizing: 'border-box', fontFamily: 'sans-serif'
      }}>
        
        <div style={{ marginBottom: '30px', paddingBottom: '20px', borderBottom: '1px solid #e2e8f0' }}>
          <h3 style={{ margin: '0 0 15px 0', color: '#2d3748' }}>1. Campaign Settings</h3>
          {!isEventActive ? (
            <form onSubmit={handleStartCampaign}>
              <label style={{ fontSize: '12px', fontWeight: 'bold' }}>Campaign Name:</label>
              <input type="text" name="campaignName" value={eventDetails.campaignName} onChange={handleInputChange} required style={{ width: '100%', marginBottom: '10px', padding: '5px', boxSizing: 'border-box' }} />

              <div style={{ display: 'flex', gap: '10px' }}>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '12px', fontWeight: 'bold' }}>Start:</label>
                  <input type="date" name="startDate" value={eventDetails.startDate} onChange={handleInputChange} required style={{ width: '100%', marginBottom: '10px', padding: '5px', boxSizing: 'border-box' }} />
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '12px', fontWeight: 'bold' }}>End:</label>
                  <input type="date" name="endDate" value={eventDetails.endDate} onChange={handleInputChange} required style={{ width: '100%', marginBottom: '10px', padding: '5px', boxSizing: 'border-box' }} />
                </div>
              </div>

              <label style={{ fontSize: '12px', fontWeight: 'bold' }}>Select Target Species:</label>
              <div style={{ background: '#f7fafc', padding: '10px', borderRadius: '4px', border: '1px solid #cbd5e0', marginBottom: '10px', maxHeight: '180px', overflowY: 'auto' }}>
                {availableSpecies.map(sp => (
                  <label key={sp} style={{ display: 'block', fontSize: '13px', margin: '6px 0', cursor: 'pointer', color: '#4a5568' }}>
                    <input 
                      type="checkbox" 
                      checked={Array.isArray(eventDetails.targetSpecies) && eventDetails.targetSpecies.includes(sp)}
                      onChange={() => handleSpeciesCheckbox(sp)}
                      style={{ marginRight: '8px' }}
                    />
                    {sp}
                  </label>
                ))}
              </div>

              <label style={{ fontSize: '12px', fontWeight: 'bold' }}>Assigned Unit:</label>
              <input type="text" name="personnel" value={eventDetails.personnel} onChange={handleInputChange} required style={{ width: '100%', marginBottom: '15px', padding: '5px', boxSizing: 'border-box' }} />

              <button type="submit" style={{ width: '100%', padding: '10px', background: '#4CAF50', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>
                Start Campaign
              </button>
            </form>
          ) : (
            <div>
              <h4 style={{ color: '#4CAF50', margin: '0 0 10px 0' }}>{eventDetails.campaignName} (Active)</h4>
              <p style={{ margin: '5px 0', fontSize: '14px' }}>
                <strong>Intercropping:</strong><br/>
                {Array.isArray(eventDetails.targetSpecies) ? eventDetails.targetSpecies.join(' + ') : 'None'}
              </p>
              <button onClick={() => { setIsEventActive(false); setDrawnZone(null); }} style={{ width: '100%', padding: '8px', background: '#f44336', color: 'white', border: 'none', borderRadius: '4px', marginTop: '10px', cursor: 'pointer', fontWeight: 'bold' }}>
                End Campaign & Reset
              </button>
            </div>
          )}
        </div>

        <div style={{ 
          marginBottom: '30px', paddingBottom: '20px', borderBottom: '1px solid #e2e8f0',
          opacity: isEventActive ? 1 : 0.4, pointerEvents: isEventActive ? 'auto' : 'none', transition: 'all 0.3s ease'
        }}>
          <h3 style={{ margin: '0 0 15px 0', color: '#2d3748' }}>2. Area Selection</h3>
          
          <div style={{ display: 'flex', gap: '15px', marginBottom: '15px', fontSize: '13px' }}>
            <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px' }}>
              <input type="radio" checked={zoneMode === 'draw'} onChange={() => setZoneMode('draw')} /> Map Draw
            </label>
            <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px' }}>
              <input type="radio" checked={zoneMode === 'manual'} onChange={() => setZoneMode('manual')} /> Manual GPS
            </label>
          </div>

          {!drawnZone ? (
            <>
              {zoneMode === 'draw' && (
                <button 
                  onClick={() => setIsDrawingPolygon(!isDrawingPolygon)} 
                  style={{ width: '100%', padding: '10px', background: isDrawingPolygon ? '#f6ad55' : '#3182ce', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}
                >
                  {isDrawingPolygon ? 'Cancel Drawing...' : '▱ Draw Polygon on Map'}
                </button>
              )}

              {zoneMode === 'manual' && (
                <div>
                  <div style={{ fontSize: '11px', color: '#718096', marginBottom: '8px' }}>Enter minimum 3 coordinate pairs (Lat, Lng)</div>
                  {manualFields.map((field, i) => (
                    <div key={i} style={{ display: 'flex', gap: '5px', marginBottom: '8px' }}>
                      <input type="number" placeholder="Lat" value={field.lat} onChange={(e) => updateManualField(i, 'lat', e.target.value)} style={{ flex: 1, padding: '6px', fontSize: '12px', border: '1px solid #cbd5e0', borderRadius: '4px' }} />
                      <input type="number" placeholder="Lng" value={field.lng} onChange={(e) => updateManualField(i, 'lng', e.target.value)} style={{ flex: 1, padding: '6px', fontSize: '12px', border: '1px solid #cbd5e0', borderRadius: '4px' }} />
                      {manualFields.length > 3 ? (
                        <button onClick={() => removeManualField(i)} style={{ background: '#fc8181', color: 'white', border: 'none', borderRadius: '4px', padding: '0 10px', cursor: 'pointer' }}>✕</button>
                      ) : (
                        <div style={{ width: '31px' }}></div> 
                      )}
                    </div>
                  ))}
                  <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                    <button onClick={addManualField} style={{ flex: 1, padding: '8px', background: '#edf2f7', color: '#2d3748', border: '1px solid #cbd5e0', borderRadius: '4px', cursor: 'pointer', fontSize: '12px', fontWeight: 'bold' }}>+ Point</button>
                    <button onClick={handleManualZoneSubmit} style={{ flex: 2, padding: '8px', background: '#3182ce', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px', fontWeight: 'bold' }}>Apply</button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div style={{ padding: '12px', background: '#f0fff4', border: '1px solid #9ae6b4', borderRadius: '4px' }}>
              <div style={{ color: '#276749', fontWeight: 'bold', marginBottom: '8px', fontSize: '14px', textAlign: 'center' }}>✓ Area Selected</div>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button onClick={() => setIsEditingZone(!isEditingZone)} style={{ flex: 1, padding: '6px', background: isEditingZone ? '#ed8936' : '#3182ce', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' }}>
                  {isEditingZone ? 'Save Shape' : 'Edit Shape'}
                </button>
                <button onClick={handleClearZone} style={{ flex: 1, padding: '6px', background: '#fff', color: '#e53e3e', border: '1px solid #fc8181', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' }}>
                  Clear Area
                </button>
              </div>
            </div>
          )}
        </div>

        <div style={{ 
          marginBottom: '30px',
          opacity: (isEventActive && drawnZone) ? 1 : 0.4, pointerEvents: (isEventActive && drawnZone) ? 'auto' : 'none', transition: 'all 0.3s ease'
        }}>
          <h3 style={{ margin: '0 0 15px 0', color: '#2d3748' }}>3. Field Export</h3>
          <p style={{ fontSize: '12px', color: '#718096', marginBottom: '15px' }}>
            Download isolated planting sites for offline GPS navigation (Avenza Maps, Mapinr).
          </p>
          <button 
            onClick={handleExportCSV}
            style={{ width: '100%', padding: '10px', background: '#38a169', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', boxShadow: '0 2px 4px rgba(0,0,0,0.2)' }}
          >
            ↓ Download CSV (Offline GPS)
          </button>
        </div>
      </div>

      <div style={{
        position: 'absolute', top: 15, right: 15, zIndex: 1000,
        background: 'rgba(255, 255, 255, 0.95)', padding: '12px 18px',
        borderRadius: '8px', boxShadow: '0 2px 10px rgba(0,0,0,0.25)', fontFamily: 'sans-serif', minWidth: '200px'
      }}>
        <h4 style={{ margin: '0 0 8px 0', color: '#2d3748' }}>San Mateo DSS Dashboard</h4>
        <div>Active Points: <strong>{activePoints.length}</strong></div>
        <div style={{ color: 'green' }}>Verified Sites: <strong>{stats.verified}</strong></div>
        <div style={{ color: 'red' }}>Flagged Paved: <strong>{stats.rejected}</strong></div>
        
        <hr style={{ margin: '10px 0' }} />
        <div style={{ fontSize: '12px', color: '#4a5568' }}>
          <strong>Cursor Location:</strong><br />
          <span id="cursor-display">Hover over map...</span>
        </div>
        {loading && <div style={{ color: '#4a5568', marginTop: 6 }}><em>Loading spatial grid...</em></div>}
      </div>

      <MapContainer center={[14.6983, 121.1185]} zoom={13} minZoom={12} maxBounds={sanMateoBounds} maxBoundsViscosity={1.0} style={{ height: '100%', width: '100%' }} preferCanvas={true} zoomControl={false}>
        <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" attribution="&copy; Esri &mdash; World Imagery" />
        <CursorTracker />
        
        <MapToolController isDrawingPolygon={isDrawingPolygon} setIsDrawingPolygon={setIsDrawingPolygon} drawnZone={drawnZone} setDrawnZone={setDrawnZone} isEditingZone={isEditingZone} setIsEditingZone={setIsEditingZone} />

        {activePoints.map((pt) => {
          const ptId = pt.stableId;
          const currentStatus = pointStatuses[ptId];
          const displayId = typeof ptId === 'string' ? ptId.replace('pt_', '') : ptId;
          
          const markerColor = currentStatus === 'rejected' ? '#718096' : pt.analysis.color;

          return (
            <CircleMarker
              key={ptId} center={[pt.lat, pt.lng]} radius={4} interactive={!isDrawingPolygon && !isEditingZone}
              pathOptions={{ color: markerColor, fillColor: markerColor, fillOpacity: 0.8 }}
            >
              <Tooltip direction="top" offset={[0, -5]} opacity={1}>
                <strong>ID:</strong> {displayId} <br/>
                {hasSpeciesSelected ? `Agroforestry Score: ${pt.analysis.score}%` : 'Click for details'}
                {currentStatus === 'rejected' && ' (FLAGGED)'}
              </Tooltip>
              
              <Popup>
                <div style={{ fontFamily: 'sans-serif', minWidth: '220px' }}>
                  <h4 style={{ margin: '0 0 5px 0', color: '#2d3748' }}>Site Analytics</h4>
                  <strong>Point ID:</strong> {displayId}<br />
                  <div style={{ fontSize: '13px', marginTop: '8px' }}>
                    <strong>Elevation:</strong> {pt.analysis.elev.toFixed(1)}m<br />
                    <strong>Slope:</strong> {pt.analysis.slope.toFixed(1)}°<br />
                    <strong>Soil pH:</strong> {pt.analysis.ph.toFixed(2)}<br />
                    <strong>Soil Type:</strong> {pt.analysis.soil}<br />
                  </div>
                  <hr style={{ margin: '8px 0' }} />
                  
                  {hasSpeciesSelected ? (
                    <div style={{ marginBottom: '10px' }}>
                      <strong>Agroforestry Viability:</strong>
                      <div style={{ fontSize: '18px', fontWeight: 'bold', color: pt.analysis.color, marginBottom: '8px' }}>
                        {pt.analysis.score}% ({pt.analysis.status})
                      </div>
                      
                      <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Species Breakdown:</div>
                      {pt.analysis.breakdown.map((b, i) => (
                        <div key={i} style={{ marginBottom: '6px', background: '#f7fafc', padding: '4px', borderRadius: '4px' }}>
                          <span style={{ fontWeight: 'bold' }}>{b.species}:</span> {b.score}%
                          <ul style={{ margin: '2px 0 0 0', paddingLeft: '18px', fontSize: '10px', color: '#555' }}>
                            {b.reasons.map((r, ri) => <li key={ri}>{r}</li>)}
                          </ul>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ marginBottom: '15px', color: '#718096', fontStyle: 'italic', fontSize: '12px', textAlign: 'center' }}>
                      Select target species to view viability scores.
                    </div>
                  )}

                  <div style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #e2e8f0' }}>
                    
                    {!currentStatus && (
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button onClick={() => handlePointVerification(pt, 'verified')} style={{ flex: 1, padding: '6px', background: '#38a169', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '11px', fontWeight: 'bold' }}>
                          ✓ Verify Plantable
                        </button>
                        <button onClick={() => handlePointVerification(pt, 'rejected')} style={{ flex: 1, padding: '6px', background: '#e53e3e', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '11px', fontWeight: 'bold' }}>
                          ✕ Flag Paved
                        </button>
                      </div>
                    )}

                    {currentStatus === 'verified' && (
                      <div>
                        <div style={{ color: '#38a169', fontWeight: 'bold', marginBottom: '8px', fontSize: '12px', textAlign: 'center' }}>✅ Verified as Plantable</div>
                        <button onClick={() => handlePointVerification(pt, 'rejected')} style={{ width: '100%', padding: '6px', background: '#e53e3e', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '11px', fontWeight: 'bold' }}>
                          Flag as Paved/Obstructed
                        </button>
                      </div>
                    )}

                    {currentStatus === 'rejected' && (
                      <div>
                        <div style={{ color: '#e53e3e', fontWeight: 'bold', marginBottom: '8px', fontSize: '12px', textAlign: 'center' }}>❌ Flagged as Paved</div>
                        <button onClick={() => handlePointVerification(pt, 'verified')} style={{ width: '100%', padding: '6px', background: '#38a169', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '11px', fontWeight: 'bold' }}>
                          Clear Flag & Mark Plantable
                        </button>
                      </div>
                    )}

                  </div>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}

export default App;