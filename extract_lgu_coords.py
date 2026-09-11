import os
import xml.etree.ElementTree as ET
import pandas as pd
from pathlib import Path

def parse_gpx(file_path):
    """Parses a GPX file and extracts track points and waypoints."""
    records = []
    farmer_name = file_path.stem.replace("Track_", "").replace(".gpx", "").strip()

    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Handle GPX XML namespace
        namespace = ''
        if root.tag.startswith('{'):
            namespace = root.tag.split('}')[0] + '}'

        # 1. Parse Track Points (<trkpt>)
        for trk in root.findall(f'{namespace}trk'):
            trk_name_elem = trk.find(f'{namespace}name')
            plot_label = trk_name_elem.text if trk_name_elem is not None and trk_name_elem.text else farmer_name

            for trkseg in trk.findall(f'{namespace}trkseg'):
                for trkpt in trkseg.findall(f'{namespace}trkpt'):
                    lat = float(trkpt.attrib['lat'])
                    lon = float(trkpt.attrib['lon'])
                    
                    ele_elem = trkpt.find(f'{namespace}ele')
                    elevation = float(ele_elem.text) if ele_elem is not None and ele_elem.text else None
                    
                    records.append({
                        'farmer_plot': plot_label,
                        'source_file': file_path.name,
                        'latitude': lat,
                        'longitude': lon,
                        'elevation_m': elevation,
                        'point_type': 'boundary_vertex'
                    })

        # 2. Parse Waypoints (<wpt>) if any exist
        for wpt in root.findall(f'{namespace}wpt'):
            lat = float(wpt.attrib['lat'])
            lon = float(wpt.attrib['lon'])
            
            ele_elem = wpt.find(f'{namespace}ele')
            elevation = float(ele_elem.text) if ele_elem is not None and ele_elem.text else None
            
            records.append({
                'farmer_plot': farmer_name,
                'source_file': file_path.name,
                'latitude': lat,
                'longitude': lon,
                'elevation_m': elevation,
                'point_type': 'waypoint'
            })

    except Exception as e:
        print(f"  [!] Error parsing {file_path.name}: {e}")

    return records


def compile_san_mateo_tracks(input_dir, output_file):
    input_path = Path(input_dir)
    
    # Search for GPX files recursively across folders
    gpx_files = list(input_path.rglob("*.gpx")) + list(input_path.rglob("*.GPX"))

    if not gpx_files:
        print(f"[X] No .gpx files found in: {input_path.resolve()}")
        return

    print("==================================================")
    print(f" FOUND {len(gpx_files)} GPX FILES TO PROCESS")
    print("==================================================")

    all_points = []
    for idx, gpx_file in enumerate(gpx_files, 1):
        pts = parse_gpx(gpx_file)
        all_points.extend(pts)
        print(f"[{idx}/{len(gpx_files)}] Parsed {gpx_file.name} -> {len(pts)} points")

    df = pd.DataFrame(all_points)

    if df.empty:
        print("[!] No coordinate points extracted. Check if GPX files contain valid tracks.")
        return

    # Ensure output directory exists
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(output_path, index=False)

    print("\n==================================================")
    print(f" EXTRACTION COMPLETE")
    print(f" Total points collected: {len(df):,}")
    print(f" Unique farmer plots:   {df['farmer_plot'].nunique()}")
    print(f" Saved to:              {output_path.resolve()}")
    print("==================================================")


if __name__ == "__main__":
    SOURCE_DIRECTORY = r"C:\Users\user\Downloads\GIS San Mateo-20260907T090739Z-1-001"
    OUTPUT_CSV = "data/san_mateo_farmland_coordinates.csv"

    compile_san_mateo_tracks(SOURCE_DIRECTORY, OUTPUT_CSV)