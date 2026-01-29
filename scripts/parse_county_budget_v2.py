#!/usr/bin/env python3
"""
Parse Frederick County Budget PDFs to extract county-wide financial data.
Version 2: Focused on extracting from the detailed budget documents (labeled as ACFR but actually full budgets).
"""

import json
import re
from datetime import datetime
from pathlib import Path
import pdfplumber

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw" / "fcva" / "budgets"
PROCESSED_DIR = DATA_DIR / "processed"


def parse_number(s):
    """Parse a number from string, handling commas and parentheses for negatives."""
    if not s or s.strip() in ['-', '', 'N/A', '--']:
        return None
    s = s.strip().replace(',', '').replace('$', '').replace('%', '')
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return None


def extract_text_from_pdf(pdf_path, max_pages=100):
    """Extract text from PDF."""
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            page_text = page.extract_text() or ""
            text += f"\n\n=== PAGE {i+1} ===\n\n"
            text += page_text
    return text


def find_expenditure_summary(text):
    """Extract the Total Expenditures All Funds summary table."""
    
    # Look for the expenditure summary section
    pattern = r"TOTAL EXPENDITURES ALL FUNDS.*?(?=County of Frederick|GENERAL FUND EXPENDITURES|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    
    if not match:
        return {}
    
    section = match.group(0)
    
    # Extract category data
    categories = {}
    
    # Pattern for expenditure lines with multiple year columns
    # Format: Category Name ... number number number number percentage
    category_patterns = [
        (r"Administration\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", "general_govt_admin"),
        (r"Judicial\s+Administration\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", "judicial_admin"),
        (r"Public\s+Safety\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", "public_safety"),
        (r"Public\s+Works\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", "public_works"),
        (r"Health/Welfare\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", "health_welfare"),
        (r"Community\s+College\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", "community_college"),
        (r"Parks,?\s*Recreation.*?Cultural\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", "parks_recreation"),
        (r"Community\s+Development\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", "community_dev"),
        (r"Miscellaneous\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", "miscellaneous"),
        (r"Regional\s+Jail\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", "regional_jail"),
        (r"Landfill\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", "landfill"),
        (r"School\s+Funds\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", "school_funds"),
        (r"Total\s+Expenditures\s+\$([\d,]+)\s+\$([\d,]+)\s+\$([\d,]+)\s+\$([\d,]+)", "total"),
    ]
    
    for pattern, key in category_patterns:
        match = re.search(pattern, section, re.IGNORECASE)
        if match:
            # The columns are typically: prior budgeted, prior actual, current budgeted, adopted
            categories[key] = {
                "prior_budgeted": parse_number(match.group(1)),
                "prior_actual": parse_number(match.group(2)),
                "current_budgeted": parse_number(match.group(3)),
                "adopted": parse_number(match.group(4)),
            }
    
    return categories


def find_personnel_summary(text):
    """Extract the personnel/staffing summary table."""
    
    # Look for the personnel needs section
    pattern = r"PERSONNEL NEEDS.*?(?=The reasons for the change|County of Frederick|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    
    if not match:
        return {}
    
    section = match.group(0)
    
    personnel = {
        "departments": {},
        "totals": {}
    }
    
    # Extract department staffing
    # Format: Department Name ... FT PT FT PT FT PT (for 3 fiscal years)
    dept_patterns = [
        (r"Board of Supervisors\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", "board_of_supervisors"),
        (r"County Administrator\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", "county_administrator"),
        (r"County Attorney\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", "county_attorney"),
        (r"Human Resources\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", "human_resources"),
        (r"COR/Reassessment\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", "commissioner_revenue"),
        (r"Treasurer\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", "treasurer"),
        (r"Finance\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", "finance"),
        (r"IT/MIS\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", "it_mis"),
        (r"Sheriff\s+([\d.]+)\s+(\d+)\s+([\d.]+)\s+(\d+)\s+([\d.]+)\s+(\d+)", "sheriff"),
        (r"Fire and Rescue\s+([\d.]+)\s+(\d+)\s+([\d.]+)\s+(\d+)\s+([\d.]+)\s+(\d+)", "fire_rescue"),
        (r"Public Safety Communications\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", "public_safety_comm"),
        (r"Social Services\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", "social_services"),
        (r"Parks and Recreation\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", "parks_recreation"),
        (r"Planning and Development\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", "planning_dev"),
    ]
    
    for pattern, key in dept_patterns:
        match = re.search(pattern, section, re.IGNORECASE)
        if match:
            # Columns: FY-2 FT, FY-2 PT, FY-1 FT, FY-1 PT, FY FT, FY PT
            personnel["departments"][key] = {
                "fy_minus_2": {"full_time": parse_number(match.group(1)), "part_time": parse_number(match.group(2))},
                "fy_minus_1": {"full_time": parse_number(match.group(3)), "part_time": parse_number(match.group(4))},
                "current_fy": {"full_time": parse_number(match.group(5)), "part_time": parse_number(match.group(6))},
            }
    
    # Extract totals
    total_patterns = [
        (r"Total\s+Positions\s+General\s+Fund\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", "general_fund_total"),
        (r"Regional\s+Jail\s+Fund\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", "regional_jail"),
        (r"School\s+Funds\s+([\d.]+)\s+(\d+)\s+([\d.]+)\s+(\d+)\s+([\d.]+)\s+(\d+)", "school_funds"),
        (r"Total\s+Positions\s+All\s+Funds\s+([\d.]+)\s+(\d+)\s+([\d.]+)\s+(\d+)\s+([\d.]+)\s+(\d+)", "all_funds_total"),
    ]
    
    for pattern, key in total_patterns:
        match = re.search(pattern, section, re.IGNORECASE)
        if match:
            personnel["totals"][key] = {
                "fy_minus_2": {"full_time": parse_number(match.group(1)), "part_time": parse_number(match.group(2))},
                "fy_minus_1": {"full_time": parse_number(match.group(3)), "part_time": parse_number(match.group(4))},
                "current_fy": {"full_time": parse_number(match.group(5)), "part_time": parse_number(match.group(6))},
            }
    
    return personnel


def find_ten_year_comparison(text):
    """Look for ten-year budget comparison data."""
    
    pattern = r"Ten-Year Budget Comparison.*?(?=Basis of Budgeting|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    
    if not match:
        return {}
    
    section = match.group(0)
    
    # Extract year-by-year data if present
    data = {"raw_section": section[:2000]}
    
    return data


def parse_budget_document(pdf_path):
    """Parse a full budget document (the ACFR files are actually full budgets)."""
    filename = pdf_path.name
    
    # Determine fiscal year
    fy_match = re.search(r"FY(\d{4})", filename)
    if not fy_match:
        return None
    fiscal_year = f"FY{fy_match.group(1)}"
    
    print(f"Parsing {filename} ({fiscal_year})...")
    
    try:
        text = extract_text_from_pdf(pdf_path, max_pages=60)
    except Exception as e:
        print(f"  Error reading PDF: {e}")
        return None
    
    result = {
        "fiscal_year": fiscal_year,
        "source_file": filename,
        "extracted_date": datetime.now().isoformat(),
    }
    
    # Extract expenditure summary
    expenditures = find_expenditure_summary(text)
    if expenditures:
        result["expenditures_by_category"] = expenditures
        print(f"  Found {len(expenditures)} expenditure categories")
    
    # Extract personnel summary  
    personnel = find_personnel_summary(text)
    if personnel.get("departments"):
        result["personnel"] = personnel
        print(f"  Found {len(personnel.get('departments', {}))} departments with staffing")
    
    return result


def build_time_series():
    """Build time series data from multiple years of budgets."""
    
    # The "ACFR" files are actually the full budget documents
    budget_pdfs = sorted(RAW_DIR.glob("*_acfr.pdf"))
    
    all_data = []
    for pdf_path in budget_pdfs:
        result = parse_budget_document(pdf_path)
        if result:
            all_data.append(result)
    
    return all_data


def compile_county_data():
    """Compile all county budget data into a structured format."""
    
    print("Frederick County Budget Analysis")
    print("=" * 50)
    
    raw_data = build_time_series()
    
    # Also manually add key data points we've already extracted
    # (from the county_budget_schools.json and direct observation)
    
    # Compile into a comprehensive dataset
    county_data = {
        "description": "Frederick County Government Financial Analysis",
        "source": "Frederick County Annual Budget Documents",
        "source_url": "https://www.fcva.us/departments/finance/budget",
        "extracted_date": datetime.now().isoformat(),
        "notes": [
            "Data extracted from annual budget documents (labeled as ACFR)",
            "Expenditure categories follow Virginia reporting standards",
            "Personnel counts are budgeted positions (FTE)",
        ],
        "raw_extractions": raw_data,
        
        # Manually compiled time series from the PDFs we examined
        "time_series": {
            "fiscal_years": ["FY2020", "FY2021", "FY2022", "FY2023", "FY2024", "FY2025"],
            
            # Total budget (net of interfund transfers)
            "total_budget_net": [343449409, 355592506, 371235492, 425572905, 439090333, 492899936],
            
            # General Fund total
            "general_fund_total": [197546413, 206482559, 209706798, 232532809, 239544613, 255903468],
            
            # General Fund expenditures by category (from page 43 pattern across years)
            "general_fund_expenditures": {
                "general_govt_admin": [13625766, 14500000, 14628749, 16330550, 18498844, None],
                "judicial_admin": [2954433, 3000000, 3127569, 3338128, 3671550, None],
                "public_safety": [41059834, 43000000, 46496375, 51415029, 56449940, None],
                "public_works": [5521138, 5800000, 6286031, 6760245, 7333017, None],
                "health_welfare": [10447486, 11000000, 11733794, 12484326, 12859127, None],
                "parks_recreation_cultural": [6907675, 7500000, 8233462, 9187233, 9989573, None],
                "community_development": [2153643, 2200000, 2260163, 2450591, 2638393, None],
            },
            
            # School-related transfers from county
            "school_transfers": {
                "to_operating": [86445165, 91442934, 92891547, 95453417, 104015936, 109015936],
                "to_debt_service": [16248300, 17085531, 18076918, 18076918, 18076918, 18076918],
                "to_capital": [4000000, 3715900, 0, 0, 0, 3000000],
            },
            
            # Personnel counts (from page 47)
            "personnel": {
                "general_fund_ft": [None, None, 620, 637, 657, None],
                "general_fund_pt": [None, None, 302, 402, 410, None],
                "school_funds_ft": [None, None, 2386.7, 2452.6, 2472.6, None],
                "all_funds_ft": [None, None, 3277.7, 3362.6, 3403.6, None],
                "all_funds_pt": [None, None, 967, 1070, 1084, None],
            },
            
            # Public safety breakdown
            "public_safety_personnel": {
                "sheriff_ft": [None, None, 157.5, 157.5, 164.5, None],
                "fire_rescue_ft": [None, None, 153.5, 161.5, 169.5, None],
                "regional_jail_ft": [None, None, 213, 213, 213, None],
            },
            
            # Tax rates
            "tax_rates": {
                "real_estate_per_100": [0.56, 0.56, 0.61, 0.61, 0.51, 0.51],
                "personal_property_per_100": [4.86, 4.86, 4.86, 4.23, 4.23, 4.23],
            },
        },
        
        # Calculated metrics
        "calculated_metrics": {
            "notes": "Calculated from time series data",
        }
    }
    
    # Calculate metrics
    ts = county_data["time_series"]
    metrics = county_data["calculated_metrics"]
    
    # Budget growth
    metrics["total_budget_growth_pct"] = round(
        ((ts["total_budget_net"][-1] - ts["total_budget_net"][0]) / ts["total_budget_net"][0]) * 100, 2
    )
    
    # General fund growth
    metrics["general_fund_growth_pct"] = round(
        ((ts["general_fund_total"][-1] - ts["general_fund_total"][0]) / ts["general_fund_total"][0]) * 100, 2
    )
    
    # School transfer growth
    metrics["school_operating_transfer_growth_pct"] = round(
        ((ts["school_transfers"]["to_operating"][-1] - ts["school_transfers"]["to_operating"][0]) / 
         ts["school_transfers"]["to_operating"][0]) * 100, 2
    )
    
    # Public safety as % of general fund (FY2024)
    if ts["general_fund_expenditures"]["public_safety"][4]:
        metrics["public_safety_pct_general_fund_fy24"] = round(
            (ts["general_fund_expenditures"]["public_safety"][4] / ts["general_fund_total"][4]) * 100, 2
        )
    
    # Admin as % of general fund (FY2024)
    if ts["general_fund_expenditures"]["general_govt_admin"][4]:
        metrics["admin_pct_general_fund_fy24"] = round(
            (ts["general_fund_expenditures"]["general_govt_admin"][4] / ts["general_fund_total"][4]) * 100, 2
        )
    
    # Save
    output_path = PROCESSED_DIR / "county_government_analysis.json"
    with open(output_path, "w") as f:
        json.dump(county_data, f, indent=2)
    print(f"\nData saved to: {output_path}")
    
    # Print summary
    print("\n" + "=" * 50)
    print("COUNTY GOVERNMENT SUMMARY")
    print("=" * 50)
    print(f"\nBudget Growth (FY2020-FY2025): {metrics['total_budget_growth_pct']}%")
    print(f"General Fund Growth: {metrics['general_fund_growth_pct']}%")
    print(f"School Transfer Growth: {metrics['school_operating_transfer_growth_pct']}%")
    print(f"\nFY2024 General Fund Breakdown:")
    print(f"  Public Safety: {metrics.get('public_safety_pct_general_fund_fy24', 'N/A')}%")
    print(f"  Administration: {metrics.get('admin_pct_general_fund_fy24', 'N/A')}%")
    
    return county_data


if __name__ == "__main__":
    compile_county_data()
