#!/usr/bin/env python3
"""
Generate Real Estate Owner Analysis data for all years (2021-2025).
Outputs JSON files for website consumption.

Includes:
- Entity type classification and trends
- LLC ownership network analysis (common addresses)
- Property investigations (anomalies, high-value properties)
- Multi-year comparison data
"""

import json
import re
from collections import defaultdict, Counter
from pathlib import Path
from datetime import datetime

def clean_owner_name(raw_name):
    """Extract clean owner name from raw field (which may have embedded tax data)"""
    if not raw_name:
        return ""
    name = re.sub(r'\s+FH\s+[\d,\.]+.*$', '', raw_name)
    name = re.sub(r'\s+SH\s+[\d,\.]+.*$', '', name)
    return name.strip()

def classify_entity(name):
    """Classify owner by entity type"""
    name_upper = name.upper()
    
    if any(x in name_upper for x in ['COUNTY OF', 'CITY OF', 'TOWN OF', 'STATE OF', 
                                      'COMMONWEALTH', 'UNITED STATES', 'U S A',
                                      'VIRGINIA DEPT', 'VA DEPT', 'BOARD OF SUPERVISORS',
                                      'SCHOOL BOARD', 'SANITATION', 'WATER AUTH']):
        return 'Government'
    
    if any(x in name_upper for x in ['CHURCH', 'CHAPEL', 'MINISTRY', 'MINISTRIES', 
                                      'BAPTIST', 'METHODIST', 'LUTHERAN', 'CATHOLIC',
                                      'PRESBYTERIAN', 'EPISCOPAL', 'ASSEMBLY OF GOD',
                                      'CONGREGATION', 'DIOCESE', 'PARISH', 'MOSQUE',
                                      'SYNAGOGUE', 'TEMPLE', 'BIBLE', 'GOSPEL']):
        return 'Religious'
    
    if any(x in name_upper for x in ['FOUNDATION', 'ASSOC', 'ASSOCIATION', 'SOCIETY',
                                      'CLUB', 'LEGION', 'VFW', 'LIONS', 'ROTARY',
                                      'KIWANIS', 'ELKS', 'MOOSE', 'LODGE', 'FRATERNAL',
                                      'CHARITABLE', 'CHARITY', 'NON-PROFIT', 'NONPROFIT']):
        return 'Non-Profit'
    
    if re.search(r'\bLLC\b|\bL\.?L\.?C\.?\b', name_upper):
        return 'LLC'
    
    if re.search(r'\bLC\b', name_upper) and not any(x in name_upper for x in ['ELEC', 'CALC']):
        return 'LLC'  # LC is often used interchangeably with LLC in VA
    
    if any(x in name_upper for x in [' INC', ' CORP', ' CO ', ' COMPANY', 
                                      'INCORPORATED', 'CORPORATION', 'ENTERPRISES']):
        return 'Corporation'
    
    if re.search(r'\bLP\b|\bL\.?P\.?\b|LIMITED PARTNERSHIP', name_upper):
        return 'Limited Partnership'
    
    if any(x in name_upper for x in ['TRUST', 'TRUSTEE', 'REVOCABLE', 'IRREVOCABLE',
                                      'LIVING TRUST', 'FAMILY TRUST', 'TR ']):
        return 'Trust'
    
    if any(x in name_upper for x in ['ESTATE OF', 'ESTATE', ' EST ', 'HEIRS OF',
                                      'HEIRS', 'DEVISEES']):
        return 'Estate'
    
    if any(x in name_upper for x in ['BANK', 'MORTGAGE', 'FINANCIAL', 'CREDIT UNION',
                                      'SAVINGS', 'LENDING']):
        return 'Financial Institution'
    
    if any(x in name_upper for x in ['ELECTRIC', 'POWER', 'GAS', 'TELEPHONE',
                                      'COMMUNICATIONS', 'VERIZON', 'AT&T', 'COMCAST',
                                      'DOMINION', 'SHENANDOAH VALLEY ELEC']):
        return 'Utility'
    
    if any(x in name_upper for x in ['HOA', 'HOMEOWNERS', 'HOME OWNERS', 'CONDO',
                                      'CONDOMINIUM', 'PROPERTY OWNERS', 'POA']):
        return 'HOA/Condo'
    
    return 'Individual'

def extract_last_name(name):
    """Try to extract last name from individual owner names"""
    name = name.strip()
    if not name:
        return None
    
    entity_keywords = ['LLC', 'INC', 'CORP', 'TRUST', 'CHURCH', 'BANK', 
                       'COUNTY', 'ESTATE', 'FOUNDATION', 'ASSOC', ' LC']
    if any(kw in name.upper() for kw in entity_keywords):
        return None
    
    parts = name.split()
    if not parts:
        return None
    
    if ',' in name:
        last_name = name.split(',')[0].strip()
        last_name = re.sub(r'\s+(JR|SR|II|III|IV)\.?$', '', last_name, flags=re.IGNORECASE)
        return last_name.upper()
    
    first_word = parts[0].strip()
    if len(parts) >= 2 and parts[0].upper() not in ['THE', 'A', 'AN']:
        return first_word.upper()
    
    return None

def extract_state(city_state_zip):
    """Extract state from city/state/zip field"""
    if not city_state_zip or not isinstance(city_state_zip, str):
        return None
    state_match = re.search(r'\b([A-Z]{2})\s+\d{5}', city_state_zip)
    if state_match:
        return state_match.group(1)
    return None

def analyze_llc_networks(records):
    """
    Analyze LLC ownership networks by finding LLCs that share mailing addresses.
    This indicates common ownership/management.
    """
    # Group LLCs by mailing address
    addr_to_llcs = defaultdict(list)
    
    for r in records:
        owner = clean_owner_name(r.get('owner_name', ''))
        entity_type = classify_entity(owner)
        
        if entity_type == 'LLC':
            # Normalize address for grouping
            addr = (r.get('owner_address', '') or '')[:40].strip().upper()
            if addr and len(addr) > 5:
                addr_to_llcs[addr].append({
                    'name': owner,
                    'value': r.get('total_value', 0) or 0,
                    'parcel': r.get('parcel_code', ''),
                    'district': r.get('district', ''),
                    'property_class': r.get('property_class')
                })
    
    # Find addresses with multiple distinct LLCs
    networks = []
    for addr, llcs in addr_to_llcs.items():
        # Group by LLC name
        unique_llcs = defaultdict(lambda: {'value': 0, 'count': 0, 'parcels': [], 'districts': set()})
        for llc in llcs:
            name_key = llc['name'][:40]  # Normalize name length
            unique_llcs[name_key]['value'] += llc['value']
            unique_llcs[name_key]['count'] += 1
            unique_llcs[name_key]['parcels'].append(llc['parcel'])
            unique_llcs[name_key]['districts'].add(llc['district'])
            unique_llcs[name_key]['full_name'] = llc['name']
        
        # Only include if 3+ distinct LLCs at same address
        if len(unique_llcs) >= 3:
            total_val = sum(u['value'] for u in unique_llcs.values())
            total_props = sum(u['count'] for u in unique_llcs.values())
            
            llc_list = []
            for name, info in sorted(unique_llcs.items(), key=lambda x: -x[1]['value']):
                llc_list.append({
                    'name': info.get('full_name', name)[:50],
                    'properties': info['count'],
                    'value': info['value'],
                    'districts': list(info['districts'])
                })
            
            networks.append({
                'address': addr,
                'llc_count': len(unique_llcs),
                'property_count': total_props,
                'total_value': total_val,
                'llcs': llc_list[:15]  # Top 15 LLCs per network
            })
    
    # Sort by total value
    networks.sort(key=lambda x: -x['total_value'])
    return networks[:50]  # Top 50 networks

def analyze_property_investigations(records):
    """
    Identify unusual/noteworthy properties for investigation.
    """
    investigations = {
        'high_value_agricultural': [],
        'high_value_individuals': [],
        'classification_anomalies': [],
        'largest_landowners': []
    }
    
    # Find high-value agricultural properties (Class 2 with large improvements)
    for r in records:
        pclass = r.get('property_class')
        improvements = r.get('improvement_value', 0) or 0
        total = r.get('total_value', 0) or 0
        
        # Agricultural with >$5M in improvements is unusual
        if pclass == 2 and improvements > 5000000:
            owner = clean_owner_name(r.get('owner_name', ''))
            investigations['high_value_agricultural'].append({
                'parcel': r.get('parcel_code', ''),
                'owner': owner[:50],
                'land_value': r.get('land_value', 0) or 0,
                'improvement_value': improvements,
                'total_value': total,
                'district': r.get('district', ''),
                'zone': r.get('zone', ''),
                'acreage': r.get('acreage'),
                'notes': 'High-value improvements on agricultural land - likely processing facility'
            })
    
    # Sort and limit
    investigations['high_value_agricultural'].sort(key=lambda x: -x['total_value'])
    investigations['high_value_agricultural'] = investigations['high_value_agricultural'][:20]
    
    # Find top individual property holders (non-LLC, non-Corp)
    individual_holdings = defaultdict(lambda: {'value': 0, 'count': 0, 'properties': []})
    for r in records:
        owner = clean_owner_name(r.get('owner_name', ''))
        entity_type = classify_entity(owner)
        
        if entity_type == 'Individual':
            individual_holdings[owner]['value'] += r.get('total_value', 0) or 0
            individual_holdings[owner]['count'] += 1
            if len(individual_holdings[owner]['properties']) < 5:
                individual_holdings[owner]['properties'].append({
                    'parcel': r.get('parcel_code', ''),
                    'value': r.get('total_value', 0) or 0,
                    'district': r.get('district', '')
                })
    
    for owner, info in sorted(individual_holdings.items(), key=lambda x: -x[1]['value'])[:25]:
        investigations['high_value_individuals'].append({
            'owner': owner[:50],
            'total_value': info['value'],
            'property_count': info['count'],
            'top_properties': info['properties']
        })
    
    # Find largest landowners by acreage
    owner_acreage = defaultdict(lambda: {'acreage': 0, 'value': 0, 'count': 0})
    for r in records:
        owner = clean_owner_name(r.get('owner_name', ''))
        acreage = r.get('acreage')
        if acreage and isinstance(acreage, (int, float)) and acreage < 10000:  # Filter bad data
            owner_acreage[owner]['acreage'] += acreage
            owner_acreage[owner]['value'] += r.get('total_value', 0) or 0
            owner_acreage[owner]['count'] += 1
    
    for owner, info in sorted(owner_acreage.items(), key=lambda x: -x[1]['acreage'])[:25]:
        if info['acreage'] >= 50:  # At least 50 acres
            investigations['largest_landowners'].append({
                'owner': owner[:50],
                'total_acreage': round(info['acreage'], 1),
                'total_value': info['value'],
                'property_count': info['count'],
                'value_per_acre': round(info['value'] / info['acreage']) if info['acreage'] > 0 else 0
            })
    
    return investigations

def analyze_multi_year_comparison(all_years_data):
    """
    Generate detailed multi-year comparison data for trends visualization.
    """
    if len(all_years_data) < 2:
        return {}
    
    years = [d['year'] for d in all_years_data]
    
    # Entity type percentages by year (by count)
    entity_by_count = {}
    entity_by_value = {}
    
    for entity_type in ['Individual', 'LLC', 'Trust', 'Corporation', 'Estate', 'Non-Profit']:
        entity_by_count[entity_type] = []
        entity_by_value[entity_type] = []
        
        for year_data in all_years_data:
            # Find this entity type in breakdown
            found = False
            for eb in year_data['entity_breakdown']:
                if eb['type'] == entity_type:
                    entity_by_count[entity_type].append(eb['pct_records'])
                    entity_by_value[entity_type].append(eb['pct_value'])
                    found = True
                    break
            if not found:
                entity_by_count[entity_type].append(0)
                entity_by_value[entity_type].append(0)
    
    # Calculate absolute values and growth rates
    first = all_years_data[0]
    last = all_years_data[-1]
    
    growth_rates = {}
    for entity_type in ['Individual', 'LLC', 'Trust', 'Corporation']:
        first_val = 0
        last_val = 0
        for eb in first['entity_breakdown']:
            if eb['type'] == entity_type:
                first_val = eb['total_value']
                break
        for eb in last['entity_breakdown']:
            if eb['type'] == entity_type:
                last_val = eb['total_value']
                break
        
        if first_val > 0:
            growth_rates[entity_type] = {
                'first_year_value': first_val,
                'last_year_value': last_val,
                'growth_pct': round(((last_val - first_val) / first_val) * 100, 1),
                'absolute_change': last_val - first_val
            }
    
    # Year-over-year changes
    yoy_changes = []
    for i in range(1, len(all_years_data)):
        prev = all_years_data[i-1]
        curr = all_years_data[i]
        
        yoy_changes.append({
            'from_year': prev['year'],
            'to_year': curr['year'],
            'value_change': curr['total_value'] - prev['total_value'],
            'value_change_pct': round(((curr['total_value'] - prev['total_value']) / prev['total_value']) * 100, 1),
            'record_change': curr['total_records'] - prev['total_records'],
            'llc_count_change': curr['summary']['unique_llcs'] - prev['summary']['unique_llcs']
        })
    
    return {
        'years': years,
        'entity_by_count': entity_by_count,
        'entity_by_value': entity_by_value,
        'growth_rates': growth_rates,
        'year_over_year': yoy_changes,
        'summary': {
            'total_value_growth_pct': round(((last['total_value'] - first['total_value']) / first['total_value']) * 100, 1),
            'record_growth_pct': round(((last['total_records'] - first['total_records']) / first['total_records']) * 100, 1),
            'fastest_growing_entity': max(growth_rates.items(), key=lambda x: x[1]['growth_pct'])[0] if growth_rates else None,
            'fastest_growth_rate': max(growth_rates.values(), key=lambda x: x['growth_pct'])['growth_pct'] if growth_rates else 0
        }
    }

def analyze_year(records, year):
    """Analyze a single year's data and return structured results"""
    
    # Entity type classification
    entity_counts = Counter()
    entity_values = defaultdict(int)
    
    for r in records:
        owner = clean_owner_name(r.get('owner_name', ''))
        entity_type = classify_entity(owner)
        entity_counts[entity_type] += 1
        entity_values[entity_type] += r.get('total_value', 0) or 0
    
    total_records = len(records)
    total_value = sum(entity_values.values())
    
    entity_breakdown = []
    for entity_type, count in entity_counts.most_common():
        value = entity_values[entity_type]
        entity_breakdown.append({
            'type': entity_type,
            'count': count,
            'pct_records': round((count / total_records) * 100, 1) if total_records > 0 else 0,
            'total_value': value,
            'pct_value': round((value / total_value) * 100, 1) if total_value > 0 else 0
        })
    
    # Common last names
    last_names = Counter()
    last_name_values = defaultdict(int)
    
    for r in records:
        owner = clean_owner_name(r.get('owner_name', ''))
        if classify_entity(owner) == 'Individual':
            ln = extract_last_name(owner)
            if ln and len(ln) > 1:
                last_names[ln] += 1
                last_name_values[ln] += r.get('total_value', 0) or 0
    
    top_last_names = []
    for ln, count in last_names.most_common(30):
        value = last_name_values[ln]
        top_last_names.append({
            'name': ln,
            'properties': count,
            'total_value': value,
            'avg_value': round(value / count) if count > 0 else 0
        })
    
    # High value owners (all types)
    owner_data = defaultdict(lambda: {'total_value': 0, 'property_count': 0, 'entity_type': '', 'districts': set()})
    for r in records:
        owner = clean_owner_name(r.get('owner_name', ''))
        if not owner:
            continue
        owner_data[owner]['total_value'] += r.get('total_value', 0) or 0
        owner_data[owner]['property_count'] += 1
        owner_data[owner]['entity_type'] = classify_entity(owner)
        owner_data[owner]['districts'].add(r.get('district', ''))
    
    sorted_by_value = sorted(owner_data.items(), key=lambda x: x[1]['total_value'], reverse=True)
    top_owners_by_value = []
    for owner, info in sorted_by_value[:50]:
        top_owners_by_value.append({
            'owner': owner[:60],
            'properties': info['property_count'],
            'total_value': info['total_value'],
            'entity_type': info['entity_type'],
            'districts': list(info['districts'])
        })
    
    # Multi-property owners
    sorted_by_count = sorted(owner_data.items(), key=lambda x: x[1]['property_count'], reverse=True)
    multi_property_owners = []
    for owner, info in sorted_by_count[:50]:
        if info['property_count'] >= 5:
            multi_property_owners.append({
                'owner': owner[:60],
                'properties': info['property_count'],
                'total_value': info['total_value'],
                'entity_type': info['entity_type'],
                'avg_value': round(info['total_value'] / info['property_count']) if info['property_count'] > 0 else 0
            })
    
    # Property class analysis
    class_names = {
        1: 'Residential', 2: 'Agricultural/Undeveloped', 3: 'Multi-Family',
        4: 'Commercial', 5: 'Industrial', 6: 'Land Use (Deferred)',
        7: 'Public Service', 8: 'Exempt', 9: 'Mineral'
    }
    
    class_stats = defaultdict(lambda: {'count': 0, 'total_value': 0, 'entity_types': Counter()})
    for r in records:
        pclass = r.get('property_class')
        if pclass is None:
            continue
        owner = clean_owner_name(r.get('owner_name', ''))
        entity_type = classify_entity(owner)
        value = r.get('total_value', 0) or 0
        
        class_stats[pclass]['count'] += 1
        class_stats[pclass]['total_value'] += value
        class_stats[pclass]['entity_types'][entity_type] += 1
    
    property_classes = []
    for pclass in sorted([k for k in class_stats.keys() if k is not None]):
        stats = class_stats[pclass]
        entity_breakdown_class = []
        for etype, cnt in stats['entity_types'].most_common(5):
            pct = round((cnt / stats['count']) * 100, 1) if stats['count'] > 0 else 0
            entity_breakdown_class.append({'type': etype, 'count': cnt, 'pct': pct})
        
        property_classes.append({
            'class': pclass,
            'name': class_names.get(pclass, f'Class {pclass}'),
            'count': stats['count'],
            'total_value': stats['total_value'],
            'avg_value': round(stats['total_value'] / stats['count']) if stats['count'] > 0 else 0,
            'entity_breakdown': entity_breakdown_class
        })
    
    # Out of state analysis
    states = Counter()
    out_of_state_owners = defaultdict(lambda: {'state': '', 'total_value': 0, 'count': 0})
    
    for r in records:
        city_state_zip = r.get('owner_city_state_zip', '') or ''
        if not isinstance(city_state_zip, str):
            continue
        state = extract_state(city_state_zip)
        if state:
            states[state] += 1
            if state != 'VA':
                owner = clean_owner_name(r.get('owner_name', ''))
                out_of_state_owners[owner]['state'] = state
                out_of_state_owners[owner]['total_value'] += r.get('total_value', 0) or 0
                out_of_state_owners[owner]['count'] += 1
    
    state_distribution = [{'state': s, 'count': c, 'pct': round((c/total_records)*100, 2)} 
                          for s, c in states.most_common(20)]
    
    top_out_of_state = []
    for owner, info in sorted(out_of_state_owners.items(), key=lambda x: -x[1]['total_value'])[:30]:
        top_out_of_state.append({
            'owner': owner[:50],
            'state': info['state'],
            'properties': info['count'],
            'total_value': info['total_value']
        })
    
    # LLC deep dive
    llc_agg = defaultdict(lambda: {'count': 0, 'total_value': 0, 'classes': Counter(), 'districts': set()})
    for r in records:
        owner = clean_owner_name(r.get('owner_name', ''))
        if classify_entity(owner) == 'LLC':
            llc_agg[owner]['count'] += 1
            llc_agg[owner]['total_value'] += r.get('total_value', 0) or 0
            pclass = r.get('property_class')
            if pclass:
                llc_agg[owner]['classes'][pclass] += 1
            llc_agg[owner]['districts'].add(r.get('district', ''))
    
    llc_count = sum(info['count'] for info in llc_agg.values())
    
    top_llcs_by_count = []
    for name, info in sorted(llc_agg.items(), key=lambda x: -x[1]['count'])[:25]:
        if info['count'] >= 3:
            classes = [f"C{c}" for c, _ in info['classes'].most_common(3)]
            top_llcs_by_count.append({
                'name': name[:50],
                'properties': info['count'],
                'total_value': info['total_value'],
                'classes': classes,
                'districts': list(info['districts'])
            })
    
    top_llcs_by_value = []
    for name, info in sorted(llc_agg.items(), key=lambda x: -x[1]['total_value'])[:25]:
        top_llcs_by_value.append({
            'name': name[:50],
            'properties': info['count'],
            'total_value': info['total_value']
        })
    
    # Summary stats
    total_land = sum(r.get('land_value', 0) or 0 for r in records)
    total_improvements = sum(r.get('improvement_value', 0) or 0 for r in records)
    individual_value = entity_values.get('Individual', 0)
    llc_value = entity_values.get('LLC', 0)
    corp_value = entity_values.get('Corporation', 0)
    trust_value = entity_values.get('Trust', 0)
    
    return {
        'year': year,
        'total_records': total_records,
        'total_value': total_value,
        'summary': {
            'land_value': total_land,
            'improvement_value': total_improvements,
            'land_pct': round((total_land/total_value)*100, 1) if total_value > 0 else 0,
            'improvement_pct': round((total_improvements/total_value)*100, 1) if total_value > 0 else 0,
            'individual_value': individual_value,
            'individual_pct': round((individual_value/total_value)*100, 1) if total_value > 0 else 0,
            'llc_value': llc_value,
            'llc_pct': round((llc_value/total_value)*100, 1) if total_value > 0 else 0,
            'corp_value': corp_value,
            'corp_pct': round((corp_value/total_value)*100, 1) if total_value > 0 else 0,
            'trust_value': trust_value,
            'trust_pct': round((trust_value/total_value)*100, 1) if total_value > 0 else 0,
            'unique_llcs': len(llc_agg),
            'total_llc_records': llc_count
        },
        'entity_breakdown': entity_breakdown,
        'top_last_names': top_last_names,
        'top_owners_by_value': top_owners_by_value,
        'multi_property_owners': multi_property_owners,
        'property_classes': property_classes,
        'state_distribution': state_distribution,
        'top_out_of_state': top_out_of_state,
        'llc_analysis': {
            'total_llcs': llc_count,
            'unique_llcs': len(llc_agg),
            'top_by_count': top_llcs_by_count,
            'top_by_value': top_llcs_by_value
        }
    }

def main():
    output_dir = Path('/home/ethan/code/fredco-schools/data/processed')
    
    # Load main real estate tax file (contains all years)
    main_tax_file = output_dir / 'real_estate_tax.json'
    print(f"Loading {main_tax_file}...")
    with open(main_tax_file) as f:
        all_data = json.load(f)
    
    all_records = all_data['records']
    
    years = [2021, 2022, 2023, 2024, 2025]
    all_years_data = []
    all_records_latest = []
    
    for year in years:
        # Filter records for this year
        records = [r for r in all_records if r['year'] == year]
        if not records:
            print(f"Warning: No records for {year}, skipping")
            continue
            
        print(f"Processing {year}...")
        year_analysis = analyze_year(records, year)
        all_years_data.append(year_analysis)
        
        # Keep latest year's records for network analysis
        if year == max(years):
            all_records_latest = records
        
        print(f"  - {year}: {len(records):,} records, ${year_analysis['total_value']:,} total value")
    
    # Analyze LLC networks (using latest year)
    print("\nAnalyzing LLC ownership networks...")
    llc_networks = analyze_llc_networks(all_records_latest)
    print(f"  Found {len(llc_networks)} networks with 3+ LLCs at same address")
    
    # Analyze property investigations
    print("Analyzing property investigations...")
    property_investigations = analyze_property_investigations(all_records_latest)
    print(f"  Found {len(property_investigations['high_value_agricultural'])} high-value agricultural properties")
    print(f"  Found {len(property_investigations['high_value_individuals'])} top individual holders")
    
    # Multi-year comparison
    print("Generating multi-year comparison...")
    multi_year_comparison = analyze_multi_year_comparison(all_years_data)
    
    # Create trend data across years
    trends = {
        'years': [d['year'] for d in all_years_data],
        'total_records': [d['total_records'] for d in all_years_data],
        'total_value': [d['total_value'] for d in all_years_data],
        'individual_pct': [d['summary']['individual_pct'] for d in all_years_data],
        'llc_pct': [d['summary']['llc_pct'] for d in all_years_data],
        'llc_value': [d['summary']['llc_value'] for d in all_years_data],
        'trust_pct': [d['summary']['trust_pct'] for d in all_years_data],
        'trust_value': [d['summary']['trust_value'] for d in all_years_data],
        'unique_llcs': [d['summary']['unique_llcs'] for d in all_years_data],
    }
    
    # Calculate growth rates
    if len(all_years_data) >= 2:
        first = all_years_data[0]
        last = all_years_data[-1]
        trends['value_growth_pct'] = round(((last['total_value'] - first['total_value']) / first['total_value']) * 100, 1)
        trends['llc_value_growth_pct'] = round(((last['summary']['llc_value'] - first['summary']['llc_value']) / first['summary']['llc_value']) * 100, 1) if first['summary']['llc_value'] > 0 else 0
        trends['llc_count_growth_pct'] = round(((last['summary']['unique_llcs'] - first['summary']['unique_llcs']) / first['summary']['unique_llcs']) * 100, 1) if first['summary']['unique_llcs'] > 0 else 0
        trends['trust_value_growth_pct'] = round(((last['summary']['trust_value'] - first['summary']['trust_value']) / first['summary']['trust_value']) * 100, 1) if first['summary']['trust_value'] > 0 else 0
    
    output = {
        'metadata': {
            'source': 'Frederick County Commissioner of Revenue - Real Estate Tax Book',
            'generated': datetime.now().isoformat(),
            'years_analyzed': years,
            'description': 'Real estate ownership patterns, entity classification, LLC networks, and trend analysis'
        },
        'trends': trends,
        'multi_year_comparison': multi_year_comparison,
        'llc_networks': llc_networks,
        'property_investigations': property_investigations,
        'annual_data': all_years_data
    }
    
    output_file = output_dir / 'real_estate_ownership_analysis.json'
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nOutput written to {output_file}")
    print(f"Total years analyzed: {len(all_years_data)}")
    
    # Print summary
    print("\n" + "="*70)
    print("MULTI-YEAR SUMMARY")
    print("="*70)
    print(f"\n{'Year':<8} {'Records':>10} {'Total Value':>18} {'LLC %':>8} {'Trust %':>8} {'Unique LLCs':>12}")
    print("-"*70)
    for d in all_years_data:
        print(f"{d['year']:<8} {d['total_records']:>10,} ${d['total_value']:>15,} {d['summary']['llc_pct']:>7.1f}% {d['summary']['trust_pct']:>7.1f}% {d['summary']['unique_llcs']:>12,}")
    
    if len(all_years_data) >= 2:
        print(f"\n5-Year Changes ({all_years_data[0]['year']}-{all_years_data[-1]['year']}):")
        print(f"  Total Value Growth: {trends['value_growth_pct']}%")
        print(f"  LLC Value Growth: {trends['llc_value_growth_pct']}%")
        print(f"  Trust Value Growth: {trends['trust_value_growth_pct']}%")
        print(f"  Unique LLC Growth: {trends['llc_count_growth_pct']}%")
    
    print("\n" + "="*70)
    print("TOP LLC NETWORKS (Common Ownership)")
    print("="*70)
    for net in llc_networks[:5]:
        print(f"\n{net['address']}:")
        print(f"  {net['llc_count']} LLCs, {net['property_count']} properties, ${net['total_value']:,}")

if __name__ == '__main__':
    main()
