#!/usr/bin/env python3
"""
Enrich district GeoJSON with ownership entity breakdown data.
Adds LLC%, entity type distribution, top owners per district.
"""

import json
import re
from collections import defaultdict, Counter
from pathlib import Path

def clean_owner_name(raw_name):
    """Extract clean owner name from raw field"""
    if not raw_name:
        return ""
    name = re.sub(r'\s+FH\s+[\d,\.]+.*$', '', raw_name)
    name = re.sub(r'\s+SH\s+[\d,\.]+.*$', '', name)
    return name.strip()

def classify_entity(name):
    """Classify owner by entity type"""
    name_upper = name.upper()
    
    if any(x in name_upper for x in ['COUNTY OF', 'CITY OF', 'TOWN OF', 'STATE OF', 
                                      'COMMONWEALTH', 'UNITED STATES', 'BOARD OF SUPERVISORS',
                                      'SCHOOL BOARD', 'SANITATION', 'WATER AUTH']):
        return 'Government'
    
    if any(x in name_upper for x in ['CHURCH', 'CHAPEL', 'MINISTRY', 'MINISTRIES', 
                                      'BAPTIST', 'METHODIST', 'LUTHERAN', 'CATHOLIC',
                                      'PRESBYTERIAN', 'EPISCOPAL', 'ASSEMBLY OF GOD',
                                      'CONGREGATION', 'DIOCESE', 'PARISH']):
        return 'Religious'
    
    if any(x in name_upper for x in ['FOUNDATION', 'ASSOC', 'ASSOCIATION', 'SOCIETY',
                                      'CLUB', 'LEGION', 'VFW', 'LIONS', 'ROTARY']):
        return 'Non-Profit'
    
    if re.search(r'\bLLC\b|\bL\.?L\.?C\.?\b', name_upper):
        return 'LLC'
    
    if any(x in name_upper for x in [' INC', ' CORP', ' CO ', ' COMPANY', 
                                      'INCORPORATED', 'CORPORATION', 'ENTERPRISES']):
        return 'Corporation'
    
    if re.search(r'\bLP\b|\bL\.?P\.?\b|LIMITED PARTNERSHIP', name_upper):
        return 'Limited Partnership'
    
    if any(x in name_upper for x in ['TRUST', 'TRUSTEE', 'REVOCABLE', 'IRREVOCABLE']):
        return 'Trust'
    
    if any(x in name_upper for x in ['ESTATE OF', 'ESTATE', ' EST ', 'HEIRS OF']):
        return 'Estate'
    
    if any(x in name_upper for x in ['BANK', 'MORTGAGE', 'FINANCIAL', 'CREDIT UNION']):
        return 'Financial'
    
    return 'Individual'

def analyze_district_ownership(records):
    """Analyze ownership patterns for a set of records (one district)"""
    entity_counts = Counter()
    entity_values = defaultdict(int)
    owner_values = defaultdict(lambda: {'count': 0, 'value': 0})
    
    total_value = 0
    
    for r in records:
        owner = clean_owner_name(r.get('owner_name', ''))
        entity_type = classify_entity(owner)
        value = r.get('total_value', 0) or 0
        
        entity_counts[entity_type] += 1
        entity_values[entity_type] += value
        total_value += value
        
        if owner:
            owner_values[owner]['count'] += 1
            owner_values[owner]['value'] += value
    
    total_records = len(records)
    
    # Entity breakdown (simplified for JSON)
    entity_breakdown = {}
    for etype in ['Individual', 'LLC', 'Trust', 'Corporation', 'Estate']:
        count = entity_counts.get(etype, 0)
        value = entity_values.get(etype, 0)
        entity_breakdown[etype.lower()] = {
            'count': count,
            'pct_records': round((count / total_records) * 100, 1) if total_records > 0 else 0,
            'value': value,
            'pct_value': round((value / total_value) * 100, 1) if total_value > 0 else 0
        }
    
    # Top owners by value
    sorted_owners = sorted(owner_values.items(), key=lambda x: -x[1]['value'])[:10]
    top_owners = [
        {'name': owner[:40], 'properties': info['count'], 'value': info['value']}
        for owner, info in sorted_owners
    ]
    
    # Top multi-property owners
    sorted_by_count = sorted(owner_values.items(), key=lambda x: -x[1]['count'])[:10]
    top_multi = [
        {'name': owner[:40], 'properties': info['count'], 'value': info['value']}
        for owner, info in sorted_by_count if info['count'] >= 3
    ]
    
    # Summary metrics
    llc_count = entity_counts.get('LLC', 0)
    llc_value = entity_values.get('LLC', 0)
    
    return {
        'llc_count': llc_count,
        'llc_pct_records': round((llc_count / total_records) * 100, 1) if total_records > 0 else 0,
        'llc_value': llc_value,
        'llc_pct_value': round((llc_value / total_value) * 100, 1) if total_value > 0 else 0,
        'individual_pct': round((entity_counts.get('Individual', 0) / total_records) * 100, 1) if total_records > 0 else 0,
        'entity_breakdown': entity_breakdown,
        'top_owners': top_owners,
        'top_multi_property': top_multi
    }

def main():
    data_dir = Path('/home/ethan/code/fredco-schools/data/processed')
    
    # Load existing GeoJSON
    geojson_path = data_dir / 'districts_enriched.geojson'
    print(f"Loading {geojson_path}...")
    with open(geojson_path) as f:
        geojson = json.load(f)
    
    # Load main real estate tax file (contains all years)
    main_tax_file = data_dir / 'real_estate_tax.json'
    print(f"Loading {main_tax_file}...")
    with open(main_tax_file) as f:
        all_tax_data = json.load(f)
    all_records = all_tax_data['records']
    
    # District name mapping (from GeoJSON to tax data)
    district_name_map = {
        'Opequon district': 'Opequon',
        'Gainesboro district': 'Gainesboro',
        'Back Creek district': 'Back Creek',
        'Shawnee district': 'Shawnee',
        'Stonewall district': 'Stonewall',
        'Red Bud district': 'Red Bud'
    }
    
    years = [2021, 2022, 2023, 2024, 2025]
    
    for year in years:
        # Filter records for this year
        records = [r for r in all_records if r['year'] == year]
        if not records:
            print(f"Warning: No records for year {year}, skipping")
            continue
            
        print(f"Processing {year}...")
        
        # Group records by district
        by_district = defaultdict(list)
        for r in records:
            district = r.get('district', 'Unknown')
            if district:
                by_district[district].append(r)
        
        # Analyze each district
        for feature in geojson['features']:
            geojson_name = feature['properties'].get('NAME', '')
            district_name = district_name_map.get(geojson_name)
            
            if not district_name:
                continue
            
            district_records = by_district.get(district_name, [])
            if not district_records:
                print(f"  Warning: No records for {district_name}")
                continue
            
            ownership_data = analyze_district_ownership(district_records)
            
            # Add ownership data to tax_data for this year
            if 'tax_data' not in feature['properties']:
                feature['properties']['tax_data'] = {}
            
            if str(year) not in feature['properties']['tax_data']:
                feature['properties']['tax_data'][str(year)] = {}
            
            # Merge ownership data into existing tax_data
            feature['properties']['tax_data'][str(year)]['ownership'] = ownership_data
            
            print(f"  {district_name}: {len(district_records)} records, "
                  f"LLC={ownership_data['llc_pct_records']:.1f}%")
    
    # Save enriched GeoJSON
    output_path = data_dir / 'districts_enriched.geojson'
    print(f"\nSaving to {output_path}...")
    with open(output_path, 'w') as f:
        json.dump(geojson, f)
    
    print("Done!")
    
    # Print summary
    print("\n" + "="*60)
    print("DISTRICT OWNERSHIP SUMMARY (2025)")
    print("="*60)
    for feature in geojson['features']:
        name = feature['properties'].get('NAME', '').replace(' district', '')
        tax_2025 = feature['properties'].get('tax_data', {}).get('2025', {})
        ownership = tax_2025.get('ownership', {})
        if ownership:
            print(f"\n{name}:")
            print(f"  LLC: {ownership['llc_count']} properties ({ownership['llc_pct_records']}%), "
                  f"${ownership['llc_value']:,} ({ownership['llc_pct_value']}% of value)")
            print(f"  Individual: {ownership['individual_pct']}%")
            if ownership['top_owners']:
                print(f"  Top owner: {ownership['top_owners'][0]['name']} "
                      f"(${ownership['top_owners'][0]['value']:,})")

if __name__ == '__main__':
    main()
