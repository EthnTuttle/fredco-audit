#!/usr/bin/env python3
"""
Parse GLM-OCR output into structured real estate tax records.

Converts raw OCR text from JSON files into structured property records
with improved schema compared to the original pdfplumber extraction.

Handles multiple OCR formats:
- Format 1: Standard 3-line (parcel+values, owner+details, city/state/zip)
- Format 2: Single-line with owner inline before values
- Format 3: Multi-line with owner on separate line

Features:
- GIS cross-reference: Falls back to Frederick County GIS data when OCR
  fails to extract owner information (using account_number as join key)
- Tracks owner_source: "ocr" or "gis" for traceability

Usage:
    python scripts/parse_ocr_output.py --input data/processed/ocr/ --output data/processed/real_estate_ocr.json
    python scripts/parse_ocr_output.py --input "data/processed/ocr/Real Estate 2021 Tax Book_ocr.json" --output data/processed/ocr/test_parsed.json
    python scripts/parse_ocr_output.py --input data/processed/ocr/ --no-gis  # Disable GIS lookup
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
GIS_LOOKUP_FILE = PROCESSED_DIR / "gis_owner_lookup.json"

# Global GIS lookup (loaded on demand)
_gis_lookup: Optional[dict] = None


def load_gis_lookup() -> dict:
    """Load GIS owner lookup data. Returns empty dict if file doesn't exist."""
    global _gis_lookup
    if _gis_lookup is not None:
        return _gis_lookup
    
    if not GIS_LOOKUP_FILE.exists():
        print(f"  Warning: GIS lookup file not found: {GIS_LOOKUP_FILE}")
        print("  Run: python scripts/download_gis_owners.py")
        _gis_lookup = {}
        return _gis_lookup
    
    with open(GIS_LOOKUP_FILE) as f:
        data = json.load(f)
    
    _gis_lookup = data.get("lookup", {})
    print(f"  Loaded GIS lookup: {len(_gis_lookup):,} entries")
    return _gis_lookup


def lookup_owner_from_gis(account_number: str) -> Optional[dict]:
    """
    Look up owner information from GIS data by account number.
    
    Returns dict with owner_name, owner_address, city_state_zip if found.
    """
    lookup = load_gis_lookup()
    if not lookup or not account_number:
        return None
    
    gis_data = lookup.get(account_number)
    if not gis_data:
        return None
    
    return {
        "owner_name": gis_data.get("owner_name"),
        "owner_address": gis_data.get("owner_address"),
        "owner_city_state_zip": gis_data.get("city_state_zip"),
    }

# Known districts in Frederick County (including common OCR errors)
DISTRICT_MAPPING = {
    # Back Creek
    "BACK CREEK": "Back Creek",
    "BACK CREEN": "Back Creek",
    "BACK CHECK": "Back Creek",
    "BACK ORDER": "Back Creek",
    "BACK CROSS": "Back Creek",
    "BACK CLOSER": "Back Creek",
    "BACK CKEER": "Back Creek",
    "BACK CRDER": "Back Creek",
    "BACK CREDIT": "Back Creek",
    "BACK CHKBK": "Back Creek",
    "HACK CREEK": "Back Creek",
    "HACK CHECK": "Back Creek",
    "SACS CREEK": "Back Creek",
    "SACK CREEK": "Back Creek",
    "SACI CREEK": "Back Creek",
    "RACE CREEK": "Back Creek",
    # Gainesboro
    "GAINESBORO": "Gainesboro",
    "GAINSBORO": "Gainesboro",
    "GAISERSBORG": "Gainesboro",
    "GAISBORO": "Gainesboro",
    "GAIESBURG": "Gainesboro",
    "GATHERSBURG": "Gainesboro",
    "GAUDENSESKO": "Gainesboro",
    "GAUDERSBO": "Gainesboro",
    "GUNPOWDERKO": "Gainesboro",
    "GUNSBORO": "Gainesboro",
    "GUESSBORO": "Gainesboro",
    "GUEESSBORO": "Gainesboro",
    "GUENESBORO": "Gainesboro",
    "GUNNESBORO": "Gainesboro",
    "GUNDESBURO": "Gainesboro",
    "GUNDESSKO": "Gainesboro",
    "GUTTERSCKO": "Gainesboro",
    "GAUZESBORO": "Gainesboro",
    "GAINESVILLE": "Gainesboro",
    "GAINSBOROUGH": "Gainesboro",
    "GAUNDEBORO": "Gainesboro",
    "GATNESBSRO": "Gainesboro",
    "GAINSSESKO": "Gainesboro",
    "GENBDGDN": "Gainesboro",
    "GEOSCIN": "Gainesboro",
    "GEOSYND": "Gainesboro",
    "GUESTHOUSE": "Gainesboro",
    "GUESSHOUS": "Gainesboro",
    "GUESSBORRO": "Gainesboro",
    "GUESSHORO": "Gainesboro",
    "GREENHOUSE": "Gainesboro",
    "GERBUYIN": "Gainesboro",
    "GRVGRDN": "Gainesboro",
    "GUNSSBSRO": "Gainesboro",
    "GUNNESS": "Gainesboro",
    # Opequon
    "OPEQUON": "Opequon",
    "OREGON": "Opequon",
    "OREGOUN": "Opequon",
    "CREQUIN": "Opequon",
    "OREOUIM": "Opequon",
    "OPTIONAL": "Opequon",
    "CERULEAN": "Opequon",
    # Redbud
    "RED BUD": "Redbud",
    "REDBUD": "Redbud",
    # Shawnee
    "SHAWNEE": "Shawnee",
    "SHANNEE": "Shawnee",
    "SHAWEE": "Shawnee",
    "SRAWHEE": "Shawnee",
    "SAWNEE": "Shawnee",
    "SWANEE": "Shawnee",
    "BRANHEE": "Shawnee",
    "SENABEE": "Shawnee",
    "SHANDER": "Shawnee",
    "SHOUSE": "Shawnee",
    "HAWKEE": "Shawnee",
    "SPRINGER": "Shawnee",
    # Stonewall
    "STONEWALL": "Stonewall",
    "STATEWALL": "Stonewall",
    "OTHERWALL": "Stonewall",
    "OTHERSALL": "Stonewall",
    "OTHERSOLL": "Stonewall",
    "OTHERSMALL": "Stonewall",
    "OTHERALL": "Stonewall",
    "STUESVALL": "Stonewall",
    "ROSENBLL": "Stonewall",
    "FIREWALL": "Stonewall",
    "SITESALL": "Stonewall",
    "STORESALE": "Stonewall",
    "STATEMAIL": "Stonewall",
    "SITEMAIL": "Stonewall",
    "STITTSVILLE": "Stonewall",
    "KERNEL": "Stonewall",
    "SKENESE": "Stonewall",
    "SKENSGALL": "Stonewall",
    "STEPHESALL": "Stonewall",
    # Stephens City
    "STEPHENS CITY": "Stephens City",
    "STEPHENS": "Stephens City",
    "STEPHEN": "Stephens City",
    "STEPHEN CITY": "Stephens City",
    "STEVENS CITY": "Stephens City",
    "STERNESS CITY": "Stephens City",
}

# Property class descriptions
PROPERTY_CLASSES = {
    1: "Residential",
    2: "Agricultural/Undeveloped",
    3: "Multi-Family",
    4: "Commercial",
    5: "Industrial",
    6: "Land Use (Deferred)",
    7: "Public Service",
    8: "Exempt",
    9: "Mineral",
}

# Common street suffixes for address parsing
STREET_SUFFIXES = r'(?:LN|DR|ST|CT|RD|AVE|BLVD|CIR|WAY|PL|TRL|PKWY|HWY|PIKE|RUN|LOOP|TER|SQ)'
# Same but as a list for filtering
STREET_SUFFIX_LIST = ['LN', 'DR', 'ST', 'CT', 'RD', 'AVE', 'BLVD', 'CIR', 'WAY', 'PL', 'TRL', 'PKWY', 'HWY', 'PIKE', 'RUN', 'LOOP', 'TER', 'SQ']

# State abbreviations
STATE_ABBREVS = r'(?:VA|MD|WV|PA|DC|NC|OK|NR|NY|NJ|DE|OH|FL|GA|SC|TN|KY|IN|IL|CA|TX|AZ)'


def extract_year_from_filename(filename: str) -> Optional[int]:
    """Extract year from filename like 'Real Estate 2021 Tax Book.pdf'."""
    match = re.search(r'20(\d{2})', filename)
    if match:
        return 2000 + int(match.group(1))
    return None


def normalize_parcel_code(raw: str) -> str:
    """Normalize parcel code by removing extra spaces and collapsing dashes."""
    if not raw:
        return ""
    normalized = re.sub(r'\s+', '', raw)  # Remove spaces
    normalized = re.sub(r'-+', '-', normalized)  # Collapse multiple dashes
    normalized = normalized.strip('-')  # Remove leading/trailing dashes
    return normalized


def split_parcel_from_owner(text: str) -> tuple[str, str]:
    """
    Split concatenated parcel+owner text.
    
    Handles cases like:
    - "64B- - A- - 38 A P R MINI STORAGE LLC 127 MERCEDES CT..."
    - "74 - - A- - 35-A A P R MINI STORAGE LLC..."
    - "16 - - A- - 5-I AARDAPPEL WILLIAM C AARDAPPEL JENNIFER M 282..."
    
    Returns (parcel_raw, remaining_text)
    """
    # Strategy: Scan forward looking for the transition from parcel to owner
    # Parcel codes: mix of digits, single letters, dashes, spaces (e.g., "64B- - A- - 38")
    # Owner names: Multiple consecutive uppercase words (2+ chars each)
    
    parts = text.split()
    if len(parts) < 2:
        return text, ""
    
    # Find the last parcel-like token
    # Parcel tokens: contain digits OR are single letters OR are just dashes
    last_parcel_idx = 0
    
    for i, part in enumerate(parts):
        # Is this part parcel-like?
        has_digit = bool(re.search(r'\d', part))
        is_dash_only = part == '-'
        is_single_letter = bool(re.match(r'^[A-Z]$', part))
        is_parcel_suffix = bool(re.match(r'^[\dA-Z]+-?[A-Z]?$', part))  # Like "35-A", "5-I"
        
        if has_digit or is_dash_only or is_single_letter or is_parcel_suffix:
            last_parcel_idx = i
        else:
            # This is a word without digits - could be owner name start
            # Check if remaining text has address/city patterns
            remaining = ' '.join(parts[i:])
            
            # Look for clear owner indicators
            has_address = bool(re.search(rf'\b\d+\s+[A-Z][A-Z]+\s+{STREET_SUFFIXES}\b', remaining))
            has_po_box = bool(re.search(r'\bPO\s+BOX\s+\d+', remaining, re.IGNORECASE))
            has_city_zip = bool(re.search(rf'\b{STATE_ABBREVS}\s+\d{{5}}', remaining))
            has_llc_etc = bool(re.search(r'\b(?:LLC|INC|CORP|TRUST|TRUSTEE|JR|SR|II|III)\b', remaining))
            
            # Also check if this word starts what looks like a name
            # Names: Multiple 2+ char uppercase words
            word_count = 0
            for w in parts[i:i+4]:  # Look at next 4 words
                if re.match(r'^[A-Z]{2,}$', w) and w not in ['AC', 'CL', 'ZN', 'EN', 'IN', 'DB', 'FH', 'SH', 'THE', 'LOT', 'UNIT']:
                    word_count += 1
                elif re.match(r'^[&]$', w):  # Allow & in names
                    word_count += 1
                else:
                    break
            
            is_likely_name = word_count >= 2
            
            if (has_address or has_po_box or has_city_zip or has_llc_etc) and is_likely_name:
                # Found owner start
                parcel_raw = ' '.join(parts[:i])
                remaining_text = ' '.join(parts[i:])
                return parcel_raw, remaining_text
    
    # If we get here, no clear owner found - return everything as parcel
    return text, ""


def find_district(text: str) -> Optional[str]:
    """Find district name in text, handling OCR errors."""
    text_upper = text.upper()
    for key, value in DISTRICT_MAPPING.items():
        if key in text_upper:
            return value
    return None


def extract_city_state_zip(text: str) -> Optional[str]:
    """Extract city, state, zip from text."""
    # Pattern: CITY STATE ZIP (e.g., "MIDDLETOWN VA 22645-1555")
    # City names are typically 1-3 words, not containing street suffixes
    pattern = rf'([A-Z][A-Z]+(?:\s+[A-Z]+)?)\s+({STATE_ABBREVS})\s+(\d{{5}}(?:-\d{{4}})?)'
    match = re.search(pattern, text)
    if match:
        city = match.group(1).strip()
        state = match.group(2)
        zip_code = match.group(3)
        # Filter out street suffixes that might have been captured as city
        city_words = city.split()
        # If first word is a street suffix, it's wrong
        if city_words and city_words[0] in STREET_SUFFIX_LIST:
            # Try to find the real city after the suffix
            remaining = text[match.start() + len(city_words[0]):].strip()
            inner_match = re.search(rf'([A-Z][A-Z]+(?:\s+[A-Z]+)?)\s+({STATE_ABBREVS})\s+(\d{{5}}(?:-\d{{4}})?)', remaining)
            if inner_match:
                city = inner_match.group(1).strip()
                state = inner_match.group(2)
                zip_code = inner_match.group(3)
            else:
                return None
        # Still filter out any remaining street suffixes
        if any(suf in city.split() for suf in STREET_SUFFIX_LIST):
            return None
        return f"{city} {state} {zip_code}"
    return None


def extract_address(text: str) -> Optional[str]:
    """Extract street address from text."""
    # Pattern: NUMBER STREET NAME SUFFIX (e.g., "230 DEPENDENCE LN")
    pattern = rf'(\d+\s+[A-Z][A-Z\s]+{STREET_SUFFIXES})'
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    
    # Try PO Box
    po_match = re.search(r'(PO\s+BOX\s+\d+)', text, re.IGNORECASE)
    if po_match:
        return po_match.group(1).upper()
    
    return None


def extract_owner_details(text: str) -> dict:
    """
    Extract owner details (acreage, class, zone, deed) from text.
    Pattern: AC X.XX CL N ZN XX [DEED]
    
    OCR variants found in Anthropic output:
    - AC prefix: AC (96%), AZ (4%), AG, AY, AD (rare)
    - CL prefix: CL (90%), C1./C1 (7%), CI./CI (2%), C./CS/CC (1%)
    - ZN prefix: 2N (60%), 2R (10%), 1R (5%), ZN (5%), 1B/TR/IR/18/2M/LR/IN/TN/IM/IS... (rest)
    """
    result = {
        "acreage": None,
        "property_class": None,
        "zone": None,
        "deed_reference": None,
    }
    
    # Comprehensive pattern for AC/AZ CL/C1 ZN/2N and all OCR variants
    # AC variants: AC, AZ (most common misread)
    # CL variants: CL, C1, C1., CI, CI., C., CS, CC, CL.
    # ZN variants: ZN, 2N, 2R, 1R, 1B, TR, IR, 18, 2M, LR, IN, TN, IM, IS, 1S, IB, ER, I8, 2B, 2W, EN, etc.
    ac_pattern = r'(?:AC|AZ|AG|AY|AD)'
    cl_pattern = r'(?:CL\.?|C1\.?|CI\.?|C\.|CS|CC|CCL|CT|CR|CM|CE)'
    zn_pattern = r'(?:ZN|2N|2R|1R|1B|TR|IR|18|2M|LR|IN|TN|IM|IS|1S|IB|ER|I8|2B|2W|EN|JR|LB|FR|78|7R|LS|EB|1W|TA|TB)'
    
    pattern = rf'{ac_pattern}\s+([\d\.]+)\s+{cl_pattern}\s+(\d+)\s+{zn_pattern}\s+(\w+)'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        try:
            result["acreage"] = float(match.group(1))
        except ValueError:
            pass
        try:
            result["property_class"] = int(match.group(2))
        except ValueError:
            pass
        zone_val = match.group(3).upper()
        # Normalize common zone misreads
        zone_val = normalize_zone(zone_val)
        result["zone"] = zone_val
        
        # Look for deed reference after zone
        after_zone = text[match.end():].strip()
        # Deed patterns: "2013 0001596 00" or "DB 961/1376" or "IB 734/ 651"
        deed_match = re.match(r'^((?:[DI]B\s+)?\d+[\s/]\d+(?:\s+\d+)?)', after_zone)
        if deed_match:
            result["deed_reference"] = deed_match.group(1).strip()
    
    return result


def normalize_zone(zone: str) -> str:
    """Normalize OCR-garbled zone codes to standard Frederick County zones."""
    # Known Frederick County zones:
    # RA (Rural Area), RP (Residential Performance), RS (Residential Suburban)
    # R4, R5 (Residential)
    # B1, B2, B3 (Business), MH1 (Mobile Home), M1, M2 (Industrial)
    # MS (Medical Support), HE (Higher Education), EM (Extractive Mining)
    # OM (Office-Manufacturing), BP (Business Park)
    
    zone_map = {
        # Common OCR misreads for RA
        "8A": "RA", "BA": "RA", "SA": "RA", "KA": "RA", "AA": "RA",
        # Common OCR misreads for RP
        "8P": "RP", "SP": "RP",
        # Common OCR misreads for RS
        "8S": "RS", "BS": "RS",
        # Common OCR misreads for R4
        "84": "R4", "B4": "R4",
        # Common OCR misreads for R5
        "85": "R5", "B5": "R5",
        # Common OCR misreads for R2
        "82": "R2", "B2": "R2", "R2": "R2",
        # Common OCR misreads for R3
        "83": "R3", "B3": "R3", "R3": "R3",
        # Common OCR misreads for B1
        "8J": "B1",
        # Common OCR misreads for B2
        "87": "B2",
        # Common OCR misreads for MH1/MHL
        "MHL": "MH1", "MI": "MH1",
        # Misread of M1
        "M1": "M1",
        # Misread of M2
        "M2": "M2",
        # MMND -> likely RP or R5 (common in newer subdivisions)
        "MMND": "RP",
    }
    return zone_map.get(zone, zone)


def parse_owner_line(line: str) -> dict:
    """
    Parse a single owner info line that contains: NAME ADDRESS CITY STATE ZIP AC CL ZN DEED
    Example: "ABBOTT DANNELLE LEIGH GARCIA ALPRED00 108 CLEARWATER CT STEPHENS CITY VA 22655-2121 AC .00 CL 1 ZN RP 2020 0007208 00"
    """
    result = {
        "owner_name": None,
        "owner_address": None,
        "owner_city_state_zip": None,
        "acreage": None,
        "property_class": None,
        "zone": None,
        "deed_reference": None,
    }
    
    # First, find the AC CL ZN pattern to split the line (using comprehensive OCR variant patterns)
    ac_pat = r'(?:AC|AZ|AG|AY|AD)'
    cl_pat = r'(?:CL\.?|C1\.?|CI\.?|C\.|CS|CC|CCL|CT|CR|CM|CE)'
    zn_pat = r'(?:ZN|2N|2R|1R|1B|TR|IR|18|2M|LR|IN|TN|IM|IS|1S|IB|ER|I8|2B|2W|EN|JR|LB|FR|78|7R|LS|EB|1W|TA|TB)'
    ac_match = re.search(rf'\s+{ac_pat}\s+([\d\.]+)\s+{cl_pat}\s+(\d+)\s+{zn_pat}\s+(\w+)\s*(.*?)$', line, re.IGNORECASE)
    if ac_match:
        try:
            result["acreage"] = float(ac_match.group(1))
        except ValueError:
            pass
        try:
            result["property_class"] = int(ac_match.group(2))
        except ValueError:
            pass
        result["zone"] = normalize_zone(ac_match.group(3).upper())
        deed_ref = ac_match.group(4).strip()
        if deed_ref and not deed_ref.startswith(('Land', 'LAND')):
            result["deed_reference"] = deed_ref
        
        # Everything before AC is name + address + city
        before_ac = line[:ac_match.start()].strip()
    else:
        before_ac = line.strip()
    
    # Now parse: NAME ADDRESS [CITY STATE ZIP]
    # City/state/zip may be on this line OR on a separate line
    # Strategy: Find zip code, then state, then work backwards to find city and address
    zip_match = re.search(rf'({STATE_ABBREVS})\s+(\d{{5}}(?:-\d{{4}})?)', before_ac)
    if zip_match:
        state = zip_match.group(1)
        zip_code = zip_match.group(2)
        before_state = before_ac[:zip_match.start()].strip()
        
        # Find city - looking backwards, city is word(s) before state that aren't street suffixes
        # Split by spaces and work backwards
        words = before_state.split()
        
        # Find where address ends (last street suffix)
        addr_end_idx = -1
        for i in range(len(words) - 1, -1, -1):
            if words[i] in STREET_SUFFIX_LIST:
                addr_end_idx = i
                break
        
        if addr_end_idx >= 0:
            # City is everything after the street suffix
            city_words = words[addr_end_idx + 1:]
            if city_words:
                city = ' '.join(city_words)
                result["owner_city_state_zip"] = f"{city} {state} {zip_code}"
            
            # Address is from the number to the suffix (inclusive)
            # Find the street number (first number going backwards from suffix)
            addr_start_idx = -1
            for i in range(addr_end_idx, -1, -1):
                if re.match(r'^\d+$', words[i]):
                    addr_start_idx = i
                    break
            
            if addr_start_idx >= 0:
                addr = ' '.join(words[addr_start_idx:addr_end_idx + 1])
                result["owner_address"] = addr
                
                # Owner name is everything before the address
                owner_name = ' '.join(words[:addr_start_idx])
                if owner_name and not any(kw in owner_name for kw in ['LOT', 'ACRE', 'UNIT', 'BLDG']):
                    result["owner_name"] = owner_name
            else:
                # No clear address number, everything before suffix might be owner + description
                pass
        else:
            # No street suffix found, try PO Box
            po_match = re.search(r'(PO\s+BOX\s+\d+)', before_state, re.IGNORECASE)
            if po_match:
                result["owner_address"] = po_match.group(1).upper()
                # City is after PO Box
                after_po = before_state[po_match.end():].strip()
                if after_po:
                    result["owner_city_state_zip"] = f"{after_po} {state} {zip_code}"
                owner_name = before_state[:po_match.start()].strip()
                if owner_name:
                    result["owner_name"] = owner_name
            else:
                # Try to identify city as last 1-2 words
                if len(words) >= 1:
                    # Assume last word or two is city
                    if len(words) >= 2 and words[-1] not in STREET_SUFFIX_LIST:
                        city = ' '.join(words[-2:]) if len(words) >= 2 else words[-1]
                        result["owner_city_state_zip"] = f"{city} {state} {zip_code}"
                        remaining = ' '.join(words[:-2]) if len(words) >= 2 else ''
                        if remaining and not any(kw in remaining for kw in ['LOT', 'ACRE', 'UNIT', 'BLDG']):
                            result["owner_name"] = remaining
    else:
        # No zip code found - city might be on a separate line
        # Just try to parse owner name and address
        words = before_ac.split()
        
        # Find where address ends (last street suffix)
        addr_end_idx = -1
        for i in range(len(words) - 1, -1, -1):
            if words[i] in STREET_SUFFIX_LIST:
                addr_end_idx = i
                break
        
        if addr_end_idx >= 0:
            # Find the street number (first number going backwards from suffix)
            addr_start_idx = -1
            for i in range(addr_end_idx, -1, -1):
                if re.match(r'^\d+$', words[i]):
                    addr_start_idx = i
                    break
            
            if addr_start_idx >= 0:
                addr = ' '.join(words[addr_start_idx:addr_end_idx + 1])
                result["owner_address"] = addr
                
                # Owner name is everything before the address
                owner_name = ' '.join(words[:addr_start_idx])
                if owner_name and not any(kw in owner_name for kw in ['LOT', 'ACRE', 'UNIT', 'BLDG']):
                    result["owner_name"] = owner_name
    
    return result


def extract_owner_name(text: str, before_address: bool = True) -> Optional[str]:
    """
    Extract owner name from text.
    Owner names are typically all caps, may contain &, ', -, and spaces.
    """
    if before_address:
        # Look for name before an address pattern
        pattern = rf'^([A-Z][A-Z\s&\',\.\-]+?)\s+(?:\d+\s+[A-Z]|PO\s+BOX)'
        match = re.match(pattern, text)
        if match:
            name = match.group(1).strip()
            # Filter out non-names
            if not any(kw in name for kw in ['ACRE', 'LOT', 'UNIT', 'BLDG', 'CONDO', 'VALUE', 'LAND']):
                return name
    
    # Try to find name pattern anywhere
    # Names often end with common suffixes: LLC, INC, TRUSTEE, JR, SR, II, III
    name_pattern = r'([A-Z][A-Z\s&\',\.\-]+?(?:LLC|INC|TRUSTEE|JR|SR|II|III)?)\s+(?:\d+\s+[A-Z]|PO\s+BOX|AC\s+[\d\.])'
    match = re.search(name_pattern, text)
    if match:
        name = match.group(1).strip()
        if not any(kw in name for kw in ['ACRE', 'LOT', 'UNIT', 'BLDG', 'CONDO', 'VALUE', 'LAND']):
            return name
    
    return None


def parse_format1_record(lines: list[str], record_num: int, page_num: int, year: int) -> Optional[dict]:
    """
    Parse Format 1: Standard 3-line format
    Line 1: PARCEL DESCRIPTION VALUES ACCT-# FH SH DISTRICT # N
    Line 2: OWNER ADDRESS AC X.XX CL N ZN XX DEED
    Line 3: CITY STATE ZIP
    """
    if len(lines) < 1:
        return None
    
    full_text = ' '.join(lines)
    
    # Find ACCT- to anchor parsing
    acct_match = re.search(r'ACCT-\s*(\d+)', full_text)
    if not acct_match:
        return None
    
    account_number = acct_match.group(1)
    
    # Find values before ACCT-
    values_pattern = r'([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,\.]+)\s+ACCT-'
    values_match = re.search(values_pattern, full_text)
    
    if not values_match:
        # Try 2-value pattern (land only)
        values_pattern2 = r'(\d[\d,]*)\s+(\d[\d,]*)\s+([\d,\.]+)\s+ACCT-'
        values_match = re.search(values_pattern2, full_text)
        if values_match:
            land_value = int(values_match.group(1).replace(',', ''))
            improvement_value = 0
            total_value = int(values_match.group(2).replace(',', ''))
            tax_amount = float(values_match.group(3).replace(',', ''))
        else:
            return None
    else:
        land_value = int(values_match.group(1).replace(',', ''))
        improvement_value = int(values_match.group(2).replace(',', ''))
        total_value = int(values_match.group(3).replace(',', ''))
        tax_amount = float(values_match.group(4).replace(',', ''))
    
    # Extract parcel and description from before values
    before_values = full_text[:values_match.start()].strip()
    
    # Parcel pattern: starts with digits, has dashes
    parcel_match = re.match(r'^([\dA-Z][\dA-Z\s-]*?-[\s\dA-Z-]*?\d+)\s+(.*)$', before_values)
    if parcel_match:
        parcel_raw = parcel_match.group(1).strip()
        description = parcel_match.group(2).strip()
    else:
        # Simpler pattern
        simple_match = re.match(r'^([\dA-Z][\dA-Z\s-]+)\s+(.*)$', before_values)
        if simple_match:
            parcel_raw = simple_match.group(1).strip()
            description = simple_match.group(2).strip()
        else:
            return None
    
    parcel_code = normalize_parcel_code(parcel_raw)
    if not parcel_code or not re.match(r'^\d', parcel_code):
        return None
    
    # Clean description
    description = re.sub(r'\s+\d[\d,]*$', '', description)
    description = re.sub(r'^\d+\.\d+\s+ACRES?\s+', '', description)
    
    # Extract after ACCT- for FH/SH/district
    after_acct = full_text[acct_match.end():]
    
    # Parse FH/SH taxes (OCR variants: FH, PH, FA, FB for first half; SH, SS, SE, S8 for second half)
    fh_match = re.search(r'(?:FH|PH|FA|FB)\s+([\d,\.]+)', after_acct)
    sh_match = re.search(r'(?:SH|SS|SE|S8)\s+([\d,\.]+)', after_acct)
    first_half = float(fh_match.group(1).replace(',', '')) if fh_match else None
    second_half = float(sh_match.group(1).replace(',', '')) if sh_match else None
    
    # Find district
    district = find_district(after_acct) or find_district(full_text)
    
    # Parse owner info from remaining lines
    owner_name = None
    owner_address = None
    owner_city_state_zip = None
    owner_details = {"acreage": None, "property_class": None, "zone": None, "deed_reference": None}
    
    for line in lines[1:] if len(lines) > 1 else []:
        line = line.strip()
        if not line:
            continue
        
        # Check if this has owner details (AC CL ZN) - use comprehensive parser
        # Also check for AZ variant (common OCR misread of AC)
        if re.search(r'\b(?:AC|AZ)\s+[\d\.]', line, re.IGNORECASE):
            parsed = parse_owner_line(line)
            if parsed["owner_name"]:
                owner_name = parsed["owner_name"]
            if parsed["owner_address"]:
                owner_address = parsed["owner_address"]
            if parsed["owner_city_state_zip"]:
                owner_city_state_zip = parsed["owner_city_state_zip"]
            if parsed["acreage"] is not None:
                owner_details["acreage"] = parsed["acreage"]
            if parsed["property_class"] is not None:
                owner_details["property_class"] = parsed["property_class"]
            if parsed["zone"]:
                owner_details["zone"] = parsed["zone"]
            if parsed["deed_reference"]:
                owner_details["deed_reference"] = parsed["deed_reference"]
            continue
        
        # Check if this is just a city/state/zip line
        csz = extract_city_state_zip(line)
        if csz and not owner_city_state_zip:
            owner_city_state_zip = csz
            continue
        
        # Check if this has address info
        addr = extract_address(line)
        if addr and not owner_address:
            owner_address = addr
    
    return {
        "year": year,
        "page_number": page_num,
        "record_number": record_num,
        "parcel_code": parcel_code,
        "parcel_code_raw": parcel_raw,
        "description": description,
        "owner_name": owner_name,
        "owner_address": owner_address,
        "owner_city_state_zip": owner_city_state_zip,
        "land_value": land_value,
        "improvement_value": improvement_value,
        "total_value": total_value,
        "tax_amount": tax_amount,
        "first_half_tax": first_half,
        "second_half_tax": second_half,
        "account_number": account_number,
        "district": district,
        "acreage": owner_details["acreage"],
        "property_class": owner_details["property_class"],
        "zone": owner_details["zone"],
        "deed_reference": owner_details["deed_reference"],
    }


def parse_format2_record(text: str, record_num: int, page_num: int, year: int) -> Optional[dict]:
    """
    Parse Format 2/3: Single line with owner inline or multi-line variant
    PARCEL OWNER ADDRESS CITY STATE ZIP AC X.XX CL N ZN XX [Land Value] VALUES ACCT-# FH SH DISTRICT # N
    """
    # Find ACCT- to anchor parsing
    acct_match = re.search(r'ACCT-\s*(\d+)', text)
    if not acct_match:
        return None
    
    account_number = acct_match.group(1)
    
    # Find values before ACCT-
    # May have "Land Value" prefix due to OCR
    values_pattern = r'(?:Land\s+Value\s+)?([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,\.]+)\s+ACCT-'
    values_match = re.search(values_pattern, text, re.IGNORECASE)
    
    if not values_match:
        # Try 2-value pattern
        values_pattern2 = r'(?:Land\s+Value\s+)?(\d[\d,]*)\s+(\d[\d,]*)\s+([\d,\.]+)\s+ACCT-'
        values_match = re.search(values_pattern2, text, re.IGNORECASE)
        if values_match:
            land_value = int(values_match.group(1).replace(',', ''))
            improvement_value = 0
            total_value = int(values_match.group(2).replace(',', ''))
            tax_amount = float(values_match.group(3).replace(',', ''))
        else:
            return None
    else:
        land_value = int(values_match.group(1).replace(',', ''))
        improvement_value = int(values_match.group(2).replace(',', ''))
        total_value = int(values_match.group(3).replace(',', ''))
        tax_amount = float(values_match.group(4).replace(',', ''))
    
    # Everything before values contains parcel, owner, address, details
    before_values = text[:values_match.start()].strip()
    
    # Extract after ACCT- for FH/SH/district
    after_acct = text[acct_match.end():]
    fh_match = re.search(r'(?:FH|PH|FA|FB)\s+([\d,\.]+)', after_acct)
    sh_match = re.search(r'(?:SH|SS|SE|S8)\s+([\d,\.]+)', after_acct)
    first_half = float(fh_match.group(1).replace(',', '')) if fh_match else None
    second_half = float(sh_match.group(1).replace(',', '')) if sh_match else None
    district = find_district(after_acct) or find_district(text)
    
    # Extract owner details (AC CL ZN) from before_values
    owner_details = extract_owner_details(before_values)
    
    # Find where owner details start
    ac_match = re.search(r'\s+AC\s+[\d\.]+', before_values, re.IGNORECASE)
    if ac_match:
        before_ac = before_values[:ac_match.start()].strip()
    else:
        before_ac = before_values
    
    # Extract parcel code (starts at beginning, ends with digit before owner name starts)
    # Parcel codes: "64B- - A- - 38", "18A-07-10- - 556", etc.
    # Use smart splitter that detects owner name patterns
    parcel_raw, after_parcel = split_parcel_from_owner(before_ac)
    
    if not parcel_raw:
        # Fallback to regex patterns
        parcel_match = re.match(r'^([\dA-Z][\dA-Z\s-]*?-[\s\dA-Z-]*?\d+)\s+(.*)$', before_ac)
        if parcel_match:
            parcel_raw = parcel_match.group(1).strip()
            after_parcel = parcel_match.group(2).strip()
        else:
            # Simpler pattern
            simple_match = re.match(r'^([\dA-Z][\dA-Z\s-]+\d)\s+(.*)$', before_ac)
            if simple_match:
                parcel_raw = simple_match.group(1).strip()
                after_parcel = simple_match.group(2).strip()
            else:
                return None
    
    parcel_code = normalize_parcel_code(parcel_raw)
    if not parcel_code or not re.match(r'^\d', parcel_code):
        return None
    
    # Now parse after_parcel for owner name, address, city/state/zip, description
    owner_name = None
    owner_address = None
    owner_city_state_zip = None
    description = ""
    
    # Try to find city/state/zip
    csz = extract_city_state_zip(after_parcel)
    if csz:
        owner_city_state_zip = csz
        # Remove city/state/zip from after_parcel to help parsing
        csz_pattern = rf'{re.escape(csz.split()[0])}\s+{STATE_ABBREVS}\s+\d{{5}}(?:-\d{{4}})?'
        after_parcel = re.sub(csz_pattern, '', after_parcel).strip()
    
    # Try to find address
    addr = extract_address(after_parcel)
    if addr:
        owner_address = addr
        addr_pos = after_parcel.find(addr)
        if addr_pos > 0:
            # Owner name is before address
            potential_name = after_parcel[:addr_pos].strip()
            # Check if it's actually a description or name
            if re.match(r'^[A-Z][A-Z\s&\',\.\-]+$', potential_name):
                if not any(kw in potential_name for kw in ['LOT', 'ACRE', 'UNIT', 'BLDG', 'CONDO']):
                    owner_name = potential_name
                else:
                    description = potential_name
            else:
                description = potential_name
    else:
        # No clear address - try to identify owner name
        owner_name = extract_owner_name(after_parcel)
        if not owner_name:
            # Treat it all as description
            description = after_parcel
    
    # Clean up description
    if description:
        description = re.sub(r'\s+\d[\d,]*$', '', description)
        description = re.sub(r'^\d+\.\d+\s+ACRES?\s+', '', description)
    
    return {
        "year": year,
        "page_number": page_num,
        "record_number": record_num,
        "parcel_code": parcel_code,
        "parcel_code_raw": parcel_raw,
        "description": description,
        "owner_name": owner_name,
        "owner_address": owner_address,
        "owner_city_state_zip": owner_city_state_zip,
        "land_value": land_value,
        "improvement_value": improvement_value,
        "total_value": total_value,
        "tax_amount": tax_amount,
        "first_half_tax": first_half,
        "second_half_tax": second_half,
        "account_number": account_number,
        "district": district,
        "acreage": owner_details["acreage"],
        "property_class": owner_details["property_class"],
        "zone": owner_details["zone"],
        "deed_reference": owner_details["deed_reference"],
    }


def parse_single_record(record_text: str, record_num: int, page_num: int, year: int, use_gis: bool = True) -> Optional[dict]:
    """
    Parse a single property record, detecting format automatically.
    
    If use_gis=True and owner extraction fails, falls back to GIS lookup by account number.
    """
    lines = [l.strip() for l in record_text.strip().split('\n') if l.strip()]
    
    if not lines:
        return None
    
    # Check if this looks like Format 1 (multi-line with owner on separate line)
    # Format 1: First line has values and ACCT-, subsequent lines have AC CL ZN
    first_line = lines[0]
    has_acct_in_first = 'ACCT-' in first_line
    has_ac_in_first = re.search(r'\sAC\s+[\d\.]+', first_line, re.IGNORECASE)
    
    result = None
    if has_acct_in_first and not has_ac_in_first and len(lines) >= 2:
        # Format 1: Standard multi-line
        result = parse_format1_record(lines, record_num, page_num, year)
    
    if not result:
        # Try Format 2/3: Single line or owner inline
        full_text = ' '.join(lines)
        result = parse_format2_record(full_text, record_num, page_num, year)
    
    if not result:
        # Fallback to Format 1 parsing
        result = parse_format1_record(lines, record_num, page_num, year)
    
    if not result:
        return None
    
    # Determine owner source and apply GIS fallback if needed
    owner_source = "ocr" if result.get("owner_name") else None
    
    if use_gis and not result.get("owner_name"):
        # Try GIS lookup by account number
        gis_owner = lookup_owner_from_gis(result.get("account_number", ""))
        if gis_owner:
            if gis_owner.get("owner_name"):
                result["owner_name"] = gis_owner["owner_name"]
                owner_source = "gis"
            if not result.get("owner_address") and gis_owner.get("owner_address"):
                result["owner_address"] = gis_owner["owner_address"]
            if not result.get("owner_city_state_zip") and gis_owner.get("owner_city_state_zip"):
                result["owner_city_state_zip"] = gis_owner["owner_city_state_zip"]
    
    result["owner_source"] = owner_source
    return result


def parse_anthropic_page(text: str, page_num: int, year: int, use_gis: bool = True) -> list[dict]:
    """
    Parse a page of Anthropic OCR text into property records.
    
    Anthropic OCR preserves the two-column tabular layout of the original document,
    which requires a different parsing strategy than the compact glm-ocr format.
    
    Strategy: Flatten the text into a single string, then anchor on ACCT- markers
    and extract surrounding context for each record.
    """
    records = []
    
    # Flatten multi-line text into single line (collapse whitespace but preserve separators)
    # This handles the two-column layout by merging everything
    flat = re.sub(r'\n+', ' ', text)
    flat = re.sub(r'\s{2,}', ' ', flat)
    
    # Remove header/footer content
    # Strip everything before first parcel code pattern
    first_parcel = re.search(r'\b(\d{1,3}\s*[A-Z]?\s*-\s*[A-Z]?\s*-)', flat)
    if first_parcel:
        flat = flat[first_parcel.start():]
    
    # Remove page totals at end
    totals_match = re.search(r'CLASS\s+1\s+CLASS\s+2', flat)
    if totals_match:
        flat = flat[:totals_match.start()]
    
    # Find all ACCT- markers as record anchors
    acct_matches = list(re.finditer(r'ACCT-\s*(\d+)', flat))
    
    if not acct_matches:
        return records
    
    # Find record number markers (# NNNNN) that follow ACCT- entries
    record_num_markers = {m.start(): int(m.group(1)) for m in re.finditer(r'#\s*(\d{3,6})\b', flat)}
    
    for i, acct_match in enumerate(acct_matches):
        account_number = acct_match.group(1)
        
        # Define the region for this record:
        # From previous ACCT end (or start of text) to current ACCT
        if i == 0:
            region_start = 0
        else:
            # Start after previous record's ACCT and trailing info (PH, SH, district, #)
            region_start = acct_matches[i-1].end()
            # Skip past PH/SH/district/# info
            after_prev = flat[region_start:acct_match.start()]
            # Find where the next parcel code starts
            next_parcel = re.search(r'\b(\d{1,3}\s*[A-Z]?\s*-\s*(?:[A-Z]?\s*-|\s*\d))', after_prev)
            if next_parcel:
                region_start = region_start + next_parcel.start()
        
        # Region extends past ACCT to capture PH/SH/district/#
        if i < len(acct_matches) - 1:
            region_end = acct_matches[i+1].start()
        else:
            region_end = len(flat)
        
        region = flat[region_start:region_end].strip()
        
        if not region or len(region) < 20:
            continue
        
        # Extract values before ACCT-
        before_acct = flat[region_start:acct_match.start()].strip()
        after_acct = flat[acct_match.end():region_end].strip()
        
        # Find record number from after ACCT
        record_num = 0
        rec_num_match = re.search(r'#\s*(\d{3,6})\b', after_acct)
        if rec_num_match:
            record_num = int(rec_num_match.group(1))
        
        # Extract values: look for pattern LAND IMP TOTAL TAX before ACCT
        values_match = re.search(r'([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,\.]+)\s*$', before_acct)
        if not values_match:
            # Try 2-value pattern (land only, no improvements)
            values_match = re.search(r'(\d[\d,]*)\s+(\d[\d,]*)\s+([\d,\.]+)\s*$', before_acct)
            if values_match:
                land_value = int(values_match.group(1).replace(',', ''))
                improvement_value = 0
                total_value = int(values_match.group(2).replace(',', ''))
                try:
                    tax_amount = float(values_match.group(3).replace(',', ''))
                except ValueError:
                    continue
            else:
                continue
        else:
            land_value = int(values_match.group(1).replace(',', ''))
            improvement_value = int(values_match.group(2).replace(',', ''))
            total_value = int(values_match.group(3).replace(',', ''))
            try:
                tax_amount = float(values_match.group(4).replace(',', ''))
            except ValueError:
                continue
        
        # Everything before values = parcel + description + owner info
        before_values = before_acct[:values_match.start()].strip()
        
        # Extract parcel code (starts with digits, has dashes)
        parcel_match = re.match(r'^([\dA-Z][\dA-Z\s-]*?-[\s\dA-Z-]*?\d+(?:-[A-Z])?)', before_values)
        if not parcel_match:
            # Simpler pattern
            parcel_match = re.match(r'^([\dA-Z][\dA-Z\s-]+\d)', before_values)
        
        if not parcel_match:
            continue
        
        parcel_raw = parcel_match.group(1).strip()
        parcel_code = normalize_parcel_code(parcel_raw)
        
        if not parcel_code or not re.match(r'^\d', parcel_code):
            continue
        
        # After parcel: description + owner info
        after_parcel = before_values[parcel_match.end():].strip()
        
        # Extract AC CL ZN - search BOTH after_parcel AND after_acct
        # In the Anthropic two-column format, AC/CL/ZN often appears in after_acct
        # (on the owner's city/state/zip line which gets placed after ACCT in the layout)
        owner_details = extract_owner_details(after_parcel)
        if owner_details["acreage"] is None:
            # Try after_acct - this is where AC/CL/ZN usually is in Anthropic OCR
            owner_details_acct = extract_owner_details(after_acct)
            if owner_details_acct["acreage"] is not None:
                owner_details = owner_details_acct
        
        # Extract owner info from BOTH regions
        owner_name = None
        owner_address = None
        owner_city_state_zip = None
        description = ""
        
        # First try after_parcel (description region before ACCT)
        csz = extract_city_state_zip(after_parcel)
        if csz:
            owner_city_state_zip = csz
        
        addr = extract_address(after_parcel)
        if addr:
            owner_address = addr
            addr_pos = after_parcel.find(addr)
            if addr_pos > 0:
                potential_name = after_parcel[:addr_pos].strip()
                desc_match = re.search(r'(?:\d+\.\d+\s+ACRES?|[A-Z]+ (?:L\d+|LOT|UNIT|SEC|REPL))', potential_name)
                if desc_match:
                    description = potential_name[:desc_match.end()].strip()
                    potential_name = potential_name[desc_match.end():].strip()
                
                if potential_name and re.match(r'^[A-Z][A-Z\s&\',\.\-]+$', potential_name):
                    if not any(kw in potential_name for kw in ['LOT', 'ACRE', 'UNIT', 'BLDG', 'CONDO', 'RETIRED']):
                        owner_name = potential_name
        else:
            owner_name = extract_owner_name(after_parcel)
        
        # Also try after_acct for owner info (common in Anthropic two-column format)
        # The owner name, address, and city/state/zip often appear after ACCT
        if not owner_name or not owner_address:
            acct_csz = extract_city_state_zip(after_acct)
            if acct_csz and not owner_city_state_zip:
                owner_city_state_zip = acct_csz
            
            acct_addr = extract_address(after_acct)
            if acct_addr and not owner_address:
                owner_address = acct_addr
            
            if not owner_name:
                acct_owner = extract_owner_name(after_acct)
                if acct_owner:
                    owner_name = acct_owner
        
        # Parse FH/SH taxes and district from after ACCT
        fh_match = re.search(r'(?:FH|PH|FB|FA)\s+([\d,\.]+)', after_acct)
        sh_match = re.search(r'(?:SH|SS|SE|S8)\s+([\d,\.]+)', after_acct)
        first_half = float(fh_match.group(1).replace(',', '')) if fh_match else None
        second_half = float(sh_match.group(1).replace(',', '')) if sh_match else None
        district = find_district(after_acct) or find_district(region)
        
        # GIS fallback for owner
        owner_source = "ocr" if owner_name else None
        if use_gis and not owner_name:
            gis_owner = lookup_owner_from_gis(account_number)
            if gis_owner:
                if gis_owner.get("owner_name"):
                    owner_name = gis_owner["owner_name"]
                    owner_source = "gis"
                if not owner_address and gis_owner.get("owner_address"):
                    owner_address = gis_owner["owner_address"]
                if not owner_city_state_zip and gis_owner.get("owner_city_state_zip"):
                    owner_city_state_zip = gis_owner["owner_city_state_zip"]
        
        record = {
            "year": year,
            "page_number": page_num,
            "record_number": record_num,
            "parcel_code": parcel_code,
            "parcel_code_raw": parcel_raw,
            "description": description,
            "owner_name": owner_name,
            "owner_address": owner_address,
            "owner_city_state_zip": owner_city_state_zip,
            "land_value": land_value,
            "improvement_value": improvement_value,
            "total_value": total_value,
            "tax_amount": tax_amount,
            "first_half_tax": first_half,
            "second_half_tax": second_half,
            "account_number": account_number,
            "district": district,
            "acreage": owner_details["acreage"],
            "property_class": owner_details["property_class"],
            "zone": owner_details["zone"],
            "deed_reference": owner_details["deed_reference"],
            "owner_source": owner_source,
        }
        
        records.append(record)
    
    return records


def parse_ocr_page(text: str, page_num: int, year: int, use_gis: bool = True) -> list[dict]:
    """
    Parse a single page of OCR text into property records.
    Uses the original # marker approach (for glm-ocr output).
    """
    records = []
    
    # Skip Page Totals section
    if 'Page Totals' in text:
        text = text[:text.index('Page Totals')]
    
    # Remove header lines
    header_end = text.find('Half Taxes')
    if header_end > 0:
        text = text[header_end + len('Half Taxes'):].strip()
    
    # Find all record number markers
    record_markers = list(re.finditer(r'#\s*(\d+)', text))
    
    if not record_markers:
        return records
    
    for i, marker in enumerate(record_markers):
        record_num = int(marker.group(1))
        
        # Determine record boundaries
        if i == 0:
            record_start = 0
        else:
            # Start after previous record's owner info
            prev_end = record_markers[i-1].end()
            remaining = text[prev_end:]
            lines_after = remaining.split('\n')
            owner_lines_count = 0
            for line in lines_after:
                line_stripped = line.strip()
                if not line_stripped:
                    owner_lines_count += 1
                    continue
                # Stop if we hit a parcel code
                if re.match(r'^\d+[A-Z]?\s*-', line_stripped):
                    break
                owner_lines_count += 1
                if owner_lines_count >= 3:
                    break
            chars_used = sum(len(l) + 1 for l in lines_after[:owner_lines_count])
            record_start = prev_end + chars_used
        
        record_first_line_end = marker.end()
        
        # Get owner info lines after marker
        remaining_after = text[record_first_line_end:]
        lines_after = remaining_after.split('\n')
        owner_lines = []
        blank_count = 0
        for line in lines_after:
            line_stripped = line.strip()
            if not line_stripped:
                blank_count += 1
                # Allow up to 2 blank lines (page 5 format has blank line before owner)
                if blank_count > 2:
                    break
                continue
            if re.match(r'^\d+[A-Z]?\s*-', line_stripped):
                break
            owner_lines.append(line_stripped)
            blank_count = 0  # Reset after finding content
            if len(owner_lines) >= 3:  # Allow up to 3 owner lines
                break
        
        record_text = text[record_start:record_first_line_end].strip()
        if owner_lines:
            record_text = record_text + '\n' + '\n'.join(owner_lines)
        
        if record_text:
            record = parse_single_record(record_text, record_num, page_num, year, use_gis=use_gis)
            if record and record.get('parcel_code'):
                records.append(record)
    
    return records


def parse_ocr_file(ocr_json_path: Path, use_gis: bool = True) -> dict[str, Any]:
    """Parse an OCR JSON file into structured records."""
    with open(ocr_json_path) as f:
        ocr_data = json.load(f)
    
    source_file = ocr_data.get("source_file", ocr_json_path.stem)
    year = extract_year_from_filename(source_file)
    
    if not year:
        print(f"  Warning: Could not extract year from {source_file}")
        year = 2025
    
    # Detect OCR source to choose parser
    model = ocr_data.get("model", "")
    is_anthropic = ocr_json_path.name.startswith("anthropic_") or "claude" in model.lower()
    
    all_records = []
    pages_processed = 0
    errors = []
    
    for page_data in ocr_data.get("pages", []):
        page_num = page_data.get("page", 0)
        text = page_data.get("text", "")
        
        if text.startswith("ERROR:"):
            errors.append({"page": page_num, "error": text})
            continue
        
        try:
            if is_anthropic:
                records = parse_anthropic_page(text, page_num, year, use_gis=use_gis)
            else:
                records = parse_ocr_page(text, page_num, year, use_gis=use_gis)
            all_records.extend(records)
            pages_processed += 1
        except Exception as e:
            errors.append({"page": page_num, "error": str(e)})
            import traceback
            traceback.print_exc()
    
    return {
        "source_file": source_file,
        "ocr_file": str(ocr_json_path),
        "year": year,
        "pages_processed": pages_processed,
        "records_extracted": len(all_records),
        "errors": errors,
        "records": all_records,
    }


def main():
    parser = argparse.ArgumentParser(description="Parse OCR output into structured records")
    parser.add_argument("--input", "-i", type=Path, required=True, help="Input OCR JSON file or directory")
    parser.add_argument("--output", "-o", type=Path, default=PROCESSED_DIR / "real_estate_ocr.json", help="Output JSON file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print detailed progress")
    parser.add_argument("--no-gis", action="store_true", help="Disable GIS lookup fallback for owner data")
    parser.add_argument("--source", choices=["anthropic", "glm", "all"], default="anthropic",
                       help="Which OCR source to parse: anthropic (default), glm, or all")
    
    args = parser.parse_args()
    use_gis = not args.no_gis
    
    if not args.input.exists():
        print(f"Error: Input does not exist: {args.input}")
        sys.exit(1)
    
    if args.input.is_file():
        ocr_files = [args.input]
    else:
        if args.source == "anthropic":
            ocr_files = sorted(args.input.glob("anthropic_*_pages_*.json"))
        elif args.source == "glm":
            # GLM files: match *_pages_*.json but NOT anthropic_ prefix
            all_pages = sorted(args.input.glob("*_pages_*.json"))
            ocr_files = [f for f in all_pages if not f.name.startswith("anthropic_")]
        else:  # all
            ocr_files = sorted(args.input.glob("*_ocr.json")) + sorted(args.input.glob("*_pages_*.json"))
        
        # Exclude tracking/metadata files
        ocr_files = [f for f in ocr_files if "batches" not in f.name]
    
    if not ocr_files:
        print(f"No OCR JSON files found in {args.input}")
        sys.exit(0)
    
    print("=" * 60)
    print("Parsing OCR Output")
    print("=" * 60)
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    print(f"Files to process: {len(ocr_files)}")
    print(f"GIS lookup: {'enabled' if use_gis else 'disabled'}")
    print("=" * 60)
    
    # Load GIS lookup if enabled
    if use_gis:
        load_gis_lookup()
    
    all_results = []
    total_records = 0
    total_errors = 0
    
    for ocr_file in ocr_files:
        print(f"\nProcessing: {ocr_file.name}")
        result = parse_ocr_file(ocr_file, use_gis=use_gis)
        all_results.append(result)
        total_records += result["records_extracted"]
        total_errors += len(result["errors"])
        print(f"  Year: {result['year']}")
        print(f"  Pages: {result['pages_processed']}")
        print(f"  Records: {result['records_extracted']}")
        if result["errors"]:
            print(f"  Errors: {len(result['errors'])}")
    
    combined_records = []
    for result in all_results:
        combined_records.extend(result["records"])
    
    output_data = {
        "metadata": {
            "source": f"OCR extracted real estate tax records (source: {args.source})",
            "processed_date": datetime.now().isoformat(),
            "files_processed": len(ocr_files),
            "total_records": len(combined_records),
            "total_errors": total_errors,
            "property_classes": PROPERTY_CLASSES,
            "districts": list(set(DISTRICT_MAPPING.values())),
        },
        "file_summaries": [{k: v for k, v in r.items() if k != "records"} for r in all_results],
        "records": combined_records,
    }
    
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output_data, f, indent=2)
    
    print("\n" + "=" * 60)
    print("Parsing complete!")
    print("=" * 60)
    print(f"Total records: {len(combined_records)}")
    print(f"Total errors: {total_errors}")
    print(f"Output saved to: {args.output}")
    
    # Print extraction stats
    if combined_records:
        with_owner = sum(1 for r in combined_records if r.get('owner_name'))
        with_address = sum(1 for r in combined_records if r.get('owner_address'))
        with_city = sum(1 for r in combined_records if r.get('owner_city_state_zip'))
        with_zone = sum(1 for r in combined_records if r.get('zone'))
        
        # Owner source breakdown
        from_ocr = sum(1 for r in combined_records if r.get('owner_source') == 'ocr')
        from_gis = sum(1 for r in combined_records if r.get('owner_source') == 'gis')
        no_owner = sum(1 for r in combined_records if not r.get('owner_source'))
        
        with_acreage = sum(1 for r in combined_records if r.get('acreage') is not None)
        with_class = sum(1 for r in combined_records if r.get('property_class') is not None)
        with_district = sum(1 for r in combined_records if r.get('district'))
        with_fh = sum(1 for r in combined_records if r.get('first_half_tax') is not None)
        with_deed = sum(1 for r in combined_records if r.get('deed_reference'))
        
        print(f"\nExtraction rates:")
        print(f"  owner_name:      {with_owner:>7}/{len(combined_records)} ({100*with_owner/len(combined_records):.1f}%)")
        print(f"  owner_address:   {with_address:>7}/{len(combined_records)} ({100*with_address/len(combined_records):.1f}%)")
        print(f"  city_state_zip:  {with_city:>7}/{len(combined_records)} ({100*with_city/len(combined_records):.1f}%)")
        print(f"  zone:            {with_zone:>7}/{len(combined_records)} ({100*with_zone/len(combined_records):.1f}%)")
        print(f"  acreage:         {with_acreage:>7}/{len(combined_records)} ({100*with_acreage/len(combined_records):.1f}%)")
        print(f"  property_class:  {with_class:>7}/{len(combined_records)} ({100*with_class/len(combined_records):.1f}%)")
        print(f"  district:        {with_district:>7}/{len(combined_records)} ({100*with_district/len(combined_records):.1f}%)")
        print(f"  first_half_tax:  {with_fh:>7}/{len(combined_records)} ({100*with_fh/len(combined_records):.1f}%)")
        print(f"  deed_reference:  {with_deed:>7}/{len(combined_records)} ({100*with_deed/len(combined_records):.1f}%)")
        
        # Zone value distribution
        from collections import Counter
        zone_counts = Counter(r.get('zone') for r in combined_records if r.get('zone'))
        if zone_counts:
            print(f"\nZone distribution (top 15):")
            for zone, count in zone_counts.most_common(15):
                print(f"  {zone:>5}: {count:>6} ({100*count/len(combined_records):.1f}%)")
        
        # District distribution
        district_counts = Counter(r.get('district') for r in combined_records if r.get('district'))
        if district_counts:
            print(f"\nDistrict distribution:")
            for dist, count in district_counts.most_common():
                print(f"  {dist:>15}: {count:>6} ({100*count/len(combined_records):.1f}%)")
        
        print(f"\nOwner source breakdown:")
        print(f"  from OCR:        {from_ocr}/{len(combined_records)} ({100*from_ocr/len(combined_records):.1f}%)")
        print(f"  from GIS:        {from_gis}/{len(combined_records)} ({100*from_gis/len(combined_records):.1f}%)")
        print(f"  not found:       {no_owner}/{len(combined_records)} ({100*no_owner/len(combined_records):.1f}%)")
    
    if args.verbose and combined_records:
        print("\nSample records:")
        for i, rec in enumerate(combined_records[:5]):
            print(f"\n--- Record #{rec['record_number']} (Page {rec['page_number']}) ---")
            print(json.dumps(rec, indent=2))


if __name__ == "__main__":
    main()
