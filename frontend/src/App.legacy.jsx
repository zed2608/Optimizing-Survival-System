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

// 2. REVERSE GEOCODING COMPONENT (Powered by Esri ArcGIS)
const geocodePromiseCache = new Map(); 

function LocationDisplay({ lat, lng }) {
  const [address, setAddress] = useState("Fetching location...");

  useEffect(() => {
    const cacheKey = `${lat.toFixed(5)},${lng.toFixed(5)}`;
    if (geocodePromiseCache.has(cacheKey)) {
      geocodePromiseCache.get(cacheKey)
        .then(setAddress)
        .catch(() => setAddress("Location unavailable"));
      return;
    }

    const url = `https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/reverseGeocode?location=${lng},${lat}&f=json`;
    
    const fetchPromise = fetch(url)
      .then(res => {
        if (!res.ok) throw new Error("Network response was not ok");
        return res.json();
      })
      .then(data => {
        if (data && data.address) {
          const addr = data.address;
          const neighborhood = addr.Neighborhood || ''; 
          const city = addr.City || 'San Mateo';
          const matchAddr = addr.Match_addr || ''; 
          
          if (neighborhood && neighborhood !== city) {
              return `Brgy. ${neighborhood}, ${city}`;
          } else if (matchAddr) {
              return matchAddr.replace(', PHL', '').replace(/, \d{4}$/, '');
          }
          return city;
        }
        return "Unmapped Forest/Watershed Area";
      });

    geocodePromiseCache.set(cacheKey, fetchPromise);
    fetchPromise.then(setAddress).catch(() => setAddress("Location unavailable"));
  }, [lat, lng]);

  return <span style={{ color: '#38bdf8', fontWeight: '700' }}>{address}</span>;
}

// 3. PROGRAMMATIC MAP TOOL CONTROLLER
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
        style: { color: '#38bdf8', weight: 2, fillOpacity: 0.2 },
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
      shapeOptions: { color: '#38bdf8', weight: 2, fillOpacity: 0.25, interactive: false }
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

// 4. STRICT DSS SCORING ENGINE 
const speciesRules = {
  "Narra": { minElev: 0, maxElev: 1000, maxSlope: 30, minPh: 5.0, maxPh: 7.5, soil: "Alluvial Clay, Clay-Loam", drought: "High", water: "Medium", optimal_planting_months: [5, 6, 7], deployment_stage: "Sapling (6-8 mos)", climate_risk_notes: "High mortality if planted peak dry season." },
  "Molave": { minElev: 0, maxElev: 700, maxSlope: 60, minPh: 6.0, maxPh: 8.5, soil: "Limestone-Based, Sandy-Clay", drought: "High", water: "Low", optimal_planting_months: [5, 6], deployment_stage: "Sapling (6 mos)", climate_risk_notes: "Highly drought resistant once established." },
  "Dao": { minElev: 0, maxElev: 800, maxSlope: 45, minPh: 5.5, maxPh: 7.5, soil: "Alluvial Clay, Volcanic Loam", drought: "Medium", water: "High", optimal_planting_months: [6, 7, 8], deployment_stage: "Sapling (8 mos)", climate_risk_notes: "Tolerates heavy monsoon rains." },
  "Banaba": { minElev: 0, maxElev: 800, maxSlope: 15, minPh: 5.0, maxPh: 7.0, soil: "Clay-Loam, Alluvial Clay", drought: "Medium", water: "High", optimal_planting_months: [6, 7], deployment_stage: "Sapling (4-6 mos)", climate_risk_notes: "Requires consistent moisture early on." },
  "Bitaog": { minElev: 0, maxElev: 500, maxSlope: 20, minPh: 5.5, maxPh: 8.0, soil: "Sandy-Clay, Alluvial Clay", drought: "High", water: "High", optimal_planting_months: [5, 6, 7], deployment_stage: "Seedling/Sapling", climate_risk_notes: "Typhoon and wind resistant." },
  "Kalumpit": { minElev: 0, maxElev: 600, maxSlope: 45, minPh: 5.0, maxPh: 7.5, soil: "Clay-Loam, Ridge Clay", drought: "Medium", water: "Medium", optimal_planting_months: [6, 7, 8], deployment_stage: "Sapling", climate_risk_notes: "Needs protection from extreme drought." },
  "Duhat": { minElev: 0, maxElev: 1200, maxSlope: 30, minPh: 5.5, maxPh: 7.5, soil: "Alluvial Clay, Clay-Loam", drought: "High", water: "High", optimal_planting_months: [5, 6, 7, 8], deployment_stage: "Sapling (6 mos)", climate_risk_notes: "Highly adaptable to extreme weather." },
  "Kamagong": { minElev: 0, maxElev: 800, maxSlope: 45, minPh: 5.5, maxPh: 7.5, soil: "Ridge Clay, Volcanic Loam", drought: "High", water: "Low", optimal_planting_months: [5, 6, 7], deployment_stage: "Sapling (8-10 mos)", climate_risk_notes: "Vulnerable to root rot in heavy floods." },
  "Katmon": { minElev: 0, maxElev: 800, maxSlope: 45, minPh: 5.0, maxPh: 6.5, soil: "Clay-Loam, Volcanic Loam", drought: "Low", water: "Medium", optimal_planting_months: [7, 8, 9], deployment_stage: "Sapling", climate_risk_notes: "Needs high humidity; avoid El Niño planting." },
  "Batikuling": { minElev: 100, maxElev: 1000, maxSlope: 45, minPh: 5.5, maxPh: 7.0, soil: "Volcanic Loam, Clay-Loam", drought: "Medium", water: "Low", optimal_planting_months: [6, 7, 8], deployment_stage: "Sapling", climate_risk_notes: "Avoid planting in waterlogged lowlands." },
  "Palosapis": { minElev: 0, maxElev: 1000, maxSlope: 45, minPh: 5.0, maxPh: 6.5, soil: "Ridge Clay, Volcanic Loam", drought: "Low", water: "Low", optimal_planting_months: [7, 8], deployment_stage: "Sapling (6-8 mos)", climate_risk_notes: "Requires shaded nursing before field deployment." },
  "Talisay": { minElev: 0, maxElev: 400, maxSlope: 15, minPh: 5.5, maxPh: 8.5, soil: "Sandy-Clay, Alluvial Clay", drought: "High", water: "High", optimal_planting_months: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], deployment_stage: "Seedling", climate_risk_notes: "Extremely hardy; coastal/typhoon resistant." },
  "Bamboo": { minElev: 0, maxElev: 1000, maxSlope: 70, minPh: 5.0, maxPh: 8.0, soil: "Alluvial Clay, Clay-Loam", drought: "High", water: "High", optimal_planting_months: [5, 6, 7, 8], deployment_stage: "Culm Cutting/Rhizome", climate_risk_notes: "Best planted before peak monsoon for rapid growth." },
  "Langka": { minElev: 0, maxElev: 1000, maxSlope: 25, minPh: 5.5, maxPh: 7.5, soil: "Volcanic Loam, Clay-Loam", drought: "Medium", water: "Low", optimal_planting_months: [5, 6, 7], deployment_stage: "Sapling (6 mos)", climate_risk_notes: "Avoid flood-prone areas during monsoon." },
  "Guyabano": { minElev: 0, maxElev: 1000, maxSlope: 25, minPh: 5.5, maxPh: 6.5, soil: "Clay-Loam, Sandy-Clay", drought: "Medium", water: "Low", optimal_planting_months: [5, 6, 7], deployment_stage: "Sapling", climate_risk_notes: "Wind protection needed in early stages." },
  "Atsuete": { minElev: 0, maxElev: 1000, maxSlope: 25, minPh: 5.5, maxPh: 7.5, soil: "Clay-Loam, Volcanic Loam", drought: "High", water: "Low", optimal_planting_months: [5, 6], deployment_stage: "Sapling/Seedling", climate_risk_notes: "Requires full sun; avoid waterlogged soils." },
  "Cacao": { minElev: 0, maxElev: 800, maxSlope: 20, minPh: 5.0, maxPh: 7.5, soil: "Volcanic Loam, Clay-Loam", drought: "Low", water: "Low", optimal_planting_months: [7, 8, 9], deployment_stage: "Sapling (6 mos)", climate_risk_notes: "Requires shade trees (e.g. Banana) early on." },
  "Rambutan": { minElev: 0, maxElev: 600, maxSlope: 20, minPh: 5.0, maxPh: 6.5, soil: "Clay-Loam, Volcanic Loam", drought: "Low", water: "Low", optimal_planting_months: [6, 7, 8], deployment_stage: "Grafted Sapling", climate_risk_notes: "Highly sensitive to prolonged drought (El Niño)." },
  "Kasoy": { minElev: 0, maxElev: 700, maxSlope: 25, minPh: 5.0, maxPh: 8.0, soil: "Sandy-Clay, Limestone-Based", drought: "High", water: "Low", optimal_planting_months: [5, 6, 7], deployment_stage: "Seedling", climate_risk_notes: "Thrives in dry conditions; rots in standing water." },
  "Sampalok": { minElev: 0, maxElev: 1000, maxSlope: 25, minPh: 5.5, maxPh: 8.5, soil: "Sandy-Clay, Clay-Loam", drought: "High", water: "Low", optimal_planting_months: [5, 6, 7], deployment_stage: "Sapling", climate_risk_notes: "Very wind resistant." },
  "Yakal": { minElev: 100, maxElev: 800, maxSlope: 45, minPh: 5.0, maxPh: 6.5, soil: "Ridge Clay, Volcanic Loam", drought: "Low", water: "Low", optimal_planting_months: [6, 7, 8], deployment_stage: "Sapling (8 mos)", climate_risk_notes: "Requires stable soil moisture; vulnerable to dry spells." },
  "Mango": { minElev: 0, maxElev: 1200, maxSlope: 25, minPh: 5.5, maxPh: 7.5, soil: "Volcanic Loam, Clay-Loam, Alluvial Clay", drought: "High", water: "Medium", optimal_planting_months: [5, 6, 7], deployment_stage: "Grafted Sapling", climate_risk_notes: "Needs dry season for flowering; wet season for early growth." }
};

const calculateSuitability = (species, pt, targetMonth = null) => {
  const elev = parseFloat(pt.elevation_) || parseFloat(pt.elevation) || 0;
  const ph = parseFloat(pt.soil_ph) || 7;
  const slope = parseFloat(pt.slope_1) || parseFloat(pt.slope) || 0;
  const ptSoil = String(pt.soil_type || pt.soil || 'Unknown').trim();

  let score = 100;
  let reasons = []; 
  
  const rules = speciesRules[species];
  if (!rules) return { score: 0, elev, ph, slope, soil: ptSoil, reasons: ["Species data missing."]};

  if (elev < rules.minElev) {
      score -= 25; reasons.push(`Elevation too low (Min: ${rules.minElev}m) (-25%)`);
  } else if (elev > rules.maxElev) {
      score -= 25; reasons.push(`Elevation too high (Max: ${rules.maxElev}m) (-25%)`);
  } else if (elev > rules.maxElev * 0.8) {
      score -= 10; reasons.push(`Elevation near upper limit (-10%)`);
  }

  if (elev > 400 && rules.drought === "Low") {
      score -= 20; reasons.push(`High-elevation drought risk for this species (-20%)`);
  }

  if (slope > rules.maxSlope) {
      score -= 30; reasons.push(`Slope too steep (Max: ${rules.maxSlope}°) (-30%)`);
  } else if (slope > rules.maxSlope * 0.75) {
      score -= 10; reasons.push(`Moderate slope limitation (-10%)`);
  }

  if (slope < 5 && rules.water === "Low") {
      score -= 25; reasons.push(`High root-rot risk in flat terrain (-25%)`);
  }

  if (ph < rules.minPh || ph > rules.maxPh) {
      score -= 15; reasons.push(`Suboptimal pH (Ideal: ${rules.minPh}-${rules.maxPh}) (-15%)`);
  }

  const ptSoilLower = ptSoil.toLowerCase();
  const allowedSoilsLower = rules.soil.toLowerCase();
  
  if (ptSoilLower === 'unknown' || ptSoilLower === '') {
      score -= 10; reasons.push(`Unknown soil type safety penalty (-10%)`);
  } else {
      const isPointClay = ptSoilLower.includes('clay');
      const isPointSand = ptSoilLower.includes('sand');
      const isPointLoam = ptSoilLower.includes('loam');
      
      const needsClay = allowedSoilsLower.includes('clay');
      const needsSand = allowedSoilsLower.includes('sand');
      const needsLoam = allowedSoilsLower.includes('loam');

      let hasConflict = false;
      if (isPointSand && !needsSand && (needsClay || needsLoam)) hasConflict = true;
      if (isPointClay && !needsClay && (needsSand)) hasConflict = true;

      if (hasConflict) {
          score -= 30; reasons.push(`Definitive soil conflict: ${ptSoil} (-30%)`);
      } else if (!isPointClay && !isPointSand && !isPointLoam) {
          score -= 10; reasons.push(`Unverified local soil texture (${ptSoil}) (-10%)`);
      }
  }

  if (targetMonth !== null && rules.optimal_planting_months) {
      if (!rules.optimal_planting_months.includes(targetMonth)) {
          score -= 20;
          reasons.push(`Off-Season Planting Risk: High mortality if planted in Month ${targetMonth}. (-20%)`);
      }
  }

  if (reasons.length === 0) reasons.push("✓ Perfect environmental match.");
  score = Math.max(0, Math.min(100, score));

  return { score, elev, ph, slope, soil: ptSoil, reasons, details: rules };
};

const evaluateMultiSpecies = (speciesArray, pt, targetMonth) => {
  if (!speciesArray || speciesArray.length === 0) return null;

  let minScore = 100;
  let combinedResults = [];
  let envStats = {};

  speciesArray.forEach((species, i) => {
    const analysis = calculateSuitability(species, pt, targetMonth);
    if (i === 0) {
      envStats = { elev: analysis.elev, ph: analysis.ph, slope: analysis.slope, soil: analysis.soil };
    }
    if (analysis.score < minScore) minScore = analysis.score;
    
    combinedResults.push({
      species,
      score: analysis.score,
      reasons: analysis.reasons,
      details: analysis.details
    });
  });

  let color = '#ef4444'; 
  let status = 'Poor / High Risk';
  if (minScore >= 80) { color = '#10b981'; status = 'Optimal (S1)'; }
  else if (minScore >= 50) { color = '#f59e0b'; status = 'Moderate / Plantable (S2)'; }

  return { score: minScore, color, status, ...envStats, breakdown: combinedResults };
};

const findBestSpeciesForPoint = (pt, targetMonth) => {
    const allSpecies = Object.keys(speciesRules);
    let results = [];
    
    allSpecies.forEach(sp => {
        const analysis = calculateSuitability(sp, pt, targetMonth);
        results.push({
            species: sp,
            score: analysis.score,
            details: analysis.details
        });
    });

    results.sort((a, b) => b.score - a.score);
    return results.slice(0, 3);
};

const sanMateoBounds = [
  [14.4500, 120.9000], 
  [14.9500, 121.4500]  
];

const formatMonths = (monthArray) => {
    if (!monthArray || monthArray.length === 0) return "Any season";
    const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    if (monthArray.length === 1) return monthNames[monthArray[0] - 1];
    const sorted = [...monthArray].sort((a, b) => a - b);
    return `${monthNames[sorted[0] - 1]} - ${monthNames[sorted[sorted.length - 1] - 1]}`;
};

function App() {
  const today = new Date().toISOString().split('T')[0];
  
  const [points, setPoints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ verified: 0, rejected: 0 });
  const [pointStatuses, setPointStatuses] = useState({}); 
  
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [activeTab, setActiveTab] = useState('studio'); // 'studio' | 'history' | 'analytics'
  const [campaignHistory, setCampaignHistory] = useState([]);

  const [drawnZone, setDrawnZone] = useState(null);
  const [isEditingZone, setIsEditingZone] = useState(false); 
  const [appMode, setAppMode] = useState('mode_a'); 

  const [eventDetails, setEventDetails] = useState({
    campaignName: '', startDate: today, endDate: today, targetSpecies: [], personnel: ''
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

  const handleModeToggle = (newMode) => {
      setAppMode(newMode);
      setEventDetails(prev => ({ ...prev, targetSpecies: [] }));
      setDrawnZone(null);
      setPointStatuses({});
      setStats({ verified: 0, rejected: 0 });
  };

  const hasSpeciesSelected = Array.isArray(eventDetails.targetSpecies) && eventDetails.targetSpecies.length > 0;
  const targetMonth = eventDetails.startDate ? new Date(eventDetails.startDate).getMonth() + 1 : null;

  const activePoints = points.map(pt => {
    const lat = parseFloat(pt.Y ?? pt.y ?? pt.lat ?? pt.latitude);
    const lng = parseFloat(pt.X ?? pt.x ?? pt.lon ?? pt.longitude);
    if (isNaN(lat) || isNaN(lng)) return null;

    if (drawnZone) {
      const turfPoint = turf.point([lng, lat]);
      if (!turf.booleanPointInPolygon(turfPoint, drawnZone)) return null;
    }

    if (appMode === 'mode_a' && hasSpeciesSelected) {
      const analysis = evaluateMultiSpecies(eventDetails.targetSpecies, pt, targetMonth);
      if (!analysis || analysis.score === 0) return null; 
      return { ...pt, lat, lng, analysis };
    } else {
      const topRecommendations = findBestSpeciesForPoint(pt, targetMonth);
      return { 
        ...pt, lat, lng, 
        analysis: { 
          score: 'N/A', color: '#64748b', status: 'Select Species',
          elev: parseFloat(pt.elevation_) || parseFloat(pt.elevation) || 0,
          slope: parseFloat(pt.slope_1) || parseFloat(pt.slope) || 0,
          ph: parseFloat(pt.soil_ph) || 7,
          soil: String(pt.soil_type || pt.soil || 'Unknown').trim(),
          breakdown: []
        },
        oracle: topRecommendations
      };
    }
  }).filter(Boolean);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    if (name === 'startDate' && value < today) {
      alert("Campaign start date cannot be set in the past. Starting from today.");
      return;
    }
    if (name === 'endDate' && value < eventDetails.startDate) {
      alert("Campaign end date cannot be earlier than the start date.");
      return;
    }
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
    if (appMode === 'mode_a' && !hasSpeciesSelected) {
      alert("Please select at least one species by clicking the checkboxes.");
      return;
    }
    setIsEventActive(true);

    const newRecord = {
      id: Date.now(),
      name: eventDetails.campaignName,
      start: eventDetails.startDate,
      end: eventDetails.endDate,
      personnel: eventDetails.personnel,
      species: appMode === 'mode_a' ? [...eventDetails.targetSpecies] : ['Oracle Mode Analysis'],
      status: 'Active'
    };
    setCampaignHistory(prev => [newRecord, ...prev]);
  };

  const handleEndCampaign = () => {
    setIsEventActive(false);
    setDrawnZone(null);
    setCampaignHistory(prev => prev.map(c => c.name === eventDetails.campaignName ? { ...c, status: 'Concluded' } : c));
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
    } catch {
      alert("Invalid coordinates entered.");
    }
  };
  const handleClearZone = () => {
    setDrawnZone(null);
    setIsDrawingPolygon(false);
    setIsEditingZone(false);
  };

  const handleExportCSV = () => {
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

      let targetSpeciesText = '';
      let viabilityText = '';

      if (appMode === 'mode_a') {
          targetSpeciesText = Array.isArray(eventDetails.targetSpecies) ? eventDetails.targetSpecies.join(' + ') : '';
          viabilityText = `${pt.analysis.score}%`;
      } else {
          if (pt.oracle && pt.oracle.length > 0) {
              targetSpeciesText = pt.oracle.map((r, i) => `${i+1}. ${r.species}`).join(' | ');
              viabilityText = pt.oracle.map(r => `${r.score}%`).join(' | ');
          } else {
              targetSpeciesText = 'No recommendations';
              viabilityText = 'N/A';
          }
      }
      
      return {
        Point_ID: typeof ptId === 'string' ? ptId.replace('pt_', '') : ptId,
        Site_Status: statusLabel, 
        Latitude: pt.lat.toFixed(6),
        Longitude: pt.lng.toFixed(6),
        Elevation_m: pt.analysis.elev.toFixed(1),
        Slope_deg: pt.analysis.slope.toFixed(1),
        Soil_pH: pt.analysis.ph.toFixed(2),
        Soil_Type: pt.analysis.soil,
        Target_Species: targetSpeciesText,
        Agroforestry_Viability: viabilityText,
        Campaign: eventDetails.campaignName ? eventDetails.campaignName : 'Unnamed_Campaign'
      };
    });

    const headers = Object.keys(exportData[0]).join(",");
    const rows = exportData.map(row => Object.values(row).map(val => `"${val}"`).join(",")).join("\n");
    
    const blob = new Blob([`${headers}\n${rows}`], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `${eventDetails.campaignName || 'San_Mateo'}_Field_Export.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div style={{ position: 'relative', height: '100vh', width: '100vw', margin: 0, padding: 0, overflow: 'hidden', fontFamily: "'Plus Jakarta Sans', 'Inter', system-ui, sans-serif", backgroundColor: '#090d16' }}>
      
      {/* LOADING OVERLAY SCREEN */}
      {loading && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 9999,
          background: 'rgba(9, 13, 22, 0.85)', backdropFilter: 'blur(24px)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'white',
          animation: 'fadeIn 0.4s ease'
        }}>
          <div style={{
            width: '64px', height: '64px', border: '4px solid rgba(16, 185, 129, 0.2)',
            borderTop: '4px solid #10b981', borderRadius: '50%', animation: 'spin 1s linear infinite', marginBottom: '20px',
            boxShadow: '0 0 20px rgba(16, 185, 129, 0.4)'
          }}></div>
          <div style={{ fontSize: '18px', fontWeight: '700', letterSpacing: '0.5px', marginBottom: '6px' }}>Initializing San Mateo DSS Studio</div>
          <div style={{ fontSize: '13px', color: '#94a3b8' }}>Loading spatial database & environmental vector grids...</div>
          <style>{`
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
          `}</style>
        </div>
      )}

      {/* TOP GLASS NAVIGATION BAR */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: '70px', zIndex: 1100,
        background: 'rgba(15, 23, 42, 0.55)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)', boxShadow: '0 10px 30px rgba(0,0,0,0.3)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 28px', color: 'white', boxSizing: 'border-box'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{ background: 'linear-gradient(135deg, #059669 0%, #34d399 100%)', padding: '8px 14px', borderRadius: '10px', fontWeight: '800', fontSize: '14px', letterSpacing: '0.6px', boxShadow: '0 4px 15px rgba(16, 185, 129, 0.4)', color: '#064e3b' }}>
             LGU SAN MATEO 𖣂︎
          </div>
          <div>
            <div style={{ fontSize: '15px', fontWeight: '700', letterSpacing: '0.3px', color: '#f8fafc' }}>Urban Tree Planting Decision Support System</div>
            <div style={{ fontSize: '11px', color: '#94a3b8', fontWeight: '500' }}>Municipal Environment and Natural Resources Office (MENRO)</div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '6px', background: 'rgba(255, 255, 255, 0.03)', padding: '5px', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
          <button 
            onClick={() => setActiveTab('studio')}
            style={{ padding: '8px 18px', background: activeTab === 'studio' ? 'linear-gradient(135deg, #059669 0%, #10b981 100%)' : 'transparent', color: activeTab === 'studio' ? 'white' : '#94a3b8', border: 'none', borderRadius: '9px', cursor: 'pointer', fontSize: '13px', fontWeight: '700', transition: 'all 0.25s ease', boxShadow: activeTab === 'studio' ? '0 4px 12px rgba(16,185,129,0.3)' : 'none' }}
          >
            𖥠 Active Studio
          </button>
          <button 
            onClick={() => setActiveTab('history')}
            style={{ padding: '8px 18px', background: activeTab === 'history' ? 'linear-gradient(135deg, #059669 0%, #10b981 100%)' : 'transparent', color: activeTab === 'history' ? 'white' : '#94a3b8', border: 'none', borderRadius: '9px', cursor: 'pointer', fontSize: '13px', fontWeight: '700', transition: 'all 0.25s ease', boxShadow: activeTab === 'history' ? '0 4px 12px rgba(16,185,129,0.3)' : 'none' }}
          >
            🕮 Campaign Logs ({campaignHistory.length})
          </button>
          <button 
            onClick={() => setActiveTab('analytics')}
            style={{ padding: '8px 18px', background: activeTab === 'analytics' ? 'linear-gradient(135deg, #059669 0%, #10b981 100%)' : 'transparent', color: activeTab === 'analytics' ? 'white' : '#94a3b8', border: 'none', borderRadius: '9px', cursor: 'pointer', fontSize: '13px', fontWeight: '700', transition: 'all 0.25s ease', boxShadow: activeTab === 'analytics' ? '0 4px 12px rgba(16,185,129,0.3)' : 'none' }}
          >
            🗠 System Analytics
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'rgba(255,255,255,0.03)', padding: '6px 14px', borderRadius: '20px', border: '1px solid rgba(255,255,255,0.06)' }}>
          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: isEventActive ? '#10b981' : '#f59e0b', boxShadow: isEventActive ? '0 0 10px #10b981' : '0 0 8px #f59e0b' }}></div>
          <span style={{ fontSize: '12px', color: '#cbd5e1', fontWeight: '600' }}>{isEventActive ? 'Campaign Live' : 'Standby Mode'}</span>
        </div>
      </div>

      {/* FULLSCREEN HISTORICAL LOGS MODAL */}
      {activeTab === 'history' && (
        <div style={{ position: 'absolute', top: '85px', left: '24px', right: '24px', bottom: '24px', zIndex: 1200, background: 'rgba(15, 23, 42, 0.85)', backdropFilter: 'blur(24px)', borderRadius: '20px', border: '1px solid rgba(255, 255, 255, 0.12)', padding: '36px', color: 'white', overflowY: 'auto', boxShadow: '0 25px 50px rgba(0,0,0,0.5)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
            <div>
              <h2 style={{ margin: 0, fontSize: '24px', fontWeight: '800' }}>Campaign Event Logs & History</h2>
              <p style={{ margin: '6px 0 0 0', color: '#94a3b8', fontSize: '14px' }}>Complete audit trail of all previous and currently deployed municipal reforestation campaigns.</p>
            </div>
            <button onClick={() => setActiveTab('studio')} style={{ background: 'rgba(255,255,255,0.08)', color: 'white', border: '1px solid rgba(255,255,255,0.12)', padding: '10px 20px', borderRadius: '10px', cursor: 'pointer', fontWeight: '700', fontSize: '13px' }}>✕ Close & Return to Map</button>
          </div>

          {campaignHistory.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '80px', color: '#64748b', fontSize: '15px' }}>No campaign events registered yet. Initialize a campaign from the Active Studio panel.</div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '20px' }}>
              {campaignHistory.map(c => (
                <div key={c.id} style={{ background: 'rgba(255, 255, 255, 0.04)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '14px', padding: '24px', position: 'relative' }}>
                  <div style={{ position: 'absolute', top: '24px', right: '24px', padding: '4px 12px', borderRadius: '20px', fontSize: '11px', fontWeight: '700', background: c.status === 'Active' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(148, 163, 184, 0.15)', color: c.status === 'Active' ? '#34d399' : '#94a3b8' }}>
                    {c.status}
                  </div>
                  <h3 style={{ margin: '0 0 10px 0', fontSize: '18px', color: '#f8fafc', fontWeight: '700' }}>{c.name}</h3>
                  <div style={{ fontSize: '13px', color: '#94a3b8', marginBottom: '12px', fontWeight: '500' }}>
                    📅 {c.start} to {c.end}
                  </div>
                  <div style={{ fontSize: '13px', color: '#cbd5e1', marginBottom: '12px' }}>
                    <strong>Assigned Unit:</strong> {c.personnel}
                  </div>
                  <div style={{ fontSize: '12px', background: 'rgba(0,0,0,0.25)', padding: '12px', borderRadius: '8px', color: '#e2e8f0', border: '1px solid rgba(255,255,255,0.04)' }}>
                    <strong>Target Species:</strong> {c.species.join(', ')}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* FULLSCREEN ANALYTICS MODAL */}
      {activeTab === 'analytics' && (
        <div style={{ position: 'absolute', top: '85px', left: '24px', right: '24px', bottom: '24px', zIndex: 1200, background: 'rgba(15, 23, 42, 0.85)', backdropFilter: 'blur(24px)', borderRadius: '20px', border: '1px solid rgba(255, 255, 255, 0.12)', padding: '36px', color: 'white', overflowY: 'auto', boxShadow: '0 25px 50px rgba(0,0,0,0.5)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
            <div>
              <h2 style={{ margin: 0, fontSize: '24px', fontWeight: '800' }}>System Spatial Analytics</h2>
              <p style={{ margin: '6px 0 0 0', color: '#94a3b8', fontSize: '14px' }}>Real-time telemetry and metrics for verified plantable sites vs obstructed urban terrain.</p>
            </div>
            <button onClick={() => setActiveTab('studio')} style={{ background: 'rgba(255,255,255,0.08)', color: 'white', border: '1px solid rgba(255,255,255,0.12)', padding: '10px 20px', borderRadius: '10px', cursor: 'pointer', fontWeight: '700', fontSize: '13px' }}>✕ Close & Return to Map</button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '24px', marginBottom: '30px' }}>
            <div style={{ background: 'rgba(255, 255, 255, 0.04)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '16px', padding: '28px' }}>
              <div style={{ color: '#94a3b8', fontSize: '12px', fontWeight: '700', letterSpacing: '0.5px' }}>TOTAL LOADED GRID POINTS</div>
              <div style={{ fontSize: '42px', fontWeight: '800', marginTop: '12px', color: '#38bdf8' }}>{points.length}</div>
            </div>
            <div style={{ background: 'rgba(255, 255, 255, 0.04)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '16px', padding: '28px' }}>
              <div style={{ color: '#94a3b8', fontSize: '12px', fontWeight: '700', letterSpacing: '0.5px' }}>VERIFIED PLANTABLE SITES</div>
              <div style={{ fontSize: '42px', fontWeight: '800', marginTop: '12px', color: '#34d399' }}>{stats.verified}</div>
            </div>
            <div style={{ background: 'rgba(255, 255, 255, 0.04)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '16px', padding: '28px' }}>
              <div style={{ color: '#94a3b8', fontSize: '12px', fontWeight: '700', letterSpacing: '0.5px' }}>FLAGGED PAVED / OBSTRUCTED</div>
              <div style={{ fontSize: '42px', fontWeight: '800', marginTop: '12px', color: '#f87171' }}>{stats.rejected}</div>
            </div>
          </div>
        </div>
      )}

      {/* SIDEBAR TOGGLE BUTTON */}
      <button 
        onClick={() => setIsSidebarOpen(!isSidebarOpen)}
        style={{
          position: 'absolute', top: '88px', left: isSidebarOpen ? '375px' : '24px', zIndex: 1001,
          background: 'rgba(15, 23, 42, 0.75)', backdropFilter: 'blur(16px)', color: 'white', border: '1px solid rgba(255, 255, 255, 0.12)', 
          borderRadius: '10px', padding: '10px 16px', cursor: 'pointer', transition: 'left 0.3s cubic-bezier(0.4, 0, 0.2, 1)', boxShadow: '0 8px 20px rgba(0,0,0,0.4)', fontWeight: '700', fontSize: '13px'
        }}
      >
        {isSidebarOpen ? '◀ Hide Control Panel' : '▶ Open Control Panel'}
      </button>

      {/* TRUE GLASSMORPHISM CONTROL SIDEBAR */}
      <div style={{
        position: 'absolute', top: '70px', left: isSidebarOpen ? 0 : '-360px', zIndex: 1000,
        width: '350px', height: 'calc(100vh - 70px)', background: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(24px)', WebkitBackdropFilter: 'blur(24px)', borderRight: '1px solid rgba(255, 255, 255, 0.08)',
        transition: 'left 0.3s cubic-bezier(0.4, 0, 0.2, 1)', overflowY: 'auto', padding: '24px', boxSizing: 'border-box', color: '#f8fafc',
        boxShadow: '10px 0 30px rgba(0,0,0,0.4)'
      }}>

        {/* MODE SWITCHER TABS */}
        <div style={{ marginBottom: '24px', background: 'rgba(255, 255, 255, 0.04)', padding: '5px', borderRadius: '12px', display: 'flex', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
            <button 
                onClick={() => handleModeToggle('mode_a')}
                style={{ flex: 1, padding: '10px', background: appMode === 'mode_a' ? 'linear-gradient(135deg, #059669 0%, #10b981 100%)' : 'transparent', color: appMode === 'mode_a' ? 'white' : '#94a3b8', border: 'none', borderRadius: '9px', cursor: 'pointer', fontSize: '12px', fontWeight: '700', transition: '0.2s', boxShadow: appMode === 'mode_a' ? '0 4px 12px rgba(16,185,129,0.3)' : 'none' }}
            >
                Search by Species
            </button>
            <button 
                onClick={() => handleModeToggle('mode_b')}
                style={{ flex: 1, padding: '10px', background: appMode === 'mode_b' ? 'linear-gradient(135deg, #0284c7 0%, #38bdf8 100%)' : 'transparent', color: appMode === 'mode_b' ? 'white' : '#94a3b8', border: 'none', borderRadius: '9px', cursor: 'pointer', fontSize: '12px', fontWeight: '700', transition: '0.2s', boxShadow: appMode === 'mode_b' ? '0 4px 12px rgba(56,189,248,0.3)' : 'none' }}
            >
                Search by Land
            </button>
        </div>
        
        {/* SECTION 1: CAMPAIGN CONFIG */}
        <div style={{ marginBottom: '25px', paddingBottom: '20px', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '15px', color: '#f8fafc', fontWeight: '700', letterSpacing: '0.3px' }}>1. Campaign Settings</h3>
          {!isEventActive ? (
            <form onSubmit={handleStartCampaign}>
              <label style={{ fontSize: '11px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: '6px' }}>Campaign Name</label>
              <input type="text" name="campaignName" value={eventDetails.campaignName} onChange={handleInputChange} required placeholder="e.g. San Mateo Upper Watersheding" style={{ width: '100%', marginBottom: '14px', padding: '11px 14px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '10px', color: 'white', boxSizing: 'border-box', fontSize: '13px' }} />

              <div style={{ display: 'flex', gap: '10px' }}>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '11px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: '6px' }}>Start Date</label>
                  <input type="date" name="startDate" min={today} value={eventDetails.startDate} onChange={handleInputChange} required style={{ width: '100%', marginBottom: '14px', padding: '10px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '10px', color: 'white', boxSizing: 'border-box', fontSize: '12px' }} />
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '11px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: '6px' }}>End Date</label>
                  <input type="date" name="endDate" min={eventDetails.startDate || today} value={eventDetails.endDate} onChange={handleInputChange} required style={{ width: '100%', marginBottom: '14px', padding: '10px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '10px', color: 'white', boxSizing: 'border-box', fontSize: '12px' }} />
                </div>
              </div>

              {appMode === 'mode_a' ? (
                <>
                  <label style={{ fontSize: '11px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: '6px' }}>Select Target Species</label>
                  <div style={{ background: 'rgba(0,0,0,0.25)', padding: '12px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.06)', marginBottom: '14px', maxHeight: '170px', overflowY: 'auto' }}>
                    {availableSpecies.map(sp => (
                      <label key={sp} style={{ display: 'block', fontSize: '13px', margin: '8px 0', cursor: 'pointer', color: '#cbd5e1', fontWeight: '500' }}>
                        <input 
                          type="checkbox" 
                          checked={Array.isArray(eventDetails.targetSpecies) && eventDetails.targetSpecies.includes(sp)}
                          onChange={() => handleSpeciesCheckbox(sp)}
                          style={{ marginRight: '10px', accentColor: '#10b981', transform: 'scale(1.1)' }}
                        />
                        {sp}
                      </label>
                    ))}
                  </div>
                </>
              ) : (
                <div style={{ background: 'rgba(56, 189, 248, 0.1)', padding: '14px', borderRadius: '10px', border: '1px solid rgba(56, 189, 248, 0.2)', marginBottom: '14px', fontSize: '12px', color: '#bae6fd', lineHeight: '1.4' }}>
                    <strong>Oracle Mode Active:</strong> Evaluating top species matches based on environmental criteria and seasonal alignment.
                </div>
              )}

              <label style={{ fontSize: '11px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: '6px' }}>Assigned LGU Unit</label>
              <input type="text" name="personnel" value={eventDetails.personnel} onChange={handleInputChange} required placeholder="e.g. MENRO Field Team Alpha" style={{ width: '100%', marginBottom: '18px', padding: '11px 14px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '10px', color: 'white', boxSizing: 'border-box', fontSize: '13px' }} />

              <button type="submit" style={{ width: '100%', padding: '13px', background: 'linear-gradient(135deg, #059669 0%, #10b981 100%)', color: 'white', border: 'none', borderRadius: '10px', cursor: 'pointer', fontWeight: '700', fontSize: '13px', boxShadow: '0 4px 15px rgba(16, 185, 129, 0.4)', transition: 'transform 0.2s' }}>
                Initialize Campaign
              </button>
            </form>
          ) : (
            <div>
              <div style={{ padding: '16px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '10px', marginBottom: '14px' }}>
                <h4 style={{ color: '#34d399', margin: '0 0 6px 0', fontSize: '15px', fontWeight: '700' }}>{eventDetails.campaignName}</h4>
                <div style={{ fontSize: '12px', color: '#94a3b8' }}>Personnel: {eventDetails.personnel}</div>
              </div>
              <button onClick={handleEndCampaign} style={{ width: '100%', padding: '11px', background: 'linear-gradient(135deg, #dc2626 0%, #ef4444 100%)', color: 'white', border: 'none', borderRadius: '10px', cursor: 'pointer', fontWeight: '700', fontSize: '13px', boxShadow: '0 4px 15px rgba(239, 68, 68, 0.4)' }}>
                End Campaign & Reset
              </button>
            </div>
          )}
        </div>

        {/* SECTION 2: AREA SELECTION */}
        <div style={{ 
          marginBottom: '25px', paddingBottom: '20px', borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          opacity: isEventActive ? 1 : 0.4, pointerEvents: isEventActive ? 'auto' : 'none', transition: 'all 0.3s ease'
        }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '15px', color: '#f8fafc', fontWeight: '700', letterSpacing: '0.3px' }}>2. Area Selection</h3>
          
          <div style={{ display: 'flex', gap: '16px', marginBottom: '16px', fontSize: '13px' }}>
            <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px', color: '#cbd5e1', fontWeight: '500' }}>
              <input type="radio" checked={zoneMode === 'draw'} onChange={() => setZoneMode('draw')} accentColor="#10b981" /> Map Draw
            </label>
            <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px', color: '#cbd5e1', fontWeight: '500' }}>
              <input type="radio" checked={zoneMode === 'manual'} onChange={() => setZoneMode('manual')} accentColor="#10b981" /> Manual GPS
            </label>
          </div>

          {!drawnZone ? (
            <>
              {zoneMode === 'draw' && (
                <button 
                  onClick={() => setIsDrawingPolygon(!isDrawingPolygon)} 
                  style={{ width: '100%', padding: '11px', background: isDrawingPolygon ? '#d97706' : 'rgba(255,255,255,0.08)', color: 'white', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '10px', cursor: 'pointer', fontWeight: '700', fontSize: '13px' }}
                >
                  {isDrawingPolygon ? 'Cancel Drawing...' : '𓂃✍︎ Draw Polygon on Map'}
                </button>
              )}

              {zoneMode === 'manual' && (
                <div>
                  <div style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '8px' }}>Enter minimum 3 coordinate pairs (Lat, Lng)</div>
                  {manualFields.map((field, i) => (
                    <div key={i} style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
                      <input type="number" placeholder="Lat" value={field.lat} onChange={(e) => updateManualField(i, 'lat', e.target.value)} style={{ flex: 1, padding: '8px 10px', fontSize: '12px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: 'white' }} />
                      <input type="number" placeholder="Lng" value={field.lng} onChange={(e) => updateManualField(i, 'lng', e.target.value)} style={{ flex: 1, padding: '8px 10px', fontSize: '12px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: 'white' }} />
                      {manualFields.length > 3 ? (
                        <button onClick={() => removeManualField(i)} style={{ background: '#ef4444', color: 'white', border: 'none', borderRadius: '8px', padding: '0 12px', cursor: 'pointer', fontWeight: '700' }}>✕</button>
                      ) : (
                        <div style={{ width: '33px' }}></div> 
                      )}
                    </div>
                  ))}
                  <div style={{ display: 'flex', gap: '10px', marginTop: '12px' }}>
                    <button onClick={addManualField} style={{ flex: 1, padding: '9px', background: 'rgba(255,255,255,0.08)', color: '#f8fafc', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '8px', cursor: 'pointer', fontSize: '12px', fontWeight: '700' }}>+ Point</button>
                    <button onClick={handleManualZoneSubmit} style={{ flex: 2, padding: '9px', background: '#10b981', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '12px', fontWeight: '700' }}>Apply Zone</button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div style={{ padding: '16px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '10px' }}>
              <div style={{ color: '#34d399', fontWeight: '700', marginBottom: '10px', fontSize: '13px', textAlign: 'center' }}>✓ Bounding Zone Active</div>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button onClick={() => setIsEditingZone(!isEditingZone)} style={{ flex: 1, padding: '9px', background: isEditingZone ? '#d97706' : 'rgba(255,255,255,0.08)', color: 'white', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '8px', cursor: 'pointer', fontSize: '12px', fontWeight: '700' }}>
                  {isEditingZone ? 'Save Shape' : 'Edit Shape'}
                </button>
                <button onClick={handleClearZone} style={{ flex: 1, padding: '9px', background: 'rgba(239, 68, 68, 0.15)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '8px', cursor: 'pointer', fontSize: '12px', fontWeight: '700' }}>
                  Clear Zone
                </button>
              </div>
            </div>
          )}
        </div>

        {/* SECTION 3: FIELD EXPORT */}
        <div style={{ 
          opacity: (isEventActive && drawnZone) ? 1 : 0.4, pointerEvents: (isEventActive && drawnZone) ? 'auto' : 'none', transition: 'all 0.3s ease'
        }}>
          <h3 style={{ margin: '0 0 10px 0', fontSize: '15px', color: '#f8fafc', fontWeight: '700', letterSpacing: '0.3px' }}>3. Field Data Export</h3>
          <p style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '14px', lineHeight: '1.4' }}>
            Download isolated site parameters for Garmin / QGIS field deployment.
          </p>
          <button 
            onClick={handleExportCSV}
            style={{ width: '100%', padding: '13px', background: 'linear-gradient(135deg, #0284c7 0%, #38bdf8 100%)', color: 'white', border: 'none', borderRadius: '10px', cursor: 'pointer', fontWeight: '700', fontSize: '13px', boxShadow: '0 4px 15px rgba(56, 189, 248, 0.4)' }}
          >
            ↓ Export CSV (Offline GPS)
          </button>
        </div>
      </div>

      {/* DASHBOARD FLOATING METRICS OVERLAY */}
      <div style={{
        position: 'absolute', top: '88px', right: '24px', zIndex: 1000,
        background: 'rgba(15, 23, 42, 0.65)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        padding: '18px 22px', borderRadius: '14px', border: '1px solid rgba(255, 255, 255, 0.08)', color: 'white', minWidth: '230px', boxShadow: '0 15px 35px rgba(0,0,0,0.4)'
      }}>
        <h4 style={{ margin: '0 0 10px 0', color: '#f8fafc', fontSize: '13px', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '8px', fontWeight: '700', letterSpacing: '0.3px' }}>San Mateo Live Telemetry</h4>
        <div style={{ fontSize: '13px', display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontWeight: '500' }}>
          <span style={{ color: '#94a3b8' }}>Active Points:</span> <strong>{activePoints.length}</strong>
        </div>
        <div style={{ fontSize: '13px', display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontWeight: '500' }}>
          <span style={{ color: '#34d399' }}>Verified Sites:</span> <strong style={{ color: '#34d399' }}>{stats.verified}</strong>
        </div>
        <div style={{ fontSize: '13px', display: 'flex', justifyContent: 'space-between', marginBottom: '12px', fontWeight: '500' }}>
          <span style={{ color: '#f87171' }}>Flagged Paved:</span> <strong style={{ color: '#f87171' }}>{stats.rejected}</strong>
        </div>
        
        <div style={{ fontSize: '11px', color: '#94a3b8', borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '10px' }}>
          <strong style={{ display: 'block', marginBottom: '2px' }}>Cursor Coordinates:</strong>
          <span id="cursor-display" style={{ fontFamily: 'monospace', color: '#38bdf8', fontSize: '12px' }}>Hover over map...</span>
        </div>
      </div>

      {/* LEAFLET MAP CONTAINER */}
      <MapContainer center={[14.6983, 121.1185]} zoom={13} minZoom={12} maxBounds={sanMateoBounds} maxBoundsViscosity={1.0} style={{ height: '100%', width: '100%' }} preferCanvas={true} zoomControl={false}>
        <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" attribution="&copy; Esri &mdash; World Imagery" />
        <CursorTracker />
        
        <MapToolController isDrawingPolygon={isDrawingPolygon} setIsDrawingPolygon={setIsDrawingPolygon} drawnZone={drawnZone} setDrawnZone={setDrawnZone} isEditingZone={isEditingZone} setIsEditingZone={setIsEditingZone} />

        {activePoints.map((pt) => {
          const ptId = pt.stableId;
          const currentStatus = pointStatuses[ptId];
          const displayId = typeof ptId === 'string' ? ptId.replace('pt_', '') : ptId;
          
          let markerColor = '#94a3b8';
          if (appMode === 'mode_a' && hasSpeciesSelected) {
              markerColor = pt.analysis.color;
          }
          if (currentStatus === 'rejected') markerColor = '#64748b';

          return (
            <CircleMarker
              key={ptId} center={[pt.lat, pt.lng]} radius={4} interactive={!isDrawingPolygon && !isEditingZone}
              pathOptions={{ color: markerColor, fillColor: markerColor, fillOpacity: 0.85, weight: 1 }}
            >
              <Tooltip direction="top" offset={[0, -5]} opacity={1}>
                <strong>ID:</strong> {displayId} <br/>
                {appMode === 'mode_a' && hasSpeciesSelected ? `Agroforestry Score: ${pt.analysis.score}%` : 'Click for Oracle Recommendations'}
                {currentStatus === 'rejected' && ' (FLAGGED)'}
              </Tooltip>
              
              <Popup>
                <div style={{ fontFamily: 'inherit', minWidth: '280px', maxHeight: '380px', overflowY: 'auto', padding: '4px' }}>
                  <h4 style={{ margin: '0 0 8px 0', color: '#0f172a', fontSize: '15px', fontWeight: '800' }}>Site Analytics</h4>
                  
                  <div style={{ marginBottom: '8px', fontSize: '12px', background: '#f1f5f9', padding: '8px', borderRadius: '6px' }}>
                      <strong>Location:</strong> <LocationDisplay lat={pt.lat} lng={pt.lng} /><br />
                      <strong>Point ID:</strong> {displayId}
                  </div>

                  <div style={{ fontSize: '12px', marginBottom: '8px', background: '#f8fafc', padding: '8px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                    <strong>Elevation:</strong> {pt.analysis.elev.toFixed(1)}m<br />
                    <strong>Slope:</strong> {pt.analysis.slope.toFixed(1)}°<br />
                    <strong>Soil pH:</strong> {pt.analysis.ph.toFixed(2)}<br />
                    <strong>Soil Type:</strong> {pt.analysis.soil}<br />
                  </div>

                  <hr style={{ margin: '8px 0', border: 'none', borderTop: '1px solid #e2e8f0' }} />
                  
                  {appMode === 'mode_a' && hasSpeciesSelected && (
                    <div style={{ marginBottom: '10px' }}>
                      <strong>Agroforestry Viability:</strong>
                      <div style={{ fontSize: '16px', fontWeight: '800', color: pt.analysis.color, margin: '4px 0 8px 0' }}>
                        {pt.analysis.score}% ({pt.analysis.status})
                      </div>
                      
                      <div style={{ fontSize: '11px', fontWeight: '700', color: '#475569', textTransform: 'uppercase' }}>Species Breakdown:</div>
                      {pt.analysis.breakdown.map((b, i) => (
                        <div key={i} style={{ marginBottom: '6px', background: '#f8fafc', border: '1px solid #e2e8f0', padding: '6px', borderRadius: '6px' }}>
                          <span style={{ fontWeight: '700', color: '#1e293b' }}>{b.species}:</span> {b.score}%
                          <ul style={{ margin: '2px 0 4px 0', paddingLeft: '16px', fontSize: '10px', color: '#dc2626' }}>
                            {b.reasons.filter(r => !r.includes('✓')).map((r, ri) => <li key={ri}>{r}</li>)}
                          </ul>
                          <div style={{ fontSize: '10px', color: '#475569', background: '#e2e8f0', padding: '4px', borderRadius: '4px' }}>
                              <strong>Stage:</strong> {b.details.deployment_stage}<br/>
                              <strong>Risk:</strong> {b.details.climate_risk_notes}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {appMode === 'mode_b' && pt.oracle && (
                     <div style={{ marginBottom: '10px' }}>
                        <strong style={{ color: '#059669', fontSize: '13px' }}>Oracle Mode: Top Recommendations</strong>
                        <p style={{ fontSize: '10px', margin: '2px 0 6px 0', color: '#64748b' }}>
                           Based on local soil, topography, and seasonal alignment:
                        </p>
                        
                        {pt.oracle.map((rec, i) => (
                            <div key={i} style={{ marginBottom: '6px', borderLeft: `3px solid ${rec.score >= 80 ? '#10b981' : '#f59e0b'}`, paddingLeft: '8px', background: '#f8fafc', padding: '6px' }}>
                                <div style={{ fontWeight: '700', fontSize: '12px', color: '#1e293b' }}>
                                    {i+1}. {rec.species} ({rec.score}%)
                                </div>
                                <div style={{ fontSize: '10px', color: '#475569', marginTop: '2px' }}>
                                    <strong>Season:</strong> {formatMonths(rec.details.optimal_planting_months)} | <strong>Stage:</strong> {rec.details.deployment_stage}
                                </div>
                            </div>
                        ))}
                     </div>
                  )}

                  <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid #e2e8f0' }}>
                    {!currentStatus && (
                      <div style={{ display: 'flex', gap: '6px' }}>
                        <button onClick={() => handlePointVerification(pt, 'verified')} style={{ flex: 1, padding: '8px', background: '#10b981', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '11px', fontWeight: '700' }}>
                          ✓ Verify Plantable
                        </button>
                        <button onClick={() => handlePointVerification(pt, 'rejected')} style={{ flex: 1, padding: '8px', background: '#ef4444', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '11px', fontWeight: '700' }}>
                          ✕ Flag Paved
                        </button>
                      </div>
                    )}

                    {currentStatus === 'verified' && (
                      <div>
                        <div style={{ color: '#10b981', fontWeight: '700', marginBottom: '6px', fontSize: '11px', textAlign: 'center' }}>✅ Verified as Plantable</div>
                        <button onClick={() => handlePointVerification(pt, 'rejected')} style={{ width: '100%', padding: '6px', background: '#ef4444', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '11px', fontWeight: '700' }}>
                          Flag as Paved/Obstructed
                        </button>
                      </div>
                    )}

                    {currentStatus === 'rejected' && (
                      <div>
                        <div style={{ color: '#ef4444', fontWeight: '700', marginBottom: '6px', fontSize: '11px', textAlign: 'center' }}>❌ Flagged as Paved</div>
                        <button onClick={() => handlePointVerification(pt, 'verified')} style={{ width: '100%', padding: '6px', background: '#10b981', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '11px', fontWeight: '700' }}>
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