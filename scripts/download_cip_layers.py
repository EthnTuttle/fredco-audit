#!/usr/bin/env python3
"""
Download Frederick County CIP-related GIS layers.

Fetches planning, infrastructure, and transportation layers from the County GIS server.
Output: GeoParquet files for spatial analysis in the playground.

Key Layers:
- Future Rt37 Bypass (Layer 20)
- Eastern Road Plan (Layer 21)
- Fire Stations (Layer 31)
- Fire Districts (Layer 32)
- Schools and Districts (Parks service)
- Proffers (Layer 3)

Usage:
    python scripts/download_cip_layers.py
"""

import json
import os
import requests
import geopandas as gpd
from shapely.geometry import shape, Point, LineString, Polygon

# Configuration
PLANNING_BASE = "https://fredcogis.fcva.us/maps/rest/services/FC_Planning/PlanningAccessTerminal/MapServer"
PARKS_BASE = "https://fredcogis.fcva.us/maps/rest/services/FC_Parks/ParksAndRecTerminal/MapServer"
OUTPUT_DIR = "data/processed/gis"

# Layer definitions: (service_base, layer_id, output_name, description)
LAYERS = [
    # Roads and Transportation
    (PLANNING_BASE, 20, "future_rt37_bypass", "Future Route 37 Bypass alignment"),
    (PLANNING_BASE, 21, "eastern_road_plan", "Eastern Road Plan - planned roads"),
    (PLANNING_BASE, 18, "streets", "Current street centerlines"),
    
    # Fire/Safety Infrastructure
    (PLANNING_BASE, 31, "fire_stations", "Fire station locations"),
    (PLANNING_BASE, 32, "fire_districts", "Fire response districts"),
    
    # Development Proffers (CIP funding source)
    (PLANNING_BASE, 3, "proffer_points", "Proffer contribution points from rezonings"),
    
    # Planning Applications (related to CIP projects)
    (PLANNING_BASE, 6, "comp_plan_applications", "Comprehensive Plan amendment applications"),
    (PLANNING_BASE, 9, "rezonings", "Rezoning applications"),
    
    # Schools (from Parks service)
    (PARKS_BASE, 0, "public_schools", "Public school locations"),
    (PARKS_BASE, 1, "school_districts", "Elementary school attendance districts"),
    
    # Overlays and Districts
    (PLANNING_BASE, 22, "airport_overlay", "Airport overlay districts"),
    (PLANNING_BASE, 2, "interstate_overlay", "Interstate overlay district"),
    (PLANNING_BASE, 38, "conservation_easements", "Conservation easements"),
    (PLANNING_BASE, 33, "magisterial_districts", "Magisterial (supervisor) districts"),
]


def fetch_layer_features(base_url: str, layer_id: int, out_sr: int = 4326) -> list:
    """
    Fetch all features from an ArcGIS MapServer layer.
    
    Uses pagination to handle layers larger than maxRecordCount.
    """
    url = f"{base_url}/{layer_id}/query"
    
    # First get count
    count_params = {
        "where": "1=1",
        "returnCountOnly": "true",
        "f": "json"
    }
    response = requests.get(url, params=count_params)
    response.raise_for_status()
    total = response.json().get("count", 0)
    print(f"  Total features: {total:,}")
    
    if total == 0:
        return []
    
    # Fetch features in batches
    all_features = []
    offset = 0
    batch_size = 1000
    
    while offset < total:
        query_params = {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": str(out_sr),
            "resultOffset": offset,
            "resultRecordCount": batch_size,
            "f": "geojson"
        }
        
        response = requests.get(url, params=query_params)
        response.raise_for_status()
        data = response.json()
        
        features = data.get("features", [])
        if not features:
            break
            
        all_features.extend(features)
        offset += len(features)
        print(f"  Fetched {offset:,} / {total:,}")
    
    return all_features


def download_layer(base_url: str, layer_id: int, name: str, description: str) -> gpd.GeoDataFrame:
    """Download a single layer and convert to GeoDataFrame."""
    print(f"\n{'='*60}")
    print(f"Downloading: {name}")
    print(f"  Layer: {base_url}/{layer_id}")
    print(f"  Description: {description}")
    
    features = fetch_layer_features(base_url, layer_id)
    
    if not features:
        print(f"  No features found, skipping")
        return None
    
    # Convert to GeoDataFrame
    try:
        gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
        print(f"  Created GeoDataFrame: {len(gdf):,} features")
        
        # Clean up column names (lowercase, remove special chars)
        gdf.columns = [c.lower().replace(" ", "_") for c in gdf.columns]
        
        return gdf
    except Exception as e:
        print(f"  Error creating GeoDataFrame: {e}")
        return None


def main():
    """Download all CIP-related layers."""
    print("=" * 60)
    print("Frederick County CIP GIS Layer Download")
    print("=" * 60)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    results = {}
    
    for base_url, layer_id, name, description in LAYERS:
        output_path = f"{OUTPUT_DIR}/{name}.parquet"
        
        # Check cache
        if os.path.exists(output_path):
            print(f"\n{name}: already exists, loading from cache")
            gdf = gpd.read_parquet(output_path)
            results[name] = len(gdf)
            continue
        
        # Download
        gdf = download_layer(base_url, layer_id, name, description)
        
        if gdf is not None and len(gdf) > 0:
            gdf.to_parquet(output_path)
            print(f"  Saved to: {output_path}")
            results[name] = len(gdf)
        else:
            results[name] = 0
    
    # Summary
    print("\n" + "=" * 60)
    print("DOWNLOAD SUMMARY")
    print("=" * 60)
    for name, count in results.items():
        status = "OK" if count > 0 else "EMPTY"
        print(f"  {name}: {count:,} features [{status}]")
    
    print(f"\nFiles saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
