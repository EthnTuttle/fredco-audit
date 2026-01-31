#!/usr/bin/env python3
"""
Analyze Real Estate Tax Book data for owner patterns, entity types, and outliers.
Examines names and other fields for meaningful groupings.
"""

import json
import re
from collections import defaultdict, Counter
from pathlib import Path

def clean_owner_name(raw_name):
    """Extract clean owner name from raw field (which may have embedded tax data)"""
    if not raw_name:
        return ""
    # Remove embedded FH/SH tax amounts that appear in the raw data
    name = re.sub(r'\s+FH\s+[\d,\.]+.*$', '', raw_name)
    name = re.sub(r'\s+SH\s+[\d,\.]+.*$', '', name)
    return name.strip()

def classify_entity(name):
    """Classify owner by entity type"""
    name_upper = name.upper()
    
    # Government/Public entities
    if any(x in name_upper for x in ['COUNTY OF', 'CITY OF', 'TOWN OF', 'STATE OF', 
                                      'COMMONWEALTH', 'UNITED STATES', 'U S A',
                                      'VIRGINIA DEPT', 'VA DEPT', 'BOARD OF SUPERVISORS',
                                      'SCHOOL BOARD', 'SANITATION', 'WATER AUTH']):
        return 'Government'
    
    # Churches/Religious
    if any(x in name_upper for x in ['CHURCH', 'CHAPEL', 'MINISTRY', 'MINISTRIES', 
                                      'BAPTIST', 'METHODIST', 'LUTHERAN', 'CATHOLIC',
                                      'PRESBYTERIAN', 'EPISCOPAL', 'ASSEMBLY OF GOD',
                                      'CONGREGATION', 'DIOCESE', 'PARISH', 'MOSQUE',
                                      'SYNAGOGUE', 'TEMPLE', 'BIBLE', 'GOSPEL']):
        return 'Religious'
    
    # Non-profits/Organizations
    if any(x in name_upper for x in ['FOUNDATION', 'ASSOC', 'ASSOCIATION', 'SOCIETY',
                                      'CLUB', 'LEGION', 'VFW', 'LIONS', 'ROTARY',
                                      'KIWANIS', 'ELKS', 'MOOSE', 'LODGE', 'FRATERNAL',
                                      'CHARITABLE', 'CHARITY', 'NON-PROFIT', 'NONPROFIT',
                                      'INC C/O', '501']):
        return 'Non-Profit/Organization'
    
    # LLC or LC (Limited Company)
    if re.search(r'\bLLC\b|\bL\.?L\.?C\.?\b|\bLC\b', name_upper):
        return 'LLC'
    
    # Corporations
    if any(x in name_upper for x in [' INC', ' CORP', ' CO ', ' COMPANY', 
                                      'INCORPORATED', 'CORPORATION', 'ENTERPRISES']):
        return 'Corporation'
    
    # Limited Partnerships
    if re.search(r'\bLP\b|\bL\.?P\.?\b|LIMITED PARTNERSHIP', name_upper):
        return 'Limited Partnership'
    
    # Trusts
    if any(x in name_upper for x in ['TRUST', 'TRUSTEE', 'REVOCABLE', 'IRREVOCABLE',
                                      'LIVING TRUST', 'FAMILY TRUST', 'TR ']):
        return 'Trust'
    
    # Estates
    if any(x in name_upper for x in ['ESTATE OF', 'ESTATE', ' EST ', 'HEIRS OF',
                                      'HEIRS', 'DEVISEES']):
        return 'Estate'
    
    # Banks/Financial
    if any(x in name_upper for x in ['BANK', 'MORTGAGE', 'FINANCIAL', 'CREDIT UNION',
                                      'SAVINGS', 'LENDING', 'CAPITAL']):
        return 'Financial Institution'
    
    # Utilities
    if any(x in name_upper for x in ['ELECTRIC', 'POWER', 'GAS', 'TELEPHONE',
                                      'COMMUNICATIONS', 'VERIZON', 'AT&T', 'COMCAST',
                                      'DOMINION', 'SHENANDOAH VALLEY ELEC']):
        return 'Utility'
    
    # HOAs/Condos
    if any(x in name_upper for x in ['HOA', 'HOMEOWNERS', 'HOME OWNERS', 'CONDO',
                                      'CONDOMINIUM', 'PROPERTY OWNERS', 'POA']):
        return 'HOA/Condo Association'
    
    # Default to Individual
    return 'Individual'

def extract_last_name(name):
    """Try to extract last name from individual owner names"""
    name = name.strip()
    if not name:
        return None
    
    # Skip if clearly not an individual
    entity_keywords = ['LLC', 'INC', 'CORP', 'TRUST', 'CHURCH', 'BANK', 
                       'COUNTY', 'ESTATE', 'FOUNDATION', 'ASSOC', ' LC', ' LP']
    if any(kw in name.upper() for kw in entity_keywords):
        return None
    
    # Common patterns: "LASTNAME, FIRSTNAME" or "FIRSTNAME LASTNAME"
    # or "LASTNAME FIRSTNAME & SPOUSE"
    parts = name.split()
    if not parts:
        return None
    
    # If comma present, first part is likely last name
    if ',' in name:
        last_name = name.split(',')[0].strip()
        # Remove any suffixes like JR, SR, II, III
        last_name = re.sub(r'\s+(JR|SR|II|III|IV)\.?$', '', last_name, flags=re.IGNORECASE)
        return last_name.upper()
    
    # Otherwise, take first word as last name (common in tax records)
    first_word = parts[0].strip()
    # Skip if it's likely a first name followed by last name
    if len(parts) >= 2 and parts[0].upper() not in ['THE', 'A', 'AN']:
        return first_word.upper()
    
    return None

def analyze_address_patterns(records):
    """Analyze owner addresses for patterns"""
    cities = Counter()
    states = Counter()
    out_of_state = []
    
    for r in records:
        city_state_zip = r.get('owner_city_state_zip', '') or ''
        if not isinstance(city_state_zip, str):
            continue
        # Try to extract state
        state_match = re.search(r'\b([A-Z]{2})\s+\d{5}', city_state_zip)
        if state_match:
            state = state_match.group(1)
            states[state] += 1
            if state != 'VA':
                out_of_state.append({
                    'owner': clean_owner_name(r.get('owner_name', '')),
                    'state': state,
                    'total_value': r.get('total_value', 0)
                })
        
        # Extract city
        city_match = re.match(r'^([A-Z\s]+)\s+[A-Z]{2}\s+\d{5}', city_state_zip)
        if city_match:
            city = city_match.group(1).strip()
            cities[city] += 1
    
    return cities, states, out_of_state

def find_high_value_owners(records, top_n=50):
    """Find owners with highest total property values"""
    owner_values = defaultdict(lambda: {'total_value': 0, 'property_count': 0, 'properties': []})
    
    for r in records:
        owner = clean_owner_name(r.get('owner_name', ''))
        if not owner:
            continue
        owner_values[owner]['total_value'] += r.get('total_value', 0)
        owner_values[owner]['property_count'] += 1
        owner_values[owner]['properties'].append({
            'parcel': r.get('parcel_code', ''),
            'value': r.get('total_value', 0),
            'district': r.get('district', ''),
            'class': r.get('property_class', '')
        })
    
    # Sort by total value
    sorted_owners = sorted(owner_values.items(), key=lambda x: x[1]['total_value'], reverse=True)
    return sorted_owners[:top_n]

def find_multi_property_owners(records, min_properties=5):
    """Find owners with many properties"""
    owner_props = defaultdict(list)
    
    for r in records:
        owner = clean_owner_name(r.get('owner_name', ''))
        if not owner:
            continue
        owner_props[owner].append({
            'parcel': r.get('parcel_code', ''),
            'value': r.get('total_value', 0),
            'district': r.get('district', ''),
            'class': r.get('property_class', ''),
            'acreage': r.get('acreage', 0)
        })
    
    multi_owners = {k: v for k, v in owner_props.items() if len(v) >= min_properties}
    return dict(sorted(multi_owners.items(), key=lambda x: len(x[1]), reverse=True))

def analyze_property_class_patterns(records):
    """Analyze patterns by property class"""
    class_names = {
        1: 'Residential',
        2: 'Agricultural/Undeveloped', 
        3: 'Multi-Family',
        4: 'Commercial',
        5: 'Industrial',
        6: 'Land Use (Deferred)',
        7: 'Public Service',
        8: 'Exempt',
        9: 'Mineral'
    }
    
    class_stats = defaultdict(lambda: {
        'count': 0, 
        'total_value': 0, 
        'entity_types': Counter(),
        'top_owners': Counter()
    })
    
    for r in records:
        pclass = r.get('property_class', 0)
        owner = clean_owner_name(r.get('owner_name', ''))
        entity_type = classify_entity(owner)
        value = r.get('total_value', 0)
        
        class_stats[pclass]['count'] += 1
        class_stats[pclass]['total_value'] += value
        class_stats[pclass]['entity_types'][entity_type] += 1
        class_stats[pclass]['top_owners'][owner] += value
    
    # Add class names and compute averages
    result = {}
    for pclass, stats in class_stats.items():
        result[pclass] = {
            'class_name': class_names.get(pclass, f'Unknown ({pclass})'),
            'count': stats['count'],
            'total_value': stats['total_value'],
            'avg_value': stats['total_value'] / stats['count'] if stats['count'] > 0 else 0,
            'entity_types': dict(stats['entity_types']),
            'top_owners': stats['top_owners'].most_common(10)
        }
    
    return result

def find_oddities(records):
    """Find unusual patterns and potential oddities"""
    oddities = {
        'zero_value_improved': [],  # Properties with improvements but zero value
        'very_high_land_ratio': [],  # Land value much higher than improvements
        'tiny_acreage_high_value': [],  # Very small lots with high values
        'large_acreage_low_value': [],  # Large lots with low values
        'potential_duplicates': [],  # Same owner, same address
        'unusual_zones': Counter(),  # Unusual zoning patterns
    }
    
    seen_owner_address = defaultdict(list)
    
    for r in records:
        owner = clean_owner_name(r.get('owner_name', ''))
        land = r.get('land_value', 0) or 0
        improvement = r.get('improvement_value', 0) or 0
        total = r.get('total_value', 0) or 0
        acreage = r.get('acreage', 0) or 0
        zone = r.get('zone', '') or ''
        address = r.get('owner_address', '') or ''
        
        # Zero value with improvements
        if improvement > 0 and total == 0:
            oddities['zero_value_improved'].append({
                'owner': owner,
                'parcel': r.get('parcel_code', ''),
                'improvement_value': improvement
            })
        
        # Very high land ratio (land > 90% of total, excluding empty lots)
        if total > 100000 and improvement > 0:
            land_ratio = land / total if total > 0 else 0
            if land_ratio > 0.9:
                oddities['very_high_land_ratio'].append({
                    'owner': owner,
                    'parcel': r.get('parcel_code', ''),
                    'land_value': land,
                    'total_value': total,
                    'land_ratio': land_ratio
                })
        
        # Tiny acreage, high value (< 0.1 acres, > $500k)
        if acreage > 0 and acreage < 0.1 and total > 500000:
            oddities['tiny_acreage_high_value'].append({
                'owner': owner,
                'parcel': r.get('parcel_code', ''),
                'acreage': acreage,
                'total_value': total
            })
        
        # Large acreage, low value (> 50 acres, < $100k) - excluding class 6 (land use)
        if acreage > 50 and total < 100000 and r.get('property_class') != 6:
            oddities['large_acreage_low_value'].append({
                'owner': owner,
                'parcel': r.get('parcel_code', ''),
                'acreage': acreage,
                'total_value': total,
                'class': r.get('property_class')
            })
        
        # Track for potential duplicates
        key = (owner, address[:30] if address else '')
        seen_owner_address[key].append(r.get('parcel_code', ''))
        
        # Track unusual zones
        if zone:
            oddities['unusual_zones'][zone] += 1
    
    # Find potential duplicates (same owner+address with multiple parcels)
    for (owner, addr), parcels in seen_owner_address.items():
        if len(parcels) > 3 and owner:  # More than 3 parcels at same address
            oddities['potential_duplicates'].append({
                'owner': owner,
                'address': addr,
                'parcel_count': len(parcels),
                'parcels': parcels[:10]  # First 10
            })
    
    # Convert zones counter to sorted list
    oddities['unusual_zones'] = dict(oddities['unusual_zones'].most_common())
    
    return oddities

def main():
    data_dir = Path('/home/ethan/code/fredco-audit/data/processed/temp')
    
    # Load 2025 data (most recent)
    tax_file = data_dir / 'tax_2025.json'
    print(f"Loading {tax_file}...")
    
    with open(tax_file) as f:
        data = json.load(f)
    
    records = data['records']
    year = data['year']
    
    print(f"\n{'='*70}")
    print(f"REAL ESTATE OWNER ANALYSIS - {year}")
    print(f"{'='*70}")
    print(f"Total Records: {len(records):,}")
    
    # 1. Entity Type Classification
    print(f"\n{'='*70}")
    print("1. OWNER ENTITY TYPE CLASSIFICATION")
    print(f"{'='*70}")
    
    entity_counts = Counter()
    entity_values = defaultdict(int)
    entity_examples = defaultdict(list)
    
    for r in records:
        owner = clean_owner_name(r.get('owner_name', ''))
        entity_type = classify_entity(owner)
        entity_counts[entity_type] += 1
        entity_values[entity_type] += r.get('total_value', 0)
        if len(entity_examples[entity_type]) < 5:
            entity_examples[entity_type].append(owner[:60])
    
    print(f"\n{'Entity Type':<25} {'Count':>10} {'% Records':>10} {'Total Value':>18} {'% Value':>10}")
    print("-" * 75)
    
    total_records = len(records)
    total_value = sum(entity_values.values())
    
    for entity_type, count in entity_counts.most_common():
        value = entity_values[entity_type]
        pct_records = (count / total_records) * 100
        pct_value = (value / total_value) * 100 if total_value > 0 else 0
        print(f"{entity_type:<25} {count:>10,} {pct_records:>9.1f}% ${value:>15,} {pct_value:>9.1f}%")
    
    print("\nExamples by type:")
    for entity_type in ['LLC', 'Corporation', 'Trust', 'Religious', 'Government']:
        if entity_examples[entity_type]:
            print(f"\n  {entity_type}:")
            for ex in entity_examples[entity_type][:3]:
                print(f"    - {ex}")
    
    # 2. Common Last Names (for Individuals)
    print(f"\n{'='*70}")
    print("2. MOST COMMON LAST NAMES (Individual Owners)")
    print(f"{'='*70}")
    
    last_names = Counter()
    last_name_values = defaultdict(int)
    
    for r in records:
        owner = clean_owner_name(r.get('owner_name', ''))
        if classify_entity(owner) == 'Individual':
            ln = extract_last_name(owner)
            if ln and len(ln) > 1:
                last_names[ln] += 1
                last_name_values[ln] += r.get('total_value', 0)
    
    print(f"\n{'Last Name':<20} {'Properties':>12} {'Total Value':>18} {'Avg Value':>15}")
    print("-" * 67)
    
    for ln, count in last_names.most_common(25):
        value = last_name_values[ln]
        avg = value / count if count > 0 else 0
        print(f"{ln:<20} {count:>12,} ${value:>15,} ${avg:>12,.0f}")
    
    # 3. High Value Owners
    print(f"\n{'='*70}")
    print("3. TOP 30 HIGHEST VALUE PROPERTY OWNERS")
    print(f"{'='*70}")
    
    high_value = find_high_value_owners(records, 30)
    
    print(f"\n{'Owner':<45} {'Props':>6} {'Total Value':>18}")
    print("-" * 71)
    
    for owner, info in high_value:
        print(f"{owner[:44]:<45} {info['property_count']:>6} ${info['total_value']:>15,}")
    
    # 4. Multi-Property Owners
    print(f"\n{'='*70}")
    print("4. MULTI-PROPERTY OWNERS (10+ Properties)")
    print(f"{'='*70}")
    
    multi_owners = find_multi_property_owners(records, 10)
    
    print(f"\n{'Owner':<45} {'Props':>6} {'Total Value':>18}")
    print("-" * 71)
    
    for owner, props in list(multi_owners.items())[:30]:
        total_val = sum(p['value'] for p in props)
        print(f"{owner[:44]:<45} {len(props):>6} ${total_val:>15,}")
    
    # 5. Entity Breakdown by Property Class
    print(f"\n{'='*70}")
    print("5. ENTITY TYPES BY PROPERTY CLASS")
    print(f"{'='*70}")
    
    class_analysis = analyze_property_class_patterns(records)
    
    for pclass in sorted([k for k in class_analysis.keys() if k is not None]):
        info = class_analysis[pclass]
        print(f"\n{info['class_name']} (Class {pclass}):")
        print(f"  Count: {info['count']:,}  |  Total Value: ${info['total_value']:,}  |  Avg: ${info['avg_value']:,.0f}")
        print(f"  Entity breakdown:")
        for etype, count in sorted(info['entity_types'].items(), key=lambda x: -x[1])[:5]:
            pct = (count / info['count']) * 100
            print(f"    {etype}: {count:,} ({pct:.1f}%)")
    
    # 6. Out-of-State Owners
    print(f"\n{'='*70}")
    print("6. OUT-OF-STATE PROPERTY OWNERS")
    print(f"{'='*70}")
    
    cities, states, out_of_state = analyze_address_patterns(records)
    
    print("\nOwnership by State:")
    for state, count in states.most_common(15):
        pct = (count / len(records)) * 100
        marker = " <-- Local" if state == 'VA' else ""
        print(f"  {state}: {count:,} ({pct:.1f}%){marker}")
    
    # Aggregate out-of-state by owner
    oos_by_owner = defaultdict(lambda: {'state': '', 'total_value': 0, 'count': 0})
    for item in out_of_state:
        owner = item['owner']
        oos_by_owner[owner]['state'] = item['state']
        oos_by_owner[owner]['total_value'] += item['total_value']
        oos_by_owner[owner]['count'] += 1
    
    print("\nTop Out-of-State Owners by Value:")
    sorted_oos = sorted(oos_by_owner.items(), key=lambda x: -x[1]['total_value'])[:20]
    for owner, info in sorted_oos:
        print(f"  {owner[:40]:<42} ({info['state']}) - {info['count']} props, ${info['total_value']:,}")
    
    # 7. Oddities and Anomalies
    print(f"\n{'='*70}")
    print("7. ODDITIES AND ANOMALIES")
    print(f"{'='*70}")
    
    oddities = find_oddities(records)
    
    print(f"\nZero-Value Improved Properties: {len(oddities['zero_value_improved'])}")
    for item in oddities['zero_value_improved'][:5]:
        print(f"  - {item['owner'][:40]} (Parcel: {item['parcel']}, Improvements: ${item['improvement_value']:,})")
    
    print(f"\nVery High Land Ratio (>90% land value): {len(oddities['very_high_land_ratio'])}")
    for item in oddities['very_high_land_ratio'][:5]:
        print(f"  - {item['owner'][:40]} (Parcel: {item['parcel']}, {item['land_ratio']:.1%} land)")
    
    print(f"\nTiny Lots (<0.1 acre) with High Value (>$500k): {len(oddities['tiny_acreage_high_value'])}")
    for item in oddities['tiny_acreage_high_value'][:5]:
        print(f"  - {item['owner'][:40]} ({item['acreage']:.3f} ac, ${item['total_value']:,})")
    
    print(f"\nLarge Lots (>50 ac) with Low Value (<$100k): {len(oddities['large_acreage_low_value'])}")
    for item in oddities['large_acreage_low_value'][:5]:
        print(f"  - {item['owner'][:40]} ({item['acreage']:.1f} ac, ${item['total_value']:,}, Class {item['class']})")
    
    print(f"\nPotential Duplicate Entries (same owner/address, 4+ parcels): {len(oddities['potential_duplicates'])}")
    for item in oddities['potential_duplicates'][:10]:
        print(f"  - {item['owner'][:40]} - {item['parcel_count']} parcels at similar address")
    
    print(f"\nZoning Distribution:")
    for zone, count in list(oddities['unusual_zones'].items())[:15]:
        print(f"  {zone}: {count:,}")
    
    # 8. LLC Analysis Deep Dive
    print(f"\n{'='*70}")
    print("8. LLC DEEP DIVE")
    print(f"{'='*70}")
    
    llcs = []
    for r in records:
        owner = clean_owner_name(r.get('owner_name', ''))
        if classify_entity(owner) == 'LLC':
            llcs.append({
                'name': owner,
                'value': r.get('total_value', 0),
                'class': r.get('property_class', 0),
                'district': r.get('district', ''),
                'acreage': r.get('acreage', 0)
            })
    
    print(f"\nTotal LLCs: {len(llcs):,}")
    
    # Aggregate LLC properties
    llc_agg = defaultdict(lambda: {'count': 0, 'total_value': 0, 'classes': Counter(), 'districts': Counter()})
    for llc in llcs:
        name = llc['name']
        llc_agg[name]['count'] += 1
        llc_agg[name]['total_value'] += llc['value']
        llc_agg[name]['classes'][llc['class']] += 1
        llc_agg[name]['districts'][llc['district']] += 1
    
    print(f"Unique LLC Names: {len(llc_agg):,}")
    
    # LLCs with multiple properties
    multi_llcs = {k: v for k, v in llc_agg.items() if v['count'] >= 3}
    print(f"LLCs with 3+ Properties: {len(multi_llcs)}")
    
    print("\nTop LLCs by Property Count:")
    for name, info in sorted(multi_llcs.items(), key=lambda x: -x[1]['count'])[:15]:
        classes = ', '.join([f"C{c}" for c, _ in info['classes'].most_common(3)])
        print(f"  {name[:45]:<47} {info['count']:>3} props  ${info['total_value']:>12,}  [{classes}]")
    
    print("\nTop LLCs by Total Value:")
    for name, info in sorted(llc_agg.items(), key=lambda x: -x[1]['total_value'])[:15]:
        print(f"  {name[:45]:<47} {info['count']:>3} props  ${info['total_value']:>12,}")
    
    # 9. Summary Statistics
    print(f"\n{'='*70}")
    print("9. SUMMARY STATISTICS")
    print(f"{'='*70}")
    
    total_value = sum(r.get('total_value', 0) for r in records)
    total_land = sum(r.get('land_value', 0) for r in records)
    total_improvements = sum(r.get('improvement_value', 0) for r in records)
    
    individual_value = sum(r.get('total_value', 0) for r in records if classify_entity(clean_owner_name(r.get('owner_name', ''))) == 'Individual')
    llc_value = sum(r.get('total_value', 0) for r in records if classify_entity(clean_owner_name(r.get('owner_name', ''))) == 'LLC')
    corp_value = sum(r.get('total_value', 0) for r in records if classify_entity(clean_owner_name(r.get('owner_name', ''))) == 'Corporation')
    
    print(f"\nTotal Property Value: ${total_value:,}")
    print(f"  Land Value: ${total_land:,} ({total_land/total_value*100:.1f}%)")
    print(f"  Improvement Value: ${total_improvements:,} ({total_improvements/total_value*100:.1f}%)")
    
    print(f"\nValue by Entity Type:")
    print(f"  Individuals: ${individual_value:,} ({individual_value/total_value*100:.1f}%)")
    print(f"  LLCs: ${llc_value:,} ({llc_value/total_value*100:.1f}%)")
    print(f"  Corporations: ${corp_value:,} ({corp_value/total_value*100:.1f}%)")

if __name__ == '__main__':
    main()
