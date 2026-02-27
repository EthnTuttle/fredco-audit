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

v2 (2026-02-27): Fixed $50M cap, acreage zip bug, owner field cleaning,
                  land-only split, FH/SH deferred handling, added validation.
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

# Known PDF FINAL TOTALS for validation (from the tax book PDFs themselves)
PDF_FINAL_TOTALS = {
    2021: {"total_value": 12_369_526_100, "tax_amount": 75_454_109.10},
    2022: {"total_value": 12_654_139_400, "tax_amount": 77_190_250.34},
    2023: {"total_value": 15_485_850_300, "tax_amount": 78_977_835.97},
    2024: {"total_value": 15_924_061_400, "tax_amount": 81_212_713.14},
    2025: {"total_value": 19_522_013_569, "tax_amount": 93_705_665.13},
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


def clean_owner_name(raw: str | None) -> str | None:
    """Strip embedded FH tax amount and deferred info from owner_name field.

    Examples:
        'A & R RENTALS LLC  FH  441.92'  -> 'A & R RENTALS LLC'
        'ADAMS DONALD CARSON JR  644,500 DEFERRED  644,500  3,286.95  FH  818.04'
            -> 'ADAMS DONALD CARSON JR'
        'ABBENE SANDRA   UNIT 8 BLDG 1   FH  398.82'
            -> 'ABBENE SANDRA   UNIT 8 BLDG 1'
    """
    if not raw:
        return raw
    # Strip deferred info + FH (deferred comes before FH when present)
    cleaned = re.sub(
        r'\s+[\d,]+\s+DEFERRED\s+[\d,]+\s+[\d,]+\.\d+\s+FH\s+[\d,.]+$',
        '', raw
    )
    # Strip standalone FH at end
    cleaned = re.sub(r'\s+FH\s+[\d,.]+$', '', cleaned)
    return cleaned.rstrip() or None


def clean_owner_address(raw: str | None) -> str | None:
    """Strip embedded SH tax amount from owner_address field.

    Examples:
        '230 DEPENDENCE LN  SH  441.91'  -> '230 DEPENDENCE LN'
    """
    if not raw:
        return raw
    cleaned = re.sub(r'\s+SH\s+[\d,.]+$', '', raw)
    return cleaned.rstrip() or None


def clean_city_state_zip(raw: str | None) -> str | None:
    """Strip AC/CL/ZN/district metadata from owner_city_state_zip field.

    Examples:
        'MIDDLETOWN VA 22645-1555  AC  .00 CL 1 ZN RP  SHAWNEE'
            -> 'MIDDLETOWN VA 22645-1555'
        'WINCHESTER VA 22603-4656  AC  2.19 CL 4 ZN M1  GAINESBORO'
            -> 'WINCHESTER VA 22603-4656'
    """
    if not raw:
        return raw
    # Truncate at the AC metadata field
    cleaned = re.sub(r'\s+AC\s+.*$', '', raw)
    # Also handle the rare case where CL appears without AC
    cleaned = re.sub(r'\s+CL\s+\d.*$', '', cleaned)
    return cleaned.rstrip() or None


def extract_acreage_from_csz(raw_csz: str | None) -> float | None:
    """Extract acreage from the raw city_state_zip line (the AC field).

    The AC field appears after the zip code:
        'MIDDLETOWN VA 22645-1555  AC  .00 CL 1 ZN RP  SHAWNEE'
                                       ^^^
    Previous regex matched zip+4 digits before AC, producing garbage like 1555.0.
    This function specifically extracts the value AFTER the AC label.
    """
    if not raw_csz:
        return None
    m = re.search(r'\bAC\s+([\d.]+)', raw_csz)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def extract_acreage_from_description(full_text: str) -> float | None:
    """Extract acreage from the description/location column.

    Examples from the first line of a record:
        '82.86 ACRES'  -> 82.86
        '.45 ACRE'     -> 0.45
        '5.21 ACRES'   -> 5.21
    """
    m = re.search(r'([\d.]+)\s+ACRES?\b', full_text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def parse_property_record(lines: list[str], year: int, stats: dict) -> dict | None:
    """Parse a single property record from extracted lines.

    Args:
        lines: The raw text lines for this record
        year: Tax year
        stats: Mutable dict for tracking parse statistics
    """
    if not lines:
        return None

    record = {
        "year": year,
        "parcel_code": None,
        "owner_name": None,
        "owner_name_raw": None,
        "owner_address": None,
        "owner_address_raw": None,
        "owner_city_state_zip": None,
        "owner_city_state_zip_raw": None,
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

    # Extract district -- search the raw city/state/zip line and surrounding text
    # District name appears at the far right of the city/state/zip line
    for district in DISTRICTS:
        if district in full_text.upper().replace(" ", ""):
            record["district"] = DISTRICT_NORMALIZE.get(district.replace(" ", ""),
                                  DISTRICT_NORMALIZE.get(district))
            break
        if district.replace(" ", "") in full_text.upper().replace(" ", ""):
            record["district"] = DISTRICT_NORMALIZE.get(district)
            break

    # ---------------------------------------------------------------
    # Extract values: land, improvement, total, tax
    # Values appear on the SAME LINE as ACCT- in the PDF layout
    # Format: "67,000    130,000       197,000    1,004.70      ACCT-   8028405"
    # ---------------------------------------------------------------

    # Try 4-value pattern: land imp total tax ACCT-
    acct_line_pattern = r'([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+\.?\d*)\s+ACCT-'
    acct_match = re.search(acct_line_pattern, full_text)

    if acct_match:
        land = int(acct_match.group(1).replace(",", ""))
        imp = int(acct_match.group(2).replace(",", ""))
        total = int(acct_match.group(3).replace(",", ""))
        tax = float(acct_match.group(4).replace(",", ""))

        # FIX: Removed $50M cap. Frederick County has legitimate properties
        # assessed at $90M+ (e.g., Village at Orchard Ridge, Navy Federal).
        # Old code silently dropped 3-4 large commercial properties per year.

        # FIX: Detect land-only records mismatched by 4-value regex.
        # For land-only records like "69A-1-32-115  SHAWNEELAND L115  3,400  3,400  17.34 ACCT-"
        # the 4-value regex captures: land=115(parcel digit), imp=3400, total=3400, tax=17.34
        # or sometimes: land=32, imp=115, total=3400, tax=3400 then tax gets wrong.
        # Signature: imp == total (the "improvement" is really the total, and "land" is junk).
        if imp == total and land < 500 and total >= 1000:
            # This is a land-only record where a parcel digit was captured as "land"
            record["land_value"] = total
            record["improvement_value"] = 0
            record["total_value"] = total
            record["tax_amount"] = tax
            stats["land_imp_parcel_fix"] = stats.get("land_imp_parcel_fix", 0) + 1
        else:
            record["land_value"] = land
            record["improvement_value"] = imp
            record["total_value"] = total
            record["tax_amount"] = tax

    # Try land-only format (no improvement column): "3,400  3,400  17.34 ACCT-"
    if record["total_value"] == 0:
        land_only_pattern = r'([\d,]+)\s+([\d,]+)\s+([\d,]+\.?\d*)\s+ACCT-'
        land_match = re.search(land_only_pattern, full_text)
        if land_match:
            val1 = int(land_match.group(1).replace(",", ""))
            val2 = int(land_match.group(2).replace(",", ""))
            tax = float(land_match.group(3).replace(",", ""))

            # FIX: For land-only records like "3,400  3,400  17.34 ACCT-",
            # the 3-value regex can capture trailing parcel digits as val1.
            # E.g., parcel "69A-1-32-115" with "3,400  3,400  17.34" -> val1=115.
            # Detect this: if val1 is very small (< 500) and val1 != val2,
            # it's likely a parcel digit capture, not a real land value.
            if val1 == val2:
                # Land = Total (true land-only, no improvement)
                record["land_value"] = val1
                record["total_value"] = val2
                record["tax_amount"] = tax
            elif val1 < 500 and val2 >= 1000:
                # val1 is likely a parcel code fragment, val2 is the real total
                # Treat as land-only: land=total (the land IS the total value)
                record["land_value"] = val2
                record["total_value"] = val2
                record["tax_amount"] = tax
                stats["land_only_parcel_fix"] = stats.get("land_only_parcel_fix", 0) + 1
            else:
                # val1=land, val2=total (partial improvement not shown)
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

    # ---------------------------------------------------------------
    # Extract acreage -- FIX for zip-code contamination
    # Old regex: ([\d.]+)\s*(?:ACRES?|AC\b) matched zip+4 before AC
    #   e.g., "22645-1555  AC  .00" -> captured "1555" as acreage
    # New approach: extract from the AC field in city_state_zip line,
    # and separately from "X.XX ACRES" in the description column.
    # ---------------------------------------------------------------

    # Extract owner info FIRST (we need it for acreage extraction)
    owner_lines = []
    for i, line in enumerate(lines[1:5]):  # Skip parcel line, take next 4
        line = line.strip()
        if line and not re.match(r'^(ACCT|FH|SH|AC\s|CL\s|ZN\s|\d+\.\d+\s*CL)', line):
            # Skip value lines and metadata
            if not re.match(r'^[\d,]+\s+[\d,]+\s+[\d,]+', line):
                owner_lines.append(line)

    # Store raw owner fields, then clean them
    if owner_lines:
        record["owner_name_raw"] = owner_lines[0] if len(owner_lines) > 0 else None
        record["owner_address_raw"] = owner_lines[1] if len(owner_lines) > 1 else None
        record["owner_city_state_zip_raw"] = owner_lines[2] if len(owner_lines) > 2 else None

        record["owner_name"] = clean_owner_name(record["owner_name_raw"])
        record["owner_address"] = clean_owner_address(record["owner_address_raw"])
        record["owner_city_state_zip"] = clean_city_state_zip(record["owner_city_state_zip_raw"])

    # Extract acreage: prefer AC field from city_state_zip line (most precise)
    acreage = extract_acreage_from_csz(record["owner_city_state_zip_raw"])
    if acreage is None:
        # Fallback: look for "X.XX ACRES" in description/location column
        acreage = extract_acreage_from_description(full_text)
    record["acreage"] = acreage

    # ---------------------------------------------------------------
    # Extract FH/SH tax -- FIX for deferred records
    # Deferred records have TWO sets of values. The FH/SH we want is
    # on the owner_name/owner_address lines (gross tax), NOT the
    # deferred adjustment line which also contains FH amounts.
    #
    # Normal record:
    #   owner_name_raw:  "A & R RENTALS  FH  502.35"
    #   owner_addr_raw:  "230 DEPENDENCE LN  SH  502.35"
    #
    # Deferred record:
    #   owner_name_raw:  "ADAMS DONALD  644,500 DEFERRED 644,500 3,286.95 FH 818.04"
    #   owner_addr_raw:  "10609 N FREDERICK PIKE  SH  818.04"
    #   csz_raw:         "WHITACRE VA 22625-1524 AC 243.70 CL 6 ZN RA 148,100 172,700 320,800 1,636.08 GAINESBORO"
    #
    # Strategy: extract FH from owner_name line, SH from owner_address line.
    # This gets the correct (gross) half-tax in both normal and deferred cases.
    # ---------------------------------------------------------------

    # Extract deferred value first (needed for stats)
    deferred_match = re.search(r'([\d,]+)\s*DEFERRED', full_text)
    if deferred_match:
        record["deferred_value"] = int(deferred_match.group(1).replace(",", ""))

    # FH from owner_name line
    if record["owner_name_raw"]:
        fh_match = re.search(r'FH\s+([\d,]+\.?\d*)', record["owner_name_raw"])
        if fh_match:
            try:
                record["first_half_tax"] = float(fh_match.group(1).replace(",", ""))
            except ValueError:
                pass

    # SH from owner_address line
    if record["owner_address_raw"]:
        sh_match = re.search(r'SH\s+([\d,]+\.?\d*)', record["owner_address_raw"])
        if sh_match:
            try:
                record["second_half_tax"] = float(sh_match.group(1).replace(",", ""))
            except ValueError:
                pass

    # If we didn't find FH/SH on the expected lines, fall back to full_text search
    # (handles edge cases where the layout shifts)
    if record["first_half_tax"] == 0.0 and record["tax_amount"] > 0:
        fh_match = re.search(r'\bFH\s+([\d,]+\.?\d*)', full_text)
        if fh_match:
            try:
                record["first_half_tax"] = float(fh_match.group(1).replace(",", ""))
            except ValueError:
                pass
    if record["second_half_tax"] == 0.0 and record["tax_amount"] > 0:
        sh_match = re.search(r'\bSH\s+([\d,]+\.?\d*)', full_text)
        if sh_match:
            try:
                record["second_half_tax"] = float(sh_match.group(1).replace(",", ""))
            except ValueError:
                pass

    # Extract description (subdivision, lot info) from the first line
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

    # Validate: FH + SH should approximately equal tax_amount
    if record["tax_amount"] > 0:
        fh_sh_sum = record["first_half_tax"] + record["second_half_tax"]
        if abs(fh_sh_sum - record["tax_amount"]) > 1.0 and fh_sh_sum > 0:
            stats["fh_sh_mismatch"] = stats.get("fh_sh_mismatch", 0) + 1

    # Track stats
    stats["total_parsed"] = stats.get("total_parsed", 0) + 1

    # Only return if we have meaningful data
    if record["parcel_code"] and record["total_value"] > 0:
        stats["records_with_value"] = stats.get("records_with_value", 0) + 1
        return record
    elif record["parcel_code"] and record["land_value"] > 0:
        stats["records_with_value"] = stats.get("records_with_value", 0) + 1
        return record

    if not record["parcel_code"]:
        stats["dropped_no_parcel"] = stats.get("dropped_no_parcel", 0) + 1
    else:
        stats["dropped_no_value"] = stats.get("dropped_no_value", 0) + 1

    return None


def parse_year(year: int, data_dir: Path) -> dict:
    """Parse a single year's tax book. Returns dict with records and summary."""

    book_info = TAX_BOOKS[year]
    pdf_path = data_dir / "raw" / "real-estate" / book_info["file"]

    if not pdf_path.exists():
        print(f"  [!] File not found: {pdf_path}")
        return {"year": year, "records": [], "error": "File not found"}

    print(f"  [{year}] Extracting text from {book_info['file']}...")
    text = extract_text_from_pdf(pdf_path)

    print(f"  [{year}] Parsing property records...")

    records = []
    current_record_lines = []
    stats = {}

    # Split into lines and process
    lines = text.split('\n')

    # Count ACCT markers in raw text for validation
    acct_count = len(re.findall(r'ACCT-?\s*\d+', text))
    stats["acct_markers_in_pdf"] = acct_count

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
                record = parse_property_record(current_record_lines, year, stats)
                if record:
                    records.append(record)
            current_record_lines = [line]
        else:
            current_record_lines.append(line)

    # Process last record
    if current_record_lines:
        record = parse_property_record(current_record_lines, year, stats)
        if record:
            records.append(record)

    print(f"  [{year}] Extracted {len(records):,} property records")

    # --- Validation ---
    print(f"  [{year}] Parse stats:")
    print(f"           ACCT markers in PDF: {stats.get('acct_markers_in_pdf', 0):,}")
    print(f"           Records parsed:      {stats.get('total_parsed', 0):,}")
    print(f"           Records with value:  {stats.get('records_with_value', 0):,}")
    print(f"           Dropped (no parcel): {stats.get('dropped_no_parcel', 0):,}")
    print(f"           Dropped (no value):  {stats.get('dropped_no_value', 0):,}")
    print(f"           FH+SH mismatches:    {stats.get('fh_sh_mismatch', 0):,}")
    print(f"           Land/imp parcel fix: {stats.get('land_imp_parcel_fix', 0):,}")
    print(f"           Land-only parcel fix: {stats.get('land_only_parcel_fix', 0):,}")

    # Validate against known PDF FINAL TOTALS
    if year in PDF_FINAL_TOTALS:
        expected = PDF_FINAL_TOTALS[year]
        parsed_total = sum(r["total_value"] for r in records)
        parsed_tax = sum(r["tax_amount"] for r in records)
        value_diff = parsed_total - expected["total_value"]
        tax_diff = parsed_tax - expected["tax_amount"]
        value_pct = (value_diff / expected["total_value"]) * 100 if expected["total_value"] else 0
        tax_pct = (tax_diff / expected["tax_amount"]) * 100 if expected["tax_amount"] else 0
        print(f"  [{year}] Validation vs PDF FINAL TOTALS:")
        print(f"           Total Value: parsed ${parsed_total:>15,} vs expected ${expected['total_value']:>15,}  ({value_pct:+.3f}%)")
        print(f"           Tax Amount:  parsed ${parsed_tax:>15,.2f} vs expected ${expected['tax_amount']:>15,.2f}  ({tax_pct:+.3f}%)")
        stats["validation"] = {
            "expected_total_value": expected["total_value"],
            "parsed_total_value": parsed_total,
            "value_diff": value_diff,
            "value_diff_pct": round(value_pct, 4),
            "expected_tax": expected["tax_amount"],
            "parsed_tax": parsed_tax,
            "tax_diff": tax_diff,
            "tax_diff_pct": round(tax_pct, 4),
        }

    # Calculate aggregates
    summary = calculate_summary(records, year, book_info)
    summary["parse_stats"] = stats

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

    print(f"Parsing Frederick County Real Estate Tax Books (v2 - cleaned)")
    print(f"Years: {years}")
    print(f"Output: {output_dir}")
    print(f"Fixes applied: $50M cap removed, acreage zip-code bug fixed,")
    print(f"  owner fields cleaned, land-only split fixed, FH/SH deferred fixed")
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
                import traceback
                traceback.print_exc()
                all_results[year] = {"year": year, "error": str(e), "records": []}

    print()
    print(f"Total records extracted: {len(all_records):,}")

    # Build final output structure
    output = {
        "metadata": {
            "source": "Frederick County Commissioner of Revenue",
            "source_url": "https://www.fcva.us/departments/commissioner-of-the-revenue",
            "description": "Real Estate Tax Assessment Data (v2 - cleaned)",
            "years": years,
            "districts": sorted(set(DISTRICT_NORMALIZE.values())),
            "property_classes": {str(k): v for k, v in PROPERTY_CLASSES.items()},
            "processed_date": datetime.now().isoformat(),
            "total_records": len(all_records),
            "fixes_applied": [
                "Removed $50M property value cap (was dropping 3-4 large commercial properties/year)",
                "Fixed acreage extraction (was capturing zip+4 suffix as acreage)",
                "Cleaned owner_name field (stripped embedded FH tax amounts and deferred info)",
                "Cleaned owner_address field (stripped embedded SH tax amounts)",
                "Cleaned owner_city_state_zip field (stripped AC/CL/ZN/district metadata)",
                "Fixed land/improvement split for land-only records (was capturing parcel digits)",
                "Fixed FH/SH extraction for deferred records (was reading wrong values)",
                "Added raw owner fields (owner_name_raw, owner_address_raw, owner_city_state_zip_raw)",
                "Added validation against PDF FINAL TOTALS",
            ]
        },
        "annual_summaries": [all_results[y].get("summary", {}) for y in sorted(years)],
        "records": all_records
    }

    # Write full output
    output_file = output_dir / "real_estate_tax.json"
    print(f"\nWriting {output_file}...")
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
    print("=" * 80)
    print("SUMMARY BY YEAR")
    print("=" * 80)
    for year in sorted(years):
        summary = all_results[year].get("summary", {})
        if summary:
            totals = summary.get("totals", {})
            print(f"\n{year} (Rate: ${summary.get('tax_rate', 0):.2f}/$100)")
            print(f"  Records:      {summary.get('total_records', 0):>12,}")
            print(f"  Total Value:  ${totals.get('total_value', 0):>15,}")
            print(f"  Tax Revenue:  ${totals.get('tax_amount', 0):>15,.2f}")

    # Print validation summary
    print()
    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    for year in sorted(years):
        summary = all_results[year].get("summary", {})
        stats = summary.get("parse_stats", {})
        validation = stats.get("validation", {})
        if validation:
            print(f"\n{year}:")
            print(f"  Value gap: {validation['value_diff_pct']:+.3f}%  (${validation['value_diff']:+,})")
            print(f"  Tax gap:   {validation['tax_diff_pct']:+.3f}%  (${validation['tax_diff']:+,.2f})")

    print()
    print("=" * 80)
    print("2025 BY DISTRICT")
    print("=" * 80)
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
