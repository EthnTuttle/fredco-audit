#!/usr/bin/env python3
"""
Extract detailed department-level data from Frederick County budget PDFs.
Outputs granular personnel and expenditure data by department.
"""

import pdfplumber
import re
import json
from datetime import datetime
from pathlib import Path


def parse_personnel_text(text):
    """Parse personnel table from text"""
    personnel = {}
    
    # Pattern for department lines with 6 numbers
    # e.g., "Sheriff 157.5 14 157.5 10 164.5 8"
    pattern = r'^([A-Za-z][A-Za-z/&\s\.\-]+?)\s+(\d+\.?\d*)\s+(\d+)\s+(\d+\.?\d*)\s+(\d+)\s+(\d+\.?\d*)\s+(\d+)\s*$'
    
    for line in text.split('\n'):
        line = line.strip()
        match = re.match(pattern, line)
        if match:
            dept = match.group(1).strip()
            fy_minus2_ft = float(match.group(2))
            fy_minus2_pt = int(match.group(3))
            fy_minus1_ft = float(match.group(4))
            fy_minus1_pt = int(match.group(5))
            fy_current_ft = float(match.group(6))
            fy_current_pt = int(match.group(7))
            
            personnel[dept] = {
                'fy_minus_2': {'full_time': fy_minus2_ft, 'part_time': fy_minus2_pt},
                'fy_minus_1': {'full_time': fy_minus1_ft, 'part_time': fy_minus1_pt},
                'fy_current': {'full_time': fy_current_ft, 'part_time': fy_current_pt},
            }
    
    return personnel


def parse_expenditure_text(text):
    """Parse department expenditure table from text"""
    expenses = {}
    
    # Pattern: Department name followed by 3 dollar amounts
    pattern = r'^([A-Za-z][A-Za-z/&\s\.\-\(\)]+?)\s+\$?([\d,]+)\s+\$?([\d,]+)\s+\$?([\d,]+)\s*$'
    
    for line in text.split('\n'):
        line = line.strip()
        match = re.match(pattern, line)
        if match:
            dept = match.group(1).strip()
            personnel = int(match.group(2).replace(',', ''))
            operating = int(match.group(3).replace(',', ''))
            capital = int(match.group(4).replace(',', ''))
            
            if personnel + operating + capital > 0:
                expenses[dept] = {
                    'personnel': personnel,
                    'operating': operating,
                    'capital': capital,
                    'total': personnel + operating + capital
                }
    
    return expenses


def parse_general_fund_summary(text):
    """Parse General Fund Expenditures summary page"""
    summary = {}
    
    # Pattern for lines like "Administration $14,628,749 $14,022,227 $16,330,550 $18,498,844 7.72%"
    pattern = r'^([A-Za-z][A-Za-z/\s\.\-\(\)&,]+?)\s+\$([\d,]+)\s+\$([\d,]+)\s+\$([\d,]+)\s+\$([\d,]+)\s+([\d\.]+)%'
    
    for line in text.split('\n'):
        line = line.strip()
        match = re.match(pattern, line)
        if match:
            category = match.group(1).strip()
            prior_budgeted = int(match.group(2).replace(',', ''))
            prior_actual = int(match.group(3).replace(',', ''))
            current_budgeted = int(match.group(4).replace(',', ''))
            adopted = int(match.group(5).replace(',', ''))
            pct_of_total = float(match.group(6))
            
            summary[category] = {
                'prior_budgeted': prior_budgeted,
                'prior_actual': prior_actual,
                'current_budgeted': current_budgeted,
                'adopted': adopted,
                'pct_of_total': pct_of_total
            }
    
    return summary


def find_personnel_page(pdf):
    """Find the page with PERSONNEL NEEDS table"""
    for i, page in enumerate(pdf.pages[40:60]):
        text = page.extract_text()
        if text and 'PERSONNEL NEEDS' in text and 'Full-Time' in text and 'Part-Time' in text:
            return i + 40
    return None


def find_expenditure_category_pages(pdf):
    """Find pages with TOTAL EXPENDITURES ALL FUNDS – CATEGORY SUMMARY"""
    pages = []
    for i, page in enumerate(pdf.pages[40:60]):
        text = page.extract_text()
        if text and 'CATEGORY SUMMARY' in text and 'Personnel' in text and 'Operating' in text:
            pages.append(i + 40)
    return pages


def find_general_fund_expenditure_page(pdf):
    """Find the GENERAL FUND EXPENDITURES summary page"""
    for i, page in enumerate(pdf.pages[40:55]):
        text = page.extract_text()
        if text and 'GENERAL FUND EXPENDITURES' in text and 'Administration' in text and 'Public Safety' in text:
            # Make sure it's the summary page not the detail page
            if 'Transfer to School Operating Fund' in text:
                return i + 40
    return None


def extract_fiscal_year(filename):
    """Extract fiscal year from filename like FY2024_acfr.pdf"""
    match = re.search(r'FY(\d{4})', filename)
    if match:
        return f"FY{match.group(1)}"
    return None


def process_budget_pdf(pdf_path):
    """Process a single budget PDF and extract all detailed data"""
    fiscal_year = extract_fiscal_year(pdf_path.name)
    if not fiscal_year:
        return None
    
    result = {
        'fiscal_year': fiscal_year,
        'source_file': pdf_path.name,
        'extracted_date': datetime.now().isoformat(),
        'personnel_by_department': {},
        'expenditures_by_department': {},
        'general_fund_summary': {},
    }
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Find and extract personnel data
            personnel_page = find_personnel_page(pdf)
            if personnel_page:
                text = pdf.pages[personnel_page].extract_text()
                result['personnel_by_department'] = parse_personnel_text(text)
                result['personnel_page'] = personnel_page + 1  # 1-indexed for humans
            
            # Find and extract detailed expenditure data
            expense_pages = find_expenditure_category_pages(pdf)
            if expense_pages:
                combined_text = ""
                for page_num in expense_pages:
                    combined_text += pdf.pages[page_num].extract_text() + "\n"
                result['expenditures_by_department'] = parse_expenditure_text(combined_text)
                result['expenditure_pages'] = [p + 1 for p in expense_pages]
            
            # Find and extract General Fund summary
            gf_page = find_general_fund_expenditure_page(pdf)
            if gf_page:
                text = pdf.pages[gf_page].extract_text()
                result['general_fund_summary'] = parse_general_fund_summary(text)
                result['general_fund_page'] = gf_page + 1
    
    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")
        return None
    
    return result


def main():
    budget_dir = Path("data/raw/fcva/budgets")
    output_path = Path("data/processed/county_department_detail.json")
    
    # Process all ACFR files (comprehensive budget documents)
    acfr_files = sorted(budget_dir.glob("*_acfr.pdf"))
    
    all_data = {
        'description': 'Frederick County Department-Level Budget Analysis',
        'source': 'Frederick County Annual Budget Documents (ACFR)',
        'source_url': 'https://www.fcva.us/departments/finance/budget',
        'extracted_date': datetime.now().isoformat(),
        'fiscal_years': [],
        'by_fiscal_year': {},
    }
    
    for pdf_path in acfr_files:
        print(f"Processing {pdf_path.name}...")
        data = process_budget_pdf(pdf_path)
        if data:
            fy = data['fiscal_year']
            all_data['fiscal_years'].append(fy)
            all_data['by_fiscal_year'][fy] = data
            
            print(f"  - Personnel departments: {len(data['personnel_by_department'])}")
            print(f"  - Expenditure departments: {len(data['expenditures_by_department'])}")
            print(f"  - General Fund categories: {len(data['general_fund_summary'])}")
    
    # Build time series for key departments
    all_data['time_series'] = build_time_series(all_data)
    
    # Save to JSON
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(all_data, f, indent=2)
    
    print(f"\nSaved to {output_path}")
    print(f"Processed {len(all_data['fiscal_years'])} fiscal years: {all_data['fiscal_years']}")


def build_time_series(all_data):
    """Build time series for key departments/categories"""
    
    # Key departments to track
    key_depts = [
        'Sheriff', 'Fire and Rescue', 'Social Services', 'Parks and Recreation',
        'IT/MIS', 'Treasurer', 'Finance', 'Planning and Development',
        'Commonwealth Attorney', 'Public Safety Communications', 'Inspections',
        'Maintenance', 'Animal Shelter', 'Clerk of the Circuit Court',
        'County Administrator', 'County Attorney', 'Human Resources',
    ]
    
    # Key expense categories
    key_categories = [
        'Administration', 'Judicial Administration', 'Public Safety', 
        'Public Works', 'Health/Welfare', 'Parks, Recreation, & Cultural',
        'Community Development', 'Miscellaneous'
    ]
    
    time_series = {
        'fiscal_years': sorted(all_data['fiscal_years']),
        'personnel': {},
        'expenditures': {},
        'general_fund': {},
    }
    
    # Build personnel time series
    for dept in key_depts:
        time_series['personnel'][dept] = {
            'full_time': [],
            'part_time': [],
        }
        
        for fy in time_series['fiscal_years']:
            fy_data = all_data['by_fiscal_year'].get(fy, {})
            personnel = fy_data.get('personnel_by_department', {}).get(dept, {})
            
            # Personnel table shows current FY data in 'fy_current'
            current_data = personnel.get('fy_current', {})
            time_series['personnel'][dept]['full_time'].append(current_data.get('full_time'))
            time_series['personnel'][dept]['part_time'].append(current_data.get('part_time'))
    
    # Build expenditure time series
    for dept in key_depts + ['Sheriff', 'Fire and Rescue', 'Landfill Fund', 'Regional Jail Fund']:
        if dept not in time_series['expenditures']:
            time_series['expenditures'][dept] = {
                'personnel': [],
                'operating': [],
                'capital': [],
                'total': [],
            }
        
        for fy in time_series['fiscal_years']:
            fy_data = all_data['by_fiscal_year'].get(fy, {})
            expenses = fy_data.get('expenditures_by_department', {}).get(dept, {})
            
            time_series['expenditures'][dept]['personnel'].append(expenses.get('personnel'))
            time_series['expenditures'][dept]['operating'].append(expenses.get('operating'))
            time_series['expenditures'][dept]['capital'].append(expenses.get('capital'))
            time_series['expenditures'][dept]['total'].append(expenses.get('total'))
    
    # Build General Fund summary time series
    for cat in key_categories:
        time_series['general_fund'][cat] = {
            'adopted': [],
            'pct_of_total': [],
        }
        
        for fy in time_series['fiscal_years']:
            fy_data = all_data['by_fiscal_year'].get(fy, {})
            gf_summary = fy_data.get('general_fund_summary', {}).get(cat, {})
            
            time_series['general_fund'][cat]['adopted'].append(gf_summary.get('adopted'))
            time_series['general_fund'][cat]['pct_of_total'].append(gf_summary.get('pct_of_total'))
    
    return time_series


if __name__ == '__main__':
    main()
