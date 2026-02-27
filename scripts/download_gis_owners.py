#!/usr/bin/env python3
"""
Download owner lookup data from Frederick County GIS API.

This creates a JSON lookup file keyed by account number (MACCT) with
owner name, address, and other property details for cross-referencing
with OCR-extracted tax records.

Source: Frederick County GIS - Planning Access Terminal
URL: https://fredcogis.fcva.us/maps/rest/services/FC_Planning/PlanningAccessTerminal/MapServer/0

Usage:
    python scripts/download_gis_owners.py
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from tqdm import tqdm

# Configuration
BASE_URL = "https://fredcogis.fcva.us/maps/rest/services/FC_Planning/PlanningAccessTerminal/MapServer/0"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "processed"
OUTPUT_FILE = OUTPUT_DIR / "gis_owner_lookup.json"
BATCH_SIZE = 1000

# Fields to fetch for owner lookup
FIELDS = [
    "MACCT",      # Master Account Number (join key)
    "PIN",        # Parcel ID Number
    "GPIN",       # Geographic PIN
    "MLNAM",      # Owner Last Name
    "MFNAM",      # Owner First Name (or second owner)
    "MADD1",      # Owner Mailing Address
    "MCITY",      # Owner City
    "MSTATE",     # Owner State
    "MZIP",       # Owner ZIP
    "MACRE",      # Acreage
    "MZONE",      # Zoning
    "MIMPRV",     # Improvement Value
    "MTOTLD",     # Land Value
    "MTOTPR",     # Total Value
    "MHSE",       # House Number
    "MSTRT",      # Street Name
    "MSTTYP",     # Street Type
    "MMAGCD",     # Magisterial District Code
]


def get_record_count() -> int:
    """Get total count of parcels."""
    url = f"{BASE_URL}/query"
    params = {
        "where": "1=1",
        "returnCountOnly": "true",
        "f": "json"
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data.get("count", 0)


def fetch_batch(offset: int) -> list:
    """Fetch a batch of records."""
    url = f"{BASE_URL}/query"
    params = {
        "where": "1=1",
        "outFields": ",".join(FIELDS),
        "returnGeometry": "false",  # We don't need geometry for owner lookup
        "resultOffset": offset,
        "resultRecordCount": BATCH_SIZE,
        "f": "json"
    }
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()
    return data.get("features", [])


def build_owner_lookup(features: list) -> dict:
    """Convert features list to account_number -> owner dict."""
    lookup = {}
    
    for feature in features:
        attrs = feature.get("attributes", {})
        macct = attrs.get("MACCT")
        
        if not macct:
            continue
        
        # Convert to string account number (matches tax data format)
        account_number = str(int(macct))
        
        # Build owner name from MLNAM and MFNAM
        # MLNAM is typically "LASTNAME FIRSTNAME" or just owner name
        # MFNAM is typically second owner or middle name
        mlnam = (attrs.get("MLNAM") or "").strip()
        mfnam = (attrs.get("MFNAM") or "").strip()
        
        if mfnam and mfnam != mlnam:
            owner_name = f"{mlnam} & {mfnam}" if mlnam else mfnam
        else:
            owner_name = mlnam
        
        # Build address
        madd1 = (attrs.get("MADD1") or "").strip()
        mcity = (attrs.get("MCITY") or "").strip()
        mstate = (attrs.get("MSTATE") or "").strip()
        mzip = attrs.get("MZIP")
        
        if mzip:
            # Format ZIP code
            mzip_str = str(int(mzip)) if mzip else ""
            if len(mzip_str) == 9:
                mzip_str = f"{mzip_str[:5]}-{mzip_str[5:]}"
            city_state_zip = f"{mcity} {mstate} {mzip_str}".strip()
        else:
            city_state_zip = f"{mcity} {mstate}".strip()
        
        # Build physical address
        mhse = attrs.get("MHSE") or ""
        mstrt = (attrs.get("MSTRT") or "").strip()
        msttyp = (attrs.get("MSTTYP") or "").strip()
        physical_address = f"{mhse} {mstrt} {msttyp}".strip()
        
        lookup[account_number] = {
            "owner_name": owner_name,
            "owner_address": madd1,
            "city_state_zip": city_state_zip,
            "physical_address": physical_address,
            "acreage": attrs.get("MACRE"),
            "zone": (attrs.get("MZONE") or "").strip(),
            "land_value": attrs.get("MTOTLD"),
            "improvement_value": attrs.get("MIMPRV"),
            "total_value": attrs.get("MTOTPR"),
            "district_code": attrs.get("MMAGCD"),
            "pin": (attrs.get("PIN") or "").strip(),
            "gpin": (attrs.get("GPIN") or "").strip(),
        }
    
    return lookup


def main():
    print("=" * 60)
    print("Downloading GIS Owner Lookup Data")
    print("=" * 60)
    print(f"Source: {BASE_URL}")
    print(f"Output: {OUTPUT_FILE}")
    print()
    
    # Get total count
    print("Getting record count...")
    total = get_record_count()
    print(f"Total parcels: {total:,}")
    print()
    
    # Download in batches
    all_features = []
    
    with tqdm(total=total, desc="Downloading", unit="records") as pbar:
        offset = 0
        while offset < total:
            try:
                features = fetch_batch(offset)
                all_features.extend(features)
                pbar.update(len(features))
                offset += BATCH_SIZE
                
                # Be nice to the server
                time.sleep(0.2)
                
            except requests.RequestException as e:
                print(f"\nError at offset {offset}: {e}")
                print("Retrying in 5 seconds...")
                time.sleep(5)
                continue
    
    print(f"\nDownloaded {len(all_features):,} records")
    
    # Build lookup
    print("Building owner lookup...")
    lookup = build_owner_lookup(all_features)
    print(f"Lookup entries: {len(lookup):,}")
    
    # Sample check
    if lookup:
        sample_key = list(lookup.keys())[0]
        sample = lookup[sample_key]
        print(f"\nSample entry (account {sample_key}):")
        print(f"  Owner: {sample['owner_name']}")
        print(f"  Address: {sample['owner_address']}")
        print(f"  City/State/ZIP: {sample['city_state_zip']}")
    
    # Save
    output_data = {
        "metadata": {
            "source": "Frederick County GIS - Planning Access Terminal",
            "url": BASE_URL,
            "downloaded": datetime.now().isoformat(),
            "total_records": len(lookup),
            "fields": FIELDS,
        },
        "lookup": lookup
    }
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output_data, f, indent=2)
    
    file_size = OUTPUT_FILE.stat().st_size / 1024 / 1024
    print(f"\nSaved to: {OUTPUT_FILE}")
    print(f"File size: {file_size:.1f} MB")
    print("=" * 60)


if __name__ == "__main__":
    main()
