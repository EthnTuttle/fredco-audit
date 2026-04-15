#!/usr/bin/env python3
"""
Convert JSON data files to Parquet format for efficient browser loading.
Parquet files are much smaller and faster to query with DuckDB-WASM.

Data Quality Notes:
- owner_name and owner_address fields are cleaned to remove embedded tax data
- Cleaning verified via manual spot-checks
- TODO: Full verification with GLM-OCR when Ollama >= 0.7 is available
"""

import json
import os
import re
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd


def clean_owner_field(raw_value):
    """
    Clean owner_name and owner_address fields that have embedded tax data.
    
    The PDF parsing captured fixed-width data where owner info and tax amounts
    appeared on the same line. This function strips the garbage.
    
    Examples of garbage patterns:
    - "SMITH JOHN                        L7 S1                              FH        506.61"
    - "123 MAIN ST                       WINCHESTER                         SH        253.30"
    - "ADAMS DONALD CARSON JR 531,200 DEFERRED 531,200 3,240.32"
    - "AARAMI JIMAJIMA K S 10" (trailing lot numbers)
    
    Returns cleaned string with just the owner name/address.
    """
    if not raw_value or not isinstance(raw_value, str):
        return raw_value
    
    # Remove DEFERRED tax patterns (with or without trailing tax amount)
    # "531,200 DEFERRED 531,200 3,240.32" or "531,200 DEFERRED 531,200"
    cleaned = re.sub(r'\s+[\d,]+\s+DEFERRED\s+[\d,\.]+(\s+[\d,\.]+)?$', '', raw_value)
    
    # Remove FH (first half) tax amounts and everything after
    # Must not be part of a word (use word boundary)
    cleaned = re.sub(r'\s+FH\s+[\d,\.]+.*$', '', cleaned)
    
    # Remove SH (second half) tax amounts - must be standalone SH, not part of word like "SOUTH"
    # Look for SH preceded by whitespace and followed by digits
    cleaned = re.sub(r'(?<!\w)SH\s+[\d,\.]+.*$', '', cleaned)
    
    # Remove lot/section info that got appended (L7 S1, L 7 S 1, etc.) anywhere in string
    cleaned = re.sub(r'\s+L\s*\d+\s+S\s*\d+.*$', '', cleaned)
    
    # Remove trailing standalone numbers (lot numbers, etc.)
    # Match: space + S or L followed by digits at end (but not as part of a word)
    cleaned = re.sub(r'\s+[SL]\s*\d+\s*$', '', cleaned)
    
    # Remove any trailing dollar amounts (just numbers at end)
    cleaned = re.sub(r'\s+[\d,]+\.\d{2}\s*$', '', cleaned)
    
    # Remove address-like data that got mixed in (AC ## CL # ZN pattern)
    # This catches cases like "1805 BACK MOUNTAIN RD AC 28.41 CL 5 ZN RA..."
    cleaned = re.sub(r'\s+AC\s+[\d\.]+\s+CL\s+\d.*$', '', cleaned)
    
    # Remove trailing acreage patterns like "9.00 ACRES" or "1.12 ACRES"
    cleaned = re.sub(r'\s+[\d\.]+\s+ACRES?\s*$', '', cleaned, flags=re.IGNORECASE)
    
    # Remove lot patterns like "LOT 68" or "3 S3B LOT 68"
    cleaned = re.sub(r'\s+\d*\s*S\d+[A-Z]?\s+LOT\s+\d+.*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+LOT\s+\d+.*$', '', cleaned, flags=re.IGNORECASE)
    
    # Remove trailing whitespace and multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned


def clean_real_estate_records(records):
    """Apply cleaning to real estate tax records."""
    cleaned = []
    for record in records:
        if isinstance(record, dict):
            record = record.copy()
            if 'owner_name' in record:
                record['owner_name'] = clean_owner_field(record['owner_name'])
            if 'owner_address' in record:
                record['owner_address'] = clean_owner_field(record['owner_address'])
        cleaned.append(record)
    return cleaned

# Directories
DATA_DIR = Path(__file__).parent.parent / "data" / "processed"
PARQUET_DIR = Path(__file__).parent.parent / "data" / "parquet"

# Files to convert (with their record paths)
FILES_TO_CONVERT = [
    # Large files
    {"json": "real_estate_tax.json", "parquet": "real_estate_tax.parquet", "record_path": "records"},
    {"json": "real_estate_ownership_analysis.json", "parquet": "ownership_analysis.parquet", "record_path": None},
    {"json": "real_estate_tax_summary.json", "parquet": "tax_summary.parquet", "record_path": None},
    {"json": "districts_enriched.geojson", "parquet": "districts.parquet", "record_path": "features"},
    
    # Education files
    {"json": "enrollment.json", "parquet": "enrollment.parquet", "record_path": "records"},
    {"json": "expenditures.json", "parquet": "expenditures.parquet", "record_path": "records"},
    {"json": "apa_data.json", "parquet": "apa_data.parquet", "record_path": None},
    {"json": "apa_education_expenditures.json", "parquet": "apa_education_expenditures.parquet", "record_path": None},
    
    # Budget files
    {"json": "county_budget_schools.json", "parquet": "county_budget_schools.parquet", "record_path": "data"},
    {"json": "county_department_detail.json", "parquet": "county_department_detail.parquet", "record_path": None},
    {"json": "county_government_analysis.json", "parquet": "county_government_analysis.parquet", "record_path": None},
    
    # VDOE files
    {"json": "vdoe/table8_enrollment.json", "parquet": "vdoe_table8_enrollment.parquet", "record_path": "data"},
    {"json": "vdoe/table15_expenditures.json", "parquet": "vdoe_table15_expenditures.parquet", "record_path": "data"},
    {"json": "vdoe/table17_ratios.json", "parquet": "vdoe_table17_ratios.parquet", "record_path": "data"},
    {"json": "vdoe/table18_admin_personnel.json", "parquet": "vdoe_table18_admin.parquet", "record_path": "data"},
    {"json": "vdoe/table19_instructional.json", "parquet": "vdoe_table19_instructional.parquet", "record_path": "data"},

    # Daily county reports (refreshed by scripts/refresh_daily_reports.py)
    {"json": "business_licenses.json", "parquet": "business_licenses.parquet", "record_path": "records"},
    {"json": "delinquent_real_estate_taxes.json", "parquet": "delinquent_real_estate_taxes.parquet", "record_path": "records"},
]


def flatten_nested_dict(d, parent_key='', sep='_'):
    """Flatten nested dictionaries for Parquet compatibility."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_nested_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
            # Convert list of dicts to JSON string
            items.append((new_key, json.dumps(v)))
        else:
            items.append((new_key, v))
    return dict(items)


def convert_file(json_path, parquet_path, record_path=None):
    """Convert a single JSON file to Parquet."""
    print(f"Converting {json_path.name}...")
    
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Extract records if specified
        if record_path:
            records = data.get(record_path, [])
        elif isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            # For complex objects, try to find a reasonable array
            if 'data' in data:
                records = data['data']
            elif 'records' in data:
                records = data['records']
            elif 'features' in data:
                records = data['features']
            elif 'annual_data' in data:
                records = data['annual_data']
            else:
                # Wrap single object as list
                records = [data]
        else:
            print(f"  Skipping {json_path.name}: unexpected format")
            return False
        
        if not records:
            print(f"  Skipping {json_path.name}: no records found")
            return False
        
        # Apply data cleaning for real estate tax records
        if 'real_estate_tax' in json_path.name.lower():
            print(f"  Cleaning owner_name and owner_address fields...")
            records = clean_real_estate_records(records)
        
        # Handle GeoJSON features specially
        if json_path.suffix == '.geojson':
            # Flatten feature properties and add geometry as WKT
            flattened = []
            for feature in records:
                row = {'geometry_type': feature.get('geometry', {}).get('type')}
                row['geometry_json'] = json.dumps(feature.get('geometry', {}))
                if 'properties' in feature:
                    for k, v in feature['properties'].items():
                        if isinstance(v, dict):
                            row[k] = json.dumps(v)
                        else:
                            row[k] = v
                flattened.append(row)
            records = flattened
        else:
            # Flatten nested dictionaries
            if isinstance(records[0], dict):
                flattened = []
                for record in records:
                    try:
                        flat = flatten_nested_dict(record)
                        flattened.append(flat)
                    except Exception as e:
                        print(f"  Warning: Could not flatten record: {e}")
                        flattened.append(record)
                records = flattened
        
        # Convert to DataFrame
        df = pd.DataFrame(records)
        
        # Convert to Parquet with compression
        table = pa.Table.from_pandas(df)
        pq.write_table(table, parquet_path, compression='snappy')
        
        # Report sizes
        json_size = json_path.stat().st_size
        parquet_size = parquet_path.stat().st_size
        ratio = json_size / parquet_size if parquet_size > 0 else 0
        
        print(f"  {json_path.name}: {json_size/1024/1024:.1f} MB → {parquet_size/1024/1024:.2f} MB ({ratio:.1f}x smaller)")
        print(f"  Records: {len(records)}, Columns: {len(df.columns)}")
        
        return True
        
    except Exception as e:
        print(f"  Error converting {json_path.name}: {e}")
        return False


def main():
    print("=" * 60)
    print("JSON to Parquet Conversion")
    print("=" * 60)
    
    # Create output directory
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    
    success = 0
    failed = 0
    
    for file_info in FILES_TO_CONVERT:
        json_path = DATA_DIR / file_info["json"]
        parquet_path = PARQUET_DIR / file_info["parquet"]
        
        if not json_path.exists():
            print(f"Skipping {file_info['json']}: file not found")
            failed += 1
            continue
        
        if convert_file(json_path, parquet_path, file_info.get("record_path")):
            success += 1
        else:
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Conversion complete: {success} succeeded, {failed} failed")
    print("=" * 60)
    
    # Print total sizes
    total_json = sum((DATA_DIR / f["json"]).stat().st_size for f in FILES_TO_CONVERT if (DATA_DIR / f["json"]).exists())
    total_parquet = sum((PARQUET_DIR / f["parquet"]).stat().st_size for f in FILES_TO_CONVERT if (PARQUET_DIR / f["parquet"]).exists())
    
    print(f"\nTotal JSON size: {total_json/1024/1024:.1f} MB")
    print(f"Total Parquet size: {total_parquet/1024/1024:.1f} MB")
    print(f"Overall compression: {total_json/total_parquet:.1f}x")
    
    # List output files
    print(f"\nParquet files in {PARQUET_DIR}:")
    for p in sorted(PARQUET_DIR.glob("*.parquet")):
        print(f"  {p.name}: {p.stat().st_size/1024:.1f} KB")


if __name__ == "__main__":
    main()
