#!/usr/bin/env python3
"""
Download Frederick County parcel data with tax account numbers.

The County GIS parcel layer (Layer 0) has MACCT field which corresponds 
to the account_number in the tax data, enabling a reliable join.

Usage:
    python scripts/download_county_parcels.py
"""

import json
import os
import time
import requests
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape

# Configuration
COUNTY_PARCELS_URL = "https://fredcogis.fcva.us/maps/rest/services/FC_Planning/PlanningAccessTerminal/MapServer/0"
OUTPUT_DIR = "data/processed/gis"
BATCH_SIZE = 1000

# Key fields to fetch
FIELDS = [
    "OBJECTID", "PIN", "GPIN", "MACCT",  # IDs
    "TAXMAP", "SECTION", "LOT", "SUBLOT",  # Parcel components
    "MLNAM", "MFNAM",  # Owner name
    "MADD1", "MCITY", "MSTATE", "MZIP",  # Owner address
    "MACRE", "MZONE", "MLUSE",  # Property info
    "MIMPRV", "MTOTLD", "MTOTPR",  # Values (improvement, land, total)
    "MHSE", "MSTRT", "MSTTYP",  # Physical address
    "MYRBLT", "MMAGCD"  # Year built, magisterial district
]


def get_parcel_count() -> int:
    """Get total count of parcels."""
    url = f"{COUNTY_PARCELS_URL}/query"
    params = {
        "where": "1=1",
        "returnCountOnly": "true",
        "f": "json"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()["count"]


def fetch_parcel_batch(offset: int, batch_size: int = BATCH_SIZE) -> list:
    """Fetch a batch of parcels with geometry."""
    url = f"{COUNTY_PARCELS_URL}/query"
    params = {
        "where": "1=1",
        "outFields": ",".join(FIELDS),
        "returnGeometry": "true",
        "outSR": "4326",  # WGS84
        "resultOffset": offset,
        "resultRecordCount": batch_size,
        "f": "geojson"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def download_county_parcels(output_path: str) -> gpd.GeoDataFrame:
    """Download all parcels from County GIS."""
    count = get_parcel_count()
    print(f"Total parcels to download: {count:,}")
    
    all_features = []
    offset = 0
    
    while offset < count:
        print(f"  Fetching {offset:,} - {min(offset + BATCH_SIZE, count):,}...")
        data = fetch_parcel_batch(offset)
        features = data.get("features", [])
        all_features.extend(features)
        offset += BATCH_SIZE
        
        # Be nice to the server
        time.sleep(0.3)
    
    print(f"Downloaded {len(all_features):,} parcels")
    
    # Convert to GeoDataFrame
    gdf = gpd.GeoDataFrame.from_features(all_features, crs="EPSG:4326")
    
    # Clean up column names
    gdf.columns = [c.lower() for c in gdf.columns]
    
    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    gdf.to_parquet(output_path)
    print(f"Saved to {output_path}")
    
    return gdf


def join_with_tax_data(parcels_gdf: gpd.GeoDataFrame, tax_parquet: str) -> gpd.GeoDataFrame:
    """Join parcel geometries with tax data using account number."""
    print(f"Loading tax data from {tax_parquet}...")
    tax_df = pd.read_parquet(tax_parquet)
    
    # Get most recent year's data
    latest_year = tax_df['year'].max()
    tax_df = tax_df[tax_df['year'] == latest_year].copy()
    print(f"Using {latest_year} tax data: {len(tax_df):,} records")
    
    # The MACCT field in County GIS should match account_number in tax data
    # Convert both to string and strip
    parcels_gdf['macct_str'] = parcels_gdf['macct'].apply(
        lambda x: str(int(x)) if pd.notna(x) and x != 0 else ''
    )
    tax_df['acct_str'] = tax_df['account_number'].apply(
        lambda x: str(int(x)) if pd.notna(x) else ''
    )
    
    # Join
    print("Joining on account number...")
    joined = parcels_gdf.merge(
        tax_df[['acct_str', 'parcel_code', 'owner_name', 'owner_address', 
                'total_value', 'acreage', 'property_class', 'zone', 'district',
                'land_value', 'improvement_value', 'tax_amount']],
        left_on='macct_str',
        right_on='acct_str',
        how='left',
        suffixes=('_gis', '_tax')
    )
    
    # Stats
    matched = joined['owner_name'].notna().sum()
    print(f"Matched {matched:,} of {len(joined):,} parcels ({100*matched/len(joined):.1f}%)")
    
    return joined


def main():
    """Main entry point."""
    print("=" * 60)
    print("Frederick County Parcel Data Download (County GIS)")
    print("=" * 60)
    
    raw_path = f"{OUTPUT_DIR}/county_parcels_raw.parquet"
    joined_path = f"{OUTPUT_DIR}/county_parcels.parquet"
    
    # Download
    if os.path.exists(raw_path):
        print(f"Loading cached parcels from {raw_path}")
        parcels_gdf = gpd.read_parquet(raw_path)
    else:
        parcels_gdf = download_county_parcels(raw_path)
    
    # Join with tax data
    tax_path = "data/parquet/real_estate_tax.parquet"
    if os.path.exists(tax_path):
        joined_gdf = join_with_tax_data(parcels_gdf, tax_path)
        joined_gdf.to_parquet(joined_path)
        print(f"Saved joined data to {joined_path}")
    else:
        print(f"Tax data not found at {tax_path}, skipping join")
    
    print("\nDone!")
    print(f"  Raw parcels: {raw_path}")
    print(f"  Joined data: {joined_path}")


if __name__ == "__main__":
    main()
