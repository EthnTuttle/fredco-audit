#!/usr/bin/env python3
"""
Download Frederick County VA parcel data from Virginia GIS (VGIN).

Fetches parcel geometries and joins with local tax/ownership data.
Output: GeoParquet files for spatial analysis in the playground.

Usage:
    python scripts/download_parcels.py
"""

import json
import os
import time
import requests
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape

# Configuration
VGIN_BASE = "https://vginmaps.vdem.virginia.gov/arcgis/rest/services/VA_Base_Layers/VA_Parcels/FeatureServer/0"
FREDERICK_FIPS = "51069"
OUTPUT_DIR = "data/processed/gis"
BATCH_SIZE = 2000  # VGIN max record limit

def get_parcel_count(fips: str) -> int:
    """Get total count of parcels for a county."""
    url = f"{VGIN_BASE}/query"
    params = {
        "where": f"FIPS='{fips}'",
        "returnCountOnly": "true",
        "f": "json"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()["count"]

def fetch_parcel_batch(fips: str, offset: int, batch_size: int = BATCH_SIZE) -> list:
    """Fetch a batch of parcels with geometry."""
    url = f"{VGIN_BASE}/query"
    params = {
        "where": f"FIPS='{fips}'",
        "outFields": "OBJECTID,PARCELID,PTM_ID,LOCALITY",
        "returnGeometry": "true",
        "outSR": "4326",  # WGS84 for GeoJSON compatibility
        "resultOffset": offset,
        "resultRecordCount": batch_size,
        "f": "geojson"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def download_all_parcels(fips: str, output_path: str) -> gpd.GeoDataFrame:
    """Download all parcels for a county."""
    count = get_parcel_count(fips)
    print(f"Total parcels to download: {count:,}")
    
    all_features = []
    offset = 0
    
    while offset < count:
        print(f"  Fetching {offset:,} - {min(offset + BATCH_SIZE, count):,}...")
        data = fetch_parcel_batch(fips, offset)
        features = data.get("features", [])
        all_features.extend(features)
        offset += BATCH_SIZE
        
        # Be nice to the server
        time.sleep(0.5)
    
    print(f"Downloaded {len(all_features):,} parcels")
    
    # Convert to GeoDataFrame
    gdf = gpd.GeoDataFrame.from_features(all_features, crs="EPSG:4326")
    
    # Save to GeoParquet
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    gdf.to_parquet(output_path)
    print(f"Saved to {output_path}")
    
    return gdf

def normalize_parcel_id(ptm_id: str) -> str:
    """
    Normalize VGIN PTM_ID format to match tax data parcel_code format.
    
    VGIN: "80    A     9" or "75B--14-1-7"
    Tax:  "80--A--9" or "75B--14-1-7"
    """
    if not ptm_id or ptm_id.strip() == "":
        return ""
    
    # Remove extra spaces and normalize dashes
    normalized = ptm_id.strip()
    # Replace multiple spaces with double dash
    import re
    normalized = re.sub(r'\s+', '--', normalized)
    return normalized

def join_with_tax_data(parcels_gdf: gpd.GeoDataFrame, tax_parquet: str) -> gpd.GeoDataFrame:
    """Join parcel geometries with tax/ownership data."""
    print(f"Loading tax data from {tax_parquet}...")
    tax_df = pd.read_parquet(tax_parquet)
    
    # Get most recent year's data
    latest_year = tax_df['year'].max()
    tax_df = tax_df[tax_df['year'] == latest_year].copy()
    print(f"Using {latest_year} tax data: {len(tax_df):,} records")
    
    # Normalize parcel IDs for joining
    parcels_gdf['parcel_key'] = parcels_gdf['PTM_ID'].apply(normalize_parcel_id)
    tax_df['parcel_key'] = tax_df['parcel_code'].str.strip()
    
    # Join
    joined = parcels_gdf.merge(
        tax_df[['parcel_key', 'owner_name', 'owner_address', 'total_value', 
                'acreage', 'property_class', 'zone', 'district']],
        on='parcel_key',
        how='left'
    )
    
    # Stats
    matched = joined['owner_name'].notna().sum()
    print(f"Matched {matched:,} of {len(joined):,} parcels ({100*matched/len(joined):.1f}%)")
    
    return joined

def main():
    """Main entry point."""
    print("=" * 60)
    print("Frederick County Parcel Data Download")
    print("=" * 60)
    
    # Output paths
    raw_parcels_path = f"{OUTPUT_DIR}/frederick_parcels_raw.parquet"
    joined_parcels_path = f"{OUTPUT_DIR}/frederick_parcels.parquet"
    
    # Download parcels
    if os.path.exists(raw_parcels_path):
        print(f"Loading cached parcels from {raw_parcels_path}")
        parcels_gdf = gpd.read_parquet(raw_parcels_path)
    else:
        parcels_gdf = download_all_parcels(FREDERICK_FIPS, raw_parcels_path)
    
    # Join with tax data
    tax_path = "data/parquet/real_estate_tax.parquet"
    if os.path.exists(tax_path):
        joined_gdf = join_with_tax_data(parcels_gdf, tax_path)
        joined_gdf.to_parquet(joined_parcels_path)
        print(f"Saved joined data to {joined_parcels_path}")
    else:
        print(f"Tax data not found at {tax_path}, skipping join")
    
    print("\nDone!")
    print(f"  Raw parcels: {raw_parcels_path}")
    print(f"  Joined data: {joined_parcels_path}")

if __name__ == "__main__":
    main()
