#!/usr/bin/env python3
"""
Parse a single year's Frederick County Real Estate Tax Book.
Designed to be called in parallel by multiple processes.

Usage: python parse_single_tax_year.py <year> <output_file>
"""

import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Districts in Frederick County
DISTRICTS = [
    "BACK CREEK", "BACKCREEK",
    "GAINESBORO", 
    "OPEQUON",
    "RED BUD", "REDBUD",
    "SHAWNEE",
    "STONEWALL",
    "STEPHENS CITY", "STEPHENSCITY",
    "MIDDLETOWN"
]

DISTRICT_NORMALIZE = {
    "BACKCREEK": "Back Creek",
    "BACK CREEK": "Back Creek",
    "GAINESBORO": "Gainesboro",
    "OPEQUON": "Opequon",
    "REDBUD": "Red Bud",
    "RED BUD": "Red Bud",
    "SHAWNEE": "Shawnee",
    "STONEWALL": "Stonewall",
    "STEPHENSCITY": "Stephens City",
    "STEPHENS CITY": "Stephens City",
    "MIDDLETOWN": "Middletown"
}

PROPERTY_CLASSES = {
    1: "Residential",
    2: "Agricultural/Undeveloped",
    3: "Multi-Family",
    4: "Commercial",
    5: "Industrial",
    6: "Land Use (Deferred)",
    7: "Public Service",
    8: "Exempt",
    9: "Mineral"
}

TAX_BOOKS = {
    2021: {"file": "Real Estate 2021 Tax Book.pdf", "rate": 0.61, "commissioner": "Seth T. Thatcher"},
    2022: {"file": "Real Estate 2022 Tax Book.pdf", "rate": 0.61, "commissioner": "Seth T. Thatcher"},
    2023: {"file": "RE 2023 Book.pdf", "rate": 0.51, "commissioner": "Seth T. Thatcher"},
    2024: {"file": "RE_Book_2024.pdf", "rate": 0.51, "commissioner": "Tonya Sibert"},
    2025: {"file": "RE_2025_Book.pdf", "rate": 0.48, "commissioner": "Tonya Sibert"}
}


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF using pdftotext."""
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {result.stderr}")
    return result.stdout


def parse_property_record(lines: list[str], year: int) -> dict | None:
    """Parse a single property record from extracted lines."""
    if not lines:
        return None
    
    record = {
        "year": year,
        "parcel_code": None,
        "owner_name": None,
        "owner_address": None,
        "owner_city_state_zip": None,
        "description": None,
        "land_value": 0,
        "improvement_value": 0,
        "total_value": 0,
        "tax_amount": 0.0,
        "acreage": None,
        "property_class": None,
        "zone": None,
        "account_number": None,
        "district": None,
        "first_half_tax": 0.0,
        "second_half_tax": 0.0,
        "deferred_value": 0
    }
    
    full_text = " ".join(lines)
    
    # Extract parcel code
    parcel_match = re.search(r'^(\d+[A-Z]?\s*-\s*-?\s*\d*[A-Z]?\s*-?\s*-?\s*\d*\s*-?\s*-?\s*\d*(?:-[A-Z0-9]+)?)', lines[0])
    if parcel_match:
        record["parcel_code"] = re.sub(r'\s+', '', parcel_match.group(1))
    
    # Extract account number
    acct_match = re.search(r'ACCT-?\s*(\d+)', full_text)
    if acct_match:
        record["account_number"] = acct_match.group(1)
    
    # Extract district
    text_upper = full_text.upper().replace(" ", "")
    for district in DISTRICTS:
        district_normalized = district.replace(" ", "")
        if district_normalized in text_upper:
            record["district"] = DISTRICT_NORMALIZE.get(district, DISTRICT_NORMALIZE.get(district.replace(" ", "")))
            break
    
    # Extract values - pattern: land, improvement, total, tax
    # Tax should have decimal and be roughly 0.5% of total value (rate is ~$0.50 per $100)
    value_pattern = r'([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+\.\d{2})'
    value_matches = re.findall(value_pattern, full_text)
    
    if value_matches:
        for match in value_matches:
            try:
                land = int(match[0].replace(",", ""))
                imp = int(match[1].replace(",", ""))
                total = int(match[2].replace(",", ""))
                tax = float(match[3].replace(",", ""))
                
                # Sanity checks:
                # 1. Total should roughly equal land + improvement
                # 2. Tax should be roughly 0.4-0.7% of total value
                # 3. Individual property values should be reasonable (< $100M)
                sum_check = abs(land + imp - total) < 100  # Allow small rounding
                tax_rate_check = total > 0 and 0.001 < (tax / total) < 0.02  # 0.1% to 2%
                value_check = total < 100_000_000 and tax < 1_000_000
                
                if sum_check and tax_rate_check and value_check:
                    record["land_value"] = land
                    record["improvement_value"] = imp
                    record["total_value"] = total
                    record["tax_amount"] = tax
                    break
            except (ValueError, IndexError, ZeroDivisionError):
                continue
    
    # Check for land-only records
    if record["total_value"] == 0:
        land_only_pattern = r'(\d{1,3}(?:,\d{3})*)\s+(\d{1,3}(?:,\d{3})*)\s+(\d+\.?\d*)\s+ACCT'
        land_match = re.search(land_only_pattern, full_text)
        if land_match:
            try:
                val = int(land_match.group(1).replace(",", ""))
                total = int(land_match.group(2).replace(",", ""))
                tax = float(land_match.group(3).replace(",", ""))
                if val == total:
                    record["land_value"] = val
                    record["total_value"] = total
                    record["tax_amount"] = tax
            except (ValueError, IndexError):
                pass
    
    # Extract property class
    class_match = re.search(r'CL\s*(\d)', full_text)
    if class_match:
        record["property_class"] = int(class_match.group(1))
    
    # Extract zone
    zone_match = re.search(r'ZN\s*([A-Z0-9]+)', full_text)
    if zone_match:
        record["zone"] = zone_match.group(1)
    
    # Extract acreage
    acre_match = re.search(r'([\d.]+)\s*(?:ACRES?|AC\b)', full_text, re.IGNORECASE)
    if acre_match:
        try:
            record["acreage"] = float(acre_match.group(1))
        except ValueError:
            pass
    
    # Extract first/second half tax
    fh_match = re.search(r'FH\s*([\d,]+\.?\d*)', full_text)
    sh_match = re.search(r'SH\s*([\d,]+\.?\d*)', full_text)
    if fh_match:
        try:
            record["first_half_tax"] = float(fh_match.group(1).replace(",", ""))
        except ValueError:
            pass
    if sh_match:
        try:
            record["second_half_tax"] = float(sh_match.group(1).replace(",", ""))
        except ValueError:
            pass
    
    # Extract deferred value
    deferred_match = re.search(r'([\d,]+)\s*DEFERRED', full_text)
    if deferred_match:
        try:
            record["deferred_value"] = int(deferred_match.group(1).replace(",", ""))
        except ValueError:
            pass
    
    # Extract owner info
    owner_lines = []
    for line in lines[1:5]:
        line = line.strip()
        if line and not re.match(r'^(ACCT|FH|SH|AC\s|CL\s|ZN\s|\d+\.\d+\s*CL|#\s*\d)', line):
            if not re.match(r'^[\d,]+\s+[\d,]+\s+[\d,]+', line):
                owner_lines.append(line)
    
    if owner_lines:
        record["owner_name"] = owner_lines[0] if len(owner_lines) > 0 else None
        record["owner_address"] = owner_lines[1] if len(owner_lines) > 1 else None
        record["owner_city_state_zip"] = owner_lines[2] if len(owner_lines) > 2 else None
    
    # Extract description
    desc_patterns = [
        r'((?:LOT|L)\s*\d+[A-Z]?\s*(?:P\d+)?\s*(?:S\d+[A-Z]?)?)',
        r'(LAKE\s*HOLIDAY\s*EST[.\s]*L\d+)',
        r'(SHAWNEE\s*LAND\s*L\d+)',
    ]
    for pattern in desc_patterns:
        desc_match = re.search(pattern, full_text, re.IGNORECASE)
        if desc_match:
            record["description"] = desc_match.group(1).strip()
            break
    
    # Only return if we have meaningful data
    if record["parcel_code"] and (record["total_value"] > 0 or record["land_value"] > 0):
        return record
    
    return None


def calculate_summary(records: list, year: int, book_info: dict) -> dict:
    """Calculate summary statistics from records."""
    
    summary = {
        "year": year,
        "tax_rate": book_info["rate"],
        "commissioner": book_info["commissioner"],
        "source_file": book_info["file"],
        "total_records": len(records),
        "totals": {
            "land_value": sum(r["land_value"] for r in records),
            "improvement_value": sum(r["improvement_value"] for r in records),
            "total_value": sum(r["total_value"] for r in records),
            "tax_amount": sum(r["tax_amount"] for r in records),
            "deferred_value": sum(r["deferred_value"] for r in records)
        },
        "by_district": {},
        "by_class": {},
        "by_zone": {}
    }
    
    # Aggregate by district
    district_data = defaultdict(lambda: {
        "property_count": 0,
        "land_value": 0,
        "improvement_value": 0,
        "total_value": 0,
        "tax_amount": 0,
        "deferred_value": 0,
        "total_acreage": 0,
        "by_class": defaultdict(lambda: {"count": 0, "total_value": 0, "tax": 0})
    })
    
    for r in records:
        district = r["district"] or "Unknown"
        district_data[district]["property_count"] += 1
        district_data[district]["land_value"] += r["land_value"]
        district_data[district]["improvement_value"] += r["improvement_value"]
        district_data[district]["total_value"] += r["total_value"]
        district_data[district]["tax_amount"] += r["tax_amount"]
        district_data[district]["deferred_value"] += r["deferred_value"]
        if r["acreage"]:
            district_data[district]["total_acreage"] += r["acreage"]
        
        prop_class = r["property_class"] or 0
        district_data[district]["by_class"][prop_class]["count"] += 1
        district_data[district]["by_class"][prop_class]["total_value"] += r["total_value"]
        district_data[district]["by_class"][prop_class]["tax"] += r["tax_amount"]
    
    total_value = summary["totals"]["total_value"]
    total_tax = summary["totals"]["tax_amount"]
    
    for district, data in district_data.items():
        data["pct_of_county_value"] = round(data["total_value"] / total_value * 100, 2) if total_value else 0
        data["pct_of_county_tax"] = round(data["tax_amount"] / total_tax * 100, 2) if total_tax else 0
        data["avg_property_value"] = round(data["total_value"] / data["property_count"]) if data["property_count"] else 0
        data["by_class"] = {k: dict(v) for k, v in data["by_class"].items()}
        summary["by_district"][district] = dict(data)
    
    # Aggregate by class
    class_data = defaultdict(lambda: {"count": 0, "total_value": 0, "tax": 0})
    for r in records:
        prop_class = r["property_class"] or 0
        class_data[prop_class]["count"] += 1
        class_data[prop_class]["total_value"] += r["total_value"]
        class_data[prop_class]["tax"] += r["tax_amount"]
    
    for cls, data in class_data.items():
        data["class_name"] = PROPERTY_CLASSES.get(cls, f"Class {cls}")
        data["pct_of_total"] = round(data["total_value"] / total_value * 100, 2) if total_value else 0
        summary["by_class"][cls] = dict(data)
    
    # Aggregate by zone
    zone_data = defaultdict(lambda: {"count": 0, "total_value": 0})
    for r in records:
        zone = r["zone"] or "Unknown"
        zone_data[zone]["count"] += 1
        zone_data[zone]["total_value"] += r["total_value"]
    
    summary["by_zone"] = dict(zone_data)
    
    return summary


def parse_year(year: int) -> dict:
    """Parse a single year's tax book."""
    
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"
    
    book_info = TAX_BOOKS[year]
    pdf_path = data_dir / "raw" / "fcva" / "real-estate-tax" / book_info["file"]
    
    if not pdf_path.exists():
        return {"year": year, "records": [], "summary": {}, "error": f"File not found: {pdf_path}"}
    
    print(f"[{year}] Extracting text from {book_info['file']}...", file=sys.stderr)
    text = extract_text_from_pdf(pdf_path)
    
    print(f"[{year}] Parsing property records...", file=sys.stderr)
    
    records = []
    current_record_lines = []
    
    lines = text.split('\n')
    record_start_pattern = re.compile(r'^(\d+[A-Z]?\s*-)')
    
    for line in lines:
        line_stripped = line.strip()
        
        if not line_stripped:
            continue
        if 'COUNTY OF FREDERICK' in line_stripped.upper():
            continue
        if 'COMMISSIONER OF THE REVENUE' in line_stripped.upper():
            continue
        if line_stripped.startswith('DATE:') or line_stripped.startswith('RATE '):
            continue
        if 'PAGE TOTALS' in line_stripped.upper() or 'CLASS TOTALS' in line_stripped.upper():
            continue
        if 'FINAL TOTALS' in line_stripped.upper():
            continue
        if re.match(r'^CLASS\s*\d', line_stripped):
            continue
        if line_stripped.startswith('PAGE'):
            continue
        if line_stripped.startswith('TX390BK'):
            continue
        if 'INVALID' in line_stripped:
            continue
            
        if record_start_pattern.match(line_stripped):
            if current_record_lines:
                record = parse_property_record(current_record_lines, year)
                if record:
                    records.append(record)
            current_record_lines = [line_stripped]
        else:
            current_record_lines.append(line_stripped)
    
    if current_record_lines:
        record = parse_property_record(current_record_lines, year)
        if record:
            records.append(record)
    
    print(f"[{year}] Extracted {len(records):,} property records", file=sys.stderr)
    
    summary = calculate_summary(records, year, book_info)
    
    return {
        "year": year,
        "records": records,
        "summary": summary
    }


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <year> <output_file>", file=sys.stderr)
        sys.exit(1)
    
    year = int(sys.argv[1])
    output_file = Path(sys.argv[2])
    
    if year not in TAX_BOOKS:
        print(f"Unknown year: {year}. Valid years: {list(TAX_BOOKS.keys())}", file=sys.stderr)
        sys.exit(1)
    
    result = parse_year(year)
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(result, f)
    
    print(f"[{year}] Wrote {output_file} ({len(result.get('records', []))} records)", file=sys.stderr)


if __name__ == "__main__":
    main()
