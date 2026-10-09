// The data of zoneColors.json as a module (the browser build and node read this file; the JSON is read by Python; fieldStatus.test.mjs checks that the two are the same).
export const ZONE_TABLE = {
  "note": "ONE colours module for the optional Zoning overlay. Colours follow the LGU style file (Landuse-1.qml) as given by the project team in round 15c; Sanitary Landfill, Major Commercial - Mixed Use and the outside-the-map swatch are not styled in that file. Fill is drawn at low opacity with a thin outline so it never hides the suitability dots.",
  "fill_opacity": 0.2,
  "line_weight": 0.8,
  "colors": {
    "Forest Zone": {
      "color": "#006400",
      "name": "dark green",
      "source": "LGU style file (Landuse-1.qml)"
    },
    "Buffer Zone": {
      "color": "#32e132",
      "name": "bright green",
      "source": "LGU style file (Landuse-1.qml)"
    },
    "Cemetery Zone": {
      "color": "#64e164",
      "name": "light green",
      "source": "LGU style file (Landuse-1.qml)"
    },
    "Agricultural Zone": {
      "color": "#64e164",
      "name": "light green",
      "source": "LGU style file (Landuse-1.qml)",
      "hatch": "blue 45-degree lines"
    },
    "Parks and Recreation Zone": {
      "color": "#d2856b",
      "name": "salmon",
      "source": "LGU style file (Landuse-1.qml)"
    },
    "Quarry Sub-Zone": {
      "color": "#993300",
      "name": "brown",
      "source": "LGU style file (Landuse-1.qml)"
    },
    "Special Reserved Zone": {
      "color": "#bebebe",
      "name": "light gray",
      "source": "LGU style file (Landuse-1.qml)"
    },
    "High Density Residential - Mixed Use Zone": {
      "color": "#ffff00",
      "name": "yellow",
      "source": "LGU style file (Landuse-1.qml)"
    },
    "Medium Density Residential Zone": {
      "color": "#ffff00",
      "name": "yellow",
      "source": "LGU style file (Landuse-1.qml)"
    },
    "Socialized Housing Zone": {
      "color": "#ffff00",
      "name": "yellow",
      "source": "LGU style file (Landuse-1.qml)"
    },
    "Institutional Research Zone": {
      "color": "#0000ff",
      "name": "blue",
      "source": "LGU style file (Landuse-1.qml)"
    },
    "General Institutional Zone": {
      "color": "#0000ff",
      "name": "blue",
      "source": "LGU style file (Landuse-1.qml)"
    },
    "General Institutional Zonec": {
      "color": "#0000ff",
      "name": "blue",
      "source": "LGU style file (Landuse-1.qml)"
    },
    "Minor Commercial - Mixed Use Zone": {
      "color": "#ff0000",
      "name": "red",
      "source": "LGU style file (Landuse-1.qml)"
    },
    "Major Commercial Zone": {
      "color": "#ff0000",
      "name": "red",
      "source": "LGU style file (Landuse-1.qml)"
    },
    "Major Commercial - Mixed Use Zone": {
      "color": "#8b0000",
      "name": "dark red",
      "source": "not styled in the LGU file: our choice"
    },
    "Light Industrial Zone": {
      "color": "#9600c8",
      "name": "purple",
      "source": "LGU style file (Landuse-1.qml)"
    },
    "Medium Industrial Zone": {
      "color": "#9600c8",
      "name": "purple",
      "source": "LGU style file (Landuse-1.qml)"
    },
    "Sanitary Landfill": {
      "color": "#4d4d4d",
      "name": "dark gray",
      "source": "not styled in the LGU file: our choice"
    }
  },
  "fallback": {
    "color": "#9e9e9e",
    "name": "gray"
  },
  "outside_map": {
    "color": "#ffffff",
    "name": "white dashed outline"
  },
  "credit": "Colours follow the LGU style file (Landuse-1.qml)",
  "unstyled_note": "Not in the LGU style file (our choice): Sanitary Landfill (dark gray), Major Commercial - Mixed Use (dark red) and the outside-the-map outline."
}
