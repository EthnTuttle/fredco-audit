#!/usr/bin/env python3
"""
Parse Frederick County Budget PDFs to extract county-wide financial data.
Extracts department expenditures, staffing levels, and fund summaries.
"""

import json
import re
from datetime import datetime
from pathlib import Path
import pdfplumber

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw" / "fcva" / "budgets"
PROCESSED_DIR = DATA_DIR / "processed"

def extract_text_from_pdf(pdf_path, max_pages=50):
    """Extract text from PDF."""
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            text += page.extract_text() or ""
            text += "\n\n--- PAGE BREAK ---\n\n"
    return text


def parse_number(s):
    """Parse a number from string, handling commas and parentheses for negatives."""
    if not s or s.strip() in ['-', '', 'N/A']:
        return None
    s = s.strip().replace(',', '').replace('$', '')
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return None


def extract_general_fund_summary(text, fiscal_year):
    """Extract General Fund expenditure summary by function."""
    data = {
        "fiscal_year": fiscal_year,
        "general_fund": {}
    }
    
    # Look for General Fund expenditure patterns
    # Pattern varies by year, so we'll try multiple approaches
    
    # Common department categories to look for
    categories = [
        ("general_govt_admin", r"General\s+Govern(?:ment|mental)\s+Admin(?:istration)?.*?([0-9,]+)"),
        ("judicial_admin", r"Judicial\s+Admin(?:istration)?.*?([0-9,]+)"),
        ("public_safety", r"Public\s+Safety.*?([0-9,]+)"),
        ("public_works", r"Public\s+Works.*?([0-9,]+)"),
        ("health_welfare", r"Health.*?(?:and|&)?\s*(?:Social\s+)?(?:Welfare|Services).*?([0-9,]+)"),
        ("parks_recreation", r"Parks.*?(?:Recreation|Cultural).*?([0-9,]+)"),
        ("community_dev", r"(?:Community\s+Development|Planning.*?Development).*?([0-9,]+)"),
    ]
    
    for key, pattern in categories:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data["general_fund"][key] = parse_number(match.group(1))
    
    return data


def extract_position_counts(text, fiscal_year):
    """Extract staffing/position counts by department."""
    positions = {
        "fiscal_year": fiscal_year,
        "departments": {}
    }
    
    # Look for FTE or position count tables
    # Common patterns: "Department Name ... XX.X FTE" or position count tables
    
    # Try to find a staffing summary section
    staffing_section = re.search(
        r"(?:Position|Staffing|FTE|Personnel)\s+Summary.*?(?=\n\n|\Z)",
        text, 
        re.IGNORECASE | re.DOTALL
    )
    
    if staffing_section:
        section_text = staffing_section.group(0)
        # Extract department-position pairs
        dept_pattern = r"([A-Za-z\s&/]+?)\s+(\d+\.?\d*)\s*(?:FTE|positions?)?"
        matches = re.findall(dept_pattern, section_text)
        for dept, count in matches:
            dept_clean = dept.strip()
            if len(dept_clean) > 3 and parse_number(count):
                positions["departments"][dept_clean] = parse_number(count)
    
    return positions


def extract_fund_totals(text, fiscal_year):
    """Extract total budget by fund type."""
    funds = {
        "fiscal_year": fiscal_year,
        "funds": {}
    }
    
    # Common fund patterns
    fund_patterns = [
        ("general_fund", r"General\s+Fund\s+(?:Total)?.*?([0-9,]+(?:\.[0-9]+)?)"),
        ("school_operating", r"School\s+Operating.*?([0-9,]+(?:\.[0-9]+)?)"),
        ("school_debt", r"School\s+Debt.*?([0-9,]+(?:\.[0-9]+)?)"),
        ("school_capital", r"School\s+Capital.*?([0-9,]+(?:\.[0-9]+)?)"),
        ("capital_projects", r"Capital\s+(?:Projects?\s+)?Fund.*?([0-9,]+(?:\.[0-9]+)?)"),
        ("debt_service", r"Debt\s+Service.*?([0-9,]+(?:\.[0-9]+)?)"),
    ]
    
    for key, pattern in fund_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Take the largest value (likely the total)
            values = [parse_number(m) for m in matches if parse_number(m)]
            if values:
                funds["funds"][key] = max(values)
    
    return funds


def parse_budget_pdf(pdf_path):
    """Parse a single budget PDF and extract key data."""
    filename = pdf_path.name
    
    # Determine fiscal year from filename
    fy_match = re.search(r"FY(\d{4})", filename)
    if not fy_match:
        return None
    fiscal_year = f"FY{fy_match.group(1)}"
    
    # Determine document type
    if "proposed" in filename.lower():
        doc_type = "proposed"
    elif "adopted" in filename.lower():
        doc_type = "adopted"
    elif "acfr" in filename.lower():
        doc_type = "acfr"
    else:
        doc_type = "unknown"
    
    print(f"Parsing {filename}...")
    
    try:
        text = extract_text_from_pdf(pdf_path)
    except Exception as e:
        print(f"  Error reading PDF: {e}")
        return None
    
    result = {
        "fiscal_year": fiscal_year,
        "source_file": filename,
        "doc_type": doc_type,
        "extracted_date": datetime.now().isoformat(),
    }
    
    # Extract various data sections
    gf_data = extract_general_fund_summary(text, fiscal_year)
    result["general_fund_expenditures"] = gf_data.get("general_fund", {})
    
    positions = extract_position_counts(text, fiscal_year)
    result["positions"] = positions.get("departments", {})
    
    funds = extract_fund_totals(text, fiscal_year)
    result["fund_totals"] = funds.get("funds", {})
    
    # Extract raw text snippets for manual review
    result["_text_length"] = len(text)
    
    return result


def main():
    """Main function to parse all budget PDFs."""
    print("Frederick County Budget Parser")
    print("=" * 50)
    
    # Get all proposed budget PDFs (most detailed)
    proposed_pdfs = sorted(RAW_DIR.glob("*_proposed.pdf"))
    
    all_data = {
        "description": "Frederick County Government Budget Data",
        "source": "Frederick County, Virginia Annual Budget Documents",
        "source_url": "https://www.fcva.us/departments/finance/budget",
        "extracted_date": datetime.now().isoformat(),
        "fiscal_years": [],
        "data": []
    }
    
    for pdf_path in proposed_pdfs:
        result = parse_budget_pdf(pdf_path)
        if result:
            all_data["data"].append(result)
            all_data["fiscal_years"].append(result["fiscal_year"])
    
    # Sort by fiscal year
    all_data["data"].sort(key=lambda x: x["fiscal_year"])
    all_data["fiscal_years"].sort()
    
    # Save raw extracted data
    output_path = PROCESSED_DIR / "county_budget_raw.json"
    with open(output_path, "w") as f:
        json.dump(all_data, f, indent=2)
    print(f"\nRaw data saved to: {output_path}")
    
    # Print summary
    print("\n" + "=" * 50)
    print("EXTRACTION SUMMARY")
    print("=" * 50)
    for item in all_data["data"]:
        print(f"\n{item['fiscal_year']} ({item['doc_type']}):")
        print(f"  General Fund categories: {len(item.get('general_fund_expenditures', {}))}")
        print(f"  Position departments: {len(item.get('positions', {}))}")
        print(f"  Fund totals: {len(item.get('fund_totals', {}))}")
    
    return all_data


if __name__ == "__main__":
    main()
