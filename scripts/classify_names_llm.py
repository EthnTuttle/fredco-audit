#!/usr/bin/env python3
"""
Classify property owner surnames using local LLM.
Categorizes surnames by ethnic/cultural origin.
"""

import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime
import time

# Business indicators to filter out
# Note: ' LC' (with space) to avoid matching substrings like "FALCON"
BUSINESS_INDICATORS = [
    'LLC', ' LC', 'INC', 'CORP', 'CO ', 'LTD', ' LP', 'LLP', 'TRUST', 'TRUSTEE', 'ESTATE',
    'CHURCH', 'BANK', 'COUNTY', 'CITY', 'STATE', 'FEDERAL', 'PROPERTIES', 'PROPERTY',
    'INVESTMENTS', 'HOLDINGS', 'DEVELOPMENT', 'ENTERPRISES', 'ASSOCIATES', 'PARTNERS',
    'MANAGEMENT', 'SERVICES', 'COMPANY', 'FOUNDATION', 'ASSOCIATION', 'HOSPITAL',
    'SCHOOL', 'UNIVERSITY', 'CEMETERY', 'MINISTRY', 'BAPTIST', 'METHODIST',
    'LUTHERAN', 'PRESBYTERIAN', 'CATHOLIC', 'REALTY', 'RENTALS', 'STORAGE',
    'FARM', 'FARMS', 'RANCH', 'BUILDERS', 'CONSTRUCTION', 'ELECTRIC', 'UTILITY',
    'MORTGAGE', 'FINANCIAL', 'CAPITAL', 'ET AL', 'ETAL', 'ETALS', ' GROUP'
]


def is_business(name):
    """Check if name is a business entity."""
    name_upper = name.upper()
    return any(ind in name_upper for ind in BUSINESS_INDICATORS)


def extract_surname(raw_name):
    """Extract surname from raw record (LASTNAME FIRSTNAME MI format)."""
    if not raw_name or not isinstance(raw_name, str):
        return None
    
    clean = re.split(r'\s{3,}', raw_name)[0].strip()
    if is_business(clean):
        return None
    
    words = clean.upper().split()
    if not words:
        return None
    
    # Handle compound surnames
    if len(words) >= 2 and words[0] in ['DE', 'LA', 'DEL', 'VAN', 'VON', 'MC', 'O', 'DI', 'DA', 'LE', 'DU']:
        return ' '.join(words[:2])
    
    # First word is surname
    surname = words[0]
    
    # Skip single letters or very short
    if len(surname) < 2:
        return None
    
    return surname


def classify_surnames_batch(surnames, model="llama3.2:3b"):
    """Classify a batch of surnames using ollama."""
    if not surnames:
        return {}
    
    surnames_text = '\n'.join(surnames)
    
    prompt = f"""Classify each surname by ethnic/cultural origin. Use these categories ONLY:
- ANGLO (British/American: Smith, Jones, Miller, Brown, Williams, Johnson, Davis, Wilson, Taylor, Anderson, Thomas, Jackson, White, Harris, Martin, Thompson, Moore, Walker, Lewis, Hall)
- HISPANIC (Spanish/Latin: Garcia, Rodriguez, Martinez, Hernandez, Lopez, Gonzalez, Perez, Sanchez, Ramirez, Torres, Flores, Rivera, Gomez, Diaz, Cruz)
- ASIAN (East/South/SE Asian: Nguyen, Tran, Le, Pham, Kim, Park, Lee, Chen, Wang, Li, Liu, Zhang, Patel, Singh, Sharma, Kumar, Shah)
- MENA (Middle East/North Africa: Mohammed, Ahmed, Ali, Hassan, Hussein, Khan, Abbas, Ibrahim, Khalil, Omar)
- OTHER (European non-Anglo, African, etc.: Kowalski, Mueller, Rossi, O'Brien, Murphy, Nakamura)

Surnames:
{surnames_text}

Respond ONLY with surname and category, one per line (e.g., "SMITH - ANGLO"):"""

    try:
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        response = result.stdout.strip()
        
        # Parse responses
        results = {}
        for line in response.split('\n'):
            line = line.strip()
            if ' - ' in line:
                parts = line.split(' - ')
                if len(parts) >= 2:
                    surname = parts[0].strip().upper()
                    category = parts[1].strip().upper()
                    # Normalize category
                    if category in ['ANGLO', 'HISPANIC', 'ASIAN', 'MENA', 'OTHER']:
                        results[surname] = category
                    elif 'ANGLO' in category or 'AMERICAN' in category or 'BRITISH' in category:
                        results[surname] = 'ANGLO'
                    elif 'HISPANIC' in category or 'SPANISH' in category or 'LATIN' in category:
                        results[surname] = 'HISPANIC'
                    elif 'ASIAN' in category or 'CHINESE' in category or 'KOREAN' in category or 'VIETNAMESE' in category or 'INDIAN' in category or 'JAPANESE' in category:
                        results[surname] = 'ASIAN'
                    elif 'MIDDLE' in category or 'ARAB' in category or 'MUSLIM' in category:
                        results[surname] = 'MENA'
                    else:
                        results[surname] = 'OTHER'
        
        return results
        
    except subprocess.TimeoutExpired:
        return {}
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return {}


def main():
    print("="*60)
    print("SURNAME CLASSIFICATION USING LOCAL LLM")
    print("="*60)
    
    print("\nLoading property records...")
    with open('data/processed/real_estate_tax.json', 'r') as f:
        data = json.load(f)
    
    # Extract unique surnames from most recent year (2025)
    print("Extracting unique surnames from 2025...")
    surname_counts = Counter()
    for record in data['records']:
        if record.get('year') == 2025:
            surname = extract_surname(record.get('owner_name', ''))
            if surname:
                surname_counts[surname] += 1
    
    unique_surnames = list(surname_counts.keys())
    print(f"Found {len(unique_surnames):,} unique surnames")
    print(f"Total individual properties: {sum(surname_counts.values()):,}")
    
    # Process in batches
    batch_size = 30
    results = {}
    total_batches = (len(unique_surnames) + batch_size - 1) // batch_size
    
    print(f"\nClassifying surnames in {total_batches:,} batches (this may take a while)...")
    start_time = time.time()
    
    for i in range(0, len(unique_surnames), batch_size):
        batch = unique_surnames[i:i+batch_size]
        batch_num = i // batch_size + 1
        
        batch_results = classify_surnames_batch(batch)
        results.update(batch_results)
        
        # Progress update every 20 batches
        if batch_num % 20 == 0 or batch_num == total_batches:
            elapsed = time.time() - start_time
            rate = batch_num / elapsed if elapsed > 0 else 0
            eta = (total_batches - batch_num) / rate if rate > 0 else 0
            
            print(f"  Batch {batch_num:,}/{total_batches:,} | "
                  f"Classified: {len(results):,} | "
                  f"ETA: {eta/60:.1f}m")
        
        # Save checkpoint every 100 batches
        if batch_num % 100 == 0:
            checkpoint = {
                'timestamp': datetime.now().isoformat(),
                'processed': len(results),
                'results': results
            }
            with open('data/processed/surname_classification_checkpoint.json', 'w') as f:
                json.dump(checkpoint, f)
    
    # Calculate weighted results (by property count)
    category_counts = Counter()
    category_properties = Counter()
    
    for surname, count in surname_counts.items():
        category = results.get(surname, 'UNKNOWN')
        category_counts[category] += 1
        category_properties[category] += count
    
    total_surnames = sum(category_counts.values())
    total_properties = sum(category_properties.values())
    
    print("\n" + "="*60)
    print("CLASSIFICATION RESULTS")
    print("="*60)
    
    print(f"\nBy unique surnames ({total_surnames:,} total):")
    for cat in ['ANGLO', 'HISPANIC', 'ASIAN', 'MENA', 'OTHER', 'UNKNOWN']:
        count = category_counts[cat]
        pct = count / total_surnames * 100 if total_surnames > 0 else 0
        print(f"  {cat:12s}: {count:6,} ({pct:5.1f}%)")
    
    print(f"\nBy property ownership ({total_properties:,} individual properties):")
    for cat in ['ANGLO', 'HISPANIC', 'ASIAN', 'MENA', 'OTHER', 'UNKNOWN']:
        count = category_properties[cat]
        pct = count / total_properties * 100 if total_properties > 0 else 0
        print(f"  {cat:12s}: {count:6,} ({pct:5.1f}%)")
    
    # Save full results
    output = {
        'metadata': {
            'description': 'Surname classification by ethnic/cultural origin',
            'model': 'llama3.2:3b',
            'timestamp': datetime.now().isoformat(),
            'year_analyzed': 2025,
            'total_unique_surnames': len(unique_surnames),
            'total_individual_properties': sum(surname_counts.values())
        },
        'summary_by_surname': {
            cat: {
                'count': category_counts[cat],
                'percentage': round(category_counts[cat] / total_surnames * 100, 2) if total_surnames > 0 else 0
            }
            for cat in ['ANGLO', 'HISPANIC', 'ASIAN', 'MENA', 'OTHER', 'UNKNOWN']
        },
        'summary_by_property': {
            cat: {
                'count': category_properties[cat],
                'percentage': round(category_properties[cat] / total_properties * 100, 2) if total_properties > 0 else 0
            }
            for cat in ['ANGLO', 'HISPANIC', 'ASIAN', 'MENA', 'OTHER', 'UNKNOWN']
        },
        'surname_classifications': results,
        'surname_property_counts': dict(surname_counts.most_common()),
        'top_surnames_by_category': {
            cat: [(s, surname_counts[s]) for s in sorted(
                [s for s, c in results.items() if c == cat],
                key=lambda x: -surname_counts.get(x, 0)
            )[:20]]
            for cat in ['ANGLO', 'HISPANIC', 'ASIAN', 'MENA', 'OTHER']
        }
    }
    
    with open('data/processed/surname_classification.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nResults saved to data/processed/surname_classification.json")
    
    # Show top surnames by category
    print("\n" + "-"*60)
    print("TOP SURNAMES BY CATEGORY")
    print("-"*60)
    
    for cat in ['ANGLO', 'HISPANIC', 'ASIAN', 'MENA', 'OTHER']:
        surnames_in_cat = [(s, surname_counts[s]) for s in results if results[s] == cat]
        surnames_in_cat.sort(key=lambda x: -x[1])
        
        print(f"\n{cat} (top 10):")
        for surname, count in surnames_in_cat[:10]:
            print(f"  {surname:20s}: {count:,} properties")


if __name__ == '__main__':
    main()
