#!/usr/bin/env python3
"""
Parse Frederick County Real Estate Tax Books (2021-2025)

Extracts individual property records with:
- Parcel code, owner, address
- Land value, improvement value, total value, tax
- Property class, zone, acreage
- Magisterial district
- Account number

Outputs normalized JSON with individual records and aggregates.
"""

import json
import re
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
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

# Normalize district names
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
    9: "Mineral"
}

# Tax book file info
TAX_BOOKS = {
    2021: {
        "file": "Real Estate 2021 Tax Book.pdf",
        "rate": 0.61,
        "commissioner": "Seth T. Thatcher"
    },
    2022: {
        "file": "Real Estate 2022 Tax Book.pdf",
        "rate": 0.61,
        "commissioner": "Seth T. Thatcher"
    },
    2023: {
        "file": "RE 2023 Book.pdf",
        "rate": 0.51,
        "commissioner": "Seth T. Thatcher"
    },
    2024: {
        "file": "RE_Book_2024.pdf",
        "rate": 0.51,
        "commissioner": "Tonya Sibert"
    },
    2025: {
        "file": "RE_2025_Book.pdf",
        "rate": 0.48,
        "commissioner": "Tonya Sibert"
    }
}


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF using pdftotext (faster than pdfplumber for bulk)."""
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
        "deed_book": None,
        "deferred_value": 0
    }
    
    full_text = " ".join(lines)
    
    # Extract parcel code (various formats)
    # Format: 43- -19- - 63 or 43 -19- 63 or 43-19-63 etc
    parcel_match = re.search(r'^(\d+[A-Z]?\s*-\s*-?\s*\d*[A-Z]?\s*-?\s*-?\s*\d*\s*-?\s*-?\s*\d*(?:-[A-Z])?)', lines[0])
    if parcel_match:
        record["parcel_code"] = re.sub(r'\s+', '', parcel_match.group(1))
    
    # Extract account number
    acct_match = re.search(r'ACCT-?\s*(\d+)', full_text)
    if acct_match:
        record["account_number"] = acct_match.group(1)
    
    # Extract district
    for district in DISTRICTS:
        if district in full_text.upper().replace(" ", ""):
            # Check for exact match or with space removed
            record["district"] = DISTRICT_NORMALIZE.get(district.replace(" ", ""), 
                                  DISTRICT_NORMALIZE.get(district))
            break
        if district.replace(" ", "") in full_text.upper().replace(" ", ""):
            record["district"] = DISTRICT_NORMALIZE.get(district)
            break
    
    # Extract values - look for patterns like "381,600 924,300 1,305,900 6,268.32"
    # Values appear on the SAME LINE as ACCT- (individual property values)
    # NOT on lines by themselves (those are page/class totals)
    
    # First, try to find values on the line containing ACCT-
    acct_line_pattern = r'([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+\.?\d*)\s+ACCT-'
    acct_match = re.search(acct_line_pattern, full_text)
    
    if acct_match:
        land = int(acct_match.group(1).replace(",", ""))
        imp = int(acct_match.group(2).replace(",", ""))
        total = int(acct_match.group(3).replace(",", ""))
        tax = float(acct_match.group(4).replace(",", ""))
        
        # Sanity check - individual property values should be reasonable
        # Max single property ~$50M (very generous)
        if total < 50_000_000 and tax < 500_000:
            record["land_value"] = land
            record["improvement_value"] = imp
            record["total_value"] = total
            record["tax_amount"] = tax
    
    # Also try land-only format (no improvement value shown)
    if record["total_value"] == 0:
        land_only_pattern = r'([\d,]+)\s+([\d,]+)\s+([\d,]+\.?\d*)\s+ACCT-'
        land_match = re.search(land_only_pattern, full_text)
        if land_match:
            val1 = int(land_match.group(1).replace(",", ""))
            val2 = int(land_match.group(2).replace(",", ""))
            tax = float(land_match.group(3).replace(",", ""))
            # If first two values are same, it's land-only (land = total)
            if val1 == val2 and val2 < 50_000_000:
                record["land_value"] = val1
                record["total_value"] = val2
                record["tax_amount"] = tax
            elif val2 < 50_000_000:
                # Otherwise val1=land, val2=total
                record["land_value"] = val1
                record["total_value"] = val2
                record["tax_amount"] = tax
    

    
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
        except:
            pass
    
    # Extract first/second half tax
    fh_match = re.search(r'FH\s*([\d,]+\.?\d*)', full_text)
    sh_match = re.search(r'SH\s*([\d,]+\.?\d*)', full_text)
    if fh_match:
        record["first_half_tax"] = float(fh_match.group(1).replace(",", ""))
    if sh_match:
        record["second_half_tax"] = float(sh_match.group(1).replace(",", ""))
    
    # Extract deferred value
    deferred_match = re.search(r'([\d,]+)\s*DEFERRED', full_text)
    if deferred_match:
        record["deferred_value"] = int(deferred_match.group(1).replace(",", ""))
    
    # Extract owner info from first few lines
    owner_lines = []
    for i, line in enumerate(lines[1:5]):  # Skip parcel line, take next 4
        line = line.strip()
        if line and not re.match(r'^(ACCT|FH|SH|AC\s|CL\s|ZN\s|\d+\.\d+\s*CL)', line):
            # Skip value lines and metadata
            if not re.match(r'^[\d,]+\s+[\d,]+\s+[\d,]+', line):
                owner_lines.append(line)
    
    if owner_lines:
        record["owner_name"] = owner_lines[0] if len(owner_lines) > 0 else None
        record["owner_address"] = owner_lines[1] if len(owner_lines) > 1 else None
        record["owner_city_state_zip"] = owner_lines[2] if len(owner_lines) > 2 else None
    
    # Extract description (subdivision, lot info)
    desc_patterns = [
        r'((?:LOT|L)\s*\d+[A-Z]?\s*(?:P\d+)?\s*(?:S\d+)?)',
        r'(LAKE\s*HOLIDAY\s*EST[.\s]*L\d+)',
        r'(SHAWNEE\s*LAND\s*L\d+)',
        r'([\w\s]+(?:SUBDIVISION|ESTATES?|VILLAGE|ACRES?|TRACT))',
    ]
    for pattern in desc_patterns:
        desc_match = re.search(pattern, full_text, re.IGNORECASE)
        if desc_match:
            record["description"] = desc_match.group(1).strip()
            break
    
    # Only return if we have meaningful data
    if record["parcel_code"] and record["total_value"] > 0:
        return record
    elif record["parcel_code"] and record["land_value"] > 0:
        return record
    
    return None


def parse_year(year: int, data_dir: Path) -> dict:
    """Parse a single year's tax book. Returns dict with records and summary."""
    
    book_info = TAX_BOOKS[year]
    pdf_path = data_dir / "raw" / "fcva" / "real-estate-tax" / book_info["file"]
    
    if not pdf_path.exists():
        print(f"  [!] File not found: {pdf_path}")
        return {"year": year, "records": [], "error": "File not found"}
    
    print(f"  [{year}] Extracting text from {book_info['file']}...")
    text = extract_text_from_pdf(pdf_path)
    
    print(f"  [{year}] Parsing property records...")
    
    records = []
    current_record_lines = []
    
    # Split into lines and process
    lines = text.split('\n')
    
    # Pattern to identify start of new property record
    record_start_pattern = re.compile(r'^(\d+[A-Z]?\s*-)')
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines and headers
        if not line:
            continue
        if 'COUNTY OF FREDERICK' in line.upper():
            continue
        if 'COMMISSIONER OF THE REVENUE' in line.upper():
            continue
        if line.startswith('DATE:') or line.startswith('RATE '):
            continue
        if 'PAGE TOTALS' in line.upper() or 'CLASS TOTALS' in line.upper():
            continue
        if 'FINAL TOTALS' in line.upper():
            continue
        if re.match(r'^CLASS\s*\d', line):
            continue
        if line.startswith('PAGE'):
            continue
            
        # Check if this is start of new record
        if record_start_pattern.match(line):
            # Process previous record
            if current_record_lines:
                record = parse_property_record(current_record_lines, year)
                if record:
                    records.append(record)
            current_record_lines = [line]
        else:
            current_record_lines.append(line)
    
    # Process last record
    if current_record_lines:
        record = parse_property_record(current_record_lines, year)
        if record:
            records.append(record)
    
    print(f"  [{year}] Extracted {len(records):,} property records")
    
    # Calculate aggregates
    summary = calculate_summary(records, year, book_info)
    
    return {
        "year": year,
        "records": records,
        "summary": summary
    }


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
        
        # By class within district
        prop_class = r["property_class"] or 0
        district_data[district]["by_class"][prop_class]["count"] += 1
        district_data[district]["by_class"][prop_class]["total_value"] += r["total_value"]
        district_data[district]["by_class"][prop_class]["tax"] += r["tax_amount"]
    
    # Convert to regular dict and calculate percentages
    total_value = summary["totals"]["total_value"]
    total_tax = summary["totals"]["tax_amount"]
    
    for district, data in district_data.items():
        data["pct_of_county_value"] = round(data["total_value"] / total_value * 100, 2) if total_value else 0
        data["pct_of_county_tax"] = round(data["tax_amount"] / total_tax * 100, 2) if total_tax else 0
        data["avg_property_value"] = round(data["total_value"] / data["property_count"]) if data["property_count"] else 0
        data["by_class"] = dict(data["by_class"])
        summary["by_district"][district] = dict(data)
    
    # Aggregate by class (county-wide)
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
    
    # Aggregate by zone (county-wide)
    zone_data = defaultdict(lambda: {"count": 0, "total_value": 0})
    for r in records:
        zone = r["zone"] or "Unknown"
        zone_data[zone]["count"] += 1
        zone_data[zone]["total_value"] += r["total_value"]
    
    summary["by_zone"] = dict(zone_data)
    
    return summary


def main():
    data_dir = Path(__file__).parent.parent / "data"
    output_dir = data_dir / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    years = [2021, 2022, 2023, 2024, 2025]
    
    print(f"Parsing Frederick County Real Estate Tax Books")
    print(f"Years: {years}")
    print(f"Output: {output_dir}")
    print()
    
    all_results = {}
    all_records = []
    
    # Process years in parallel
    with ProcessPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(parse_year, year, data_dir): year for year in years}
        
        for future in as_completed(futures):
            year = futures[future]
            try:
                result = future.result()
                all_results[year] = result
                all_records.extend(result.get("records", []))
                print(f"  [{year}] Complete: {len(result.get('records', []))} records")
            except Exception as e:
                print(f"  [{year}] ERROR: {e}")
                all_results[year] = {"year": year, "error": str(e), "records": []}
    
    print()
    print(f"Total records extracted: {len(all_records):,}")
    
    # Build final output structure
    output = {
        "metadata": {
            "source": "Frederick County Commissioner of Revenue",
            "source_url": "https://www.fcva.us/departments/commissioner-of-the-revenue",
            "description": "Real Estate Tax Assessment Data",
            "years": years,
            "districts": list(DISTRICT_NORMALIZE.values()),
            "property_classes": PROPERTY_CLASSES,
            "processed_date": datetime.now().isoformat(),
            "total_records": len(all_records)
        },
        "annual_summaries": [all_results[y].get("summary", {}) for y in sorted(years)],
        "records": all_records
    }
    
    # Write full output
    output_file = output_dir / "real_estate_tax.json"
    print(f"Writing {output_file}...")
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    
    # Write summary-only file (smaller, for dashboards)
    summary_output = {
        "metadata": output["metadata"],
        "annual_summaries": output["annual_summaries"]
    }
    summary_file = output_dir / "real_estate_tax_summary.json"
    print(f"Writing {summary_file}...")
    with open(summary_file, "w") as f:
        json.dump(summary_output, f, indent=2)
    
    # Print summary stats
    print()
    print("=" * 60)
    print("SUMMARY BY YEAR")
    print("=" * 60)
    for year in sorted(years):
        summary = all_results[year].get("summary", {})
        if summary:
            totals = summary.get("totals", {})
            print(f"\n{year} (Rate: ${summary.get('tax_rate', 0):.2f}/$100)")
            print(f"  Records:      {summary.get('total_records', 0):>12,}")
            print(f"  Total Value:  ${totals.get('total_value', 0):>15,}")
            print(f"  Tax Revenue:  ${totals.get('tax_amount', 0):>15,.2f}")
    
    print()
    print("=" * 60)
    print("2025 BY DISTRICT")
    print("=" * 60)
    if 2025 in all_results and "summary" in all_results[2025]:
        by_district = all_results[2025]["summary"].get("by_district", {})
        for district in sorted(by_district.keys()):
            data = by_district[district]
            print(f"\n{district}:")
            print(f"  Properties:   {data['property_count']:>10,}")
            print(f"  Total Value:  ${data['total_value']:>14,}")
            print(f"  Tax Revenue:  ${data['tax_amount']:>14,.2f}")
            print(f"  % of County:  {data['pct_of_county_value']:>10.1f}%")
    
    print()
    print(f"Output written to:")
    print(f"  - {output_file} ({output_file.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"  - {summary_file} ({summary_file.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
