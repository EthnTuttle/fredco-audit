#!/usr/bin/env python3
"""
Download NCES Common Core of Data for Virginia school districts.

This script downloads enrollment, staffing, and fiscal data from NCES
as an alternative to VDOE data which is blocked by bot protection.
"""

import requests
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

# NCES District IDs for target Virginia districts
# IDs verified from NCES district search by county
DISTRICTS = {
    "5101470": {"name": "Frederick County Public Schools", "vdoe_code": "069"},
    "5100540": {"name": "Clarke County Public Schools", "vdoe_code": "043"},
    "5101440": {"name": "Fauquier County Public Schools", "vdoe_code": "061"},
    "5103510": {"name": "Shenandoah County Public Schools", "vdoe_code": "171"},  # Corrected ID
    "5104080": {"name": "Warren County Public Schools", "vdoe_code": "187"},
    "5102250": {"name": "Loudoun County Public Schools", "vdoe_code": "107"},  # Corrected ID
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

BASE_URL = "https://nces.ed.gov/ccd/districtsearch/district_detail.asp"


def parse_district_html(html: str) -> dict:
    """Parse NCES district detail HTML to extract key data."""
    data = {}
    
    # Basic info
    match = re.search(r'Total Students:</th>\s*<td[^>]*>([0-9,]+)', html)
    if match:
        data['enrollment'] = int(match.group(1).replace(',', ''))
    
    match = re.search(r'Classroom Teachers \(FTE\):</th>\s*<td[^>]*>([0-9,.]+)', html)
    if match:
        data['teachers_fte'] = float(match.group(1).replace(',', ''))
    
    match = re.search(r'Student/Teacher Ratio:</th>\s*<td[^>]*>([0-9.]+)', html)
    if match:
        data['student_teacher_ratio'] = float(match.group(1))
    
    # Staff data
    match = re.search(r'has a staff count of\s*<b[^>]*>\s*([0-9,.]+)', html)
    if match:
        val = match.group(1).replace(',', '').rstrip('.')
        data['total_staff_fte'] = float(val)
    
    # Staff breakdown
    staff_patterns = {
        'instructional_aides': r'Instructional Aides:</th>\s*<td>([0-9,.]+)',
        'instructional_coordinators': r'Instruc\. Coordinators[^<]*</B?></th>\s*<td>([0-9,.]+)',
        'guidance_counselors': r'Total Guidance Counselors:</th>\s*<td>([0-9,.]+)',
        'school_psychologists': r'School Psychologists:</th>\s*<td>([0-9,.]+)',
        'librarians': r'Librarians/Media Specialists:</th>\s*<td>([0-9,.]+)',
        'district_administrators': r'District Administrators:</th>\s*<td>([0-9,.]+)',
        'district_admin_support': r'District Administrative Support:</th>\s*<td>([0-9,.]+)',
        'school_administrators': r'School Administrators:</th>\s*<td>([0-9,.]+)',
        'school_admin_support': r'School Administrative Support:</th>\s*<td>([0-9,.]+)',
    }
    
    data['staff_breakdown'] = {}
    for key, pattern in staff_patterns.items():
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            val = match.group(1).replace(',', '').rstrip('.')
            data['staff_breakdown'][key] = float(val) if '.' in val else int(float(val))
    
    # Revenue data
    revenue_patterns = {
        'total_revenue': r'Total Revenue:</b></font></td>\s*<td[^>]*><font[^>]*>\$([0-9,]+)',
        'federal_revenue': r'Federal:</font></td>\s*<td[^>]*><font[^>]*>\$([0-9,]+)',
        'local_revenue': r'Local:</font></td>\s*<td[^>]*><font[^>]*>\$([0-9,]+)',
        'state_revenue': r'State:</font></td>\s*<td[^>]*><font[^>]*>\$([0-9,]+)',
    }
    
    data['revenue'] = {}
    for key, pattern in revenue_patterns.items():
        match = re.search(pattern, html)
        if match:
            data['revenue'][key] = int(match.group(1).replace(',', ''))
    
    # Expenditure data
    exp_patterns = {
        'total_expenditures': r'Total Expenditures:</b></font></td>\s*<td[^>]*><font[^>]*>\$([0-9,]+)',
        'total_current_expenditures': r'Total Current Expenditures:</b></font></td>\s*<td[^>]*><font[^>]*>\$([0-9,]+)',
        'instructional_expenditures': r'Instructional Expenditures:</font></td>\s*<td[^>]*><font[^>]*>\$([0-9,]+)',
        'student_staff_support': r'Student and Staff Support:</font></td>\s*<td[^>]*><font[^>]*>\$([0-9,]+)',
        'administration': r'Administration:</font></td>\s*<td[^>]*><font[^>]*>\$([0-9,]+)',
        'operations_food_other': r'Operations, Food Service, other:</font></td>\s*<td[^>]*><font[^>]*>\$([0-9,]+)',
        'capital_outlay': r'Total Capital Outlay:</b></font></td>\s*<td[^>]*><font[^>]*>\$([0-9,]+)',
    }
    
    data['expenditures'] = {}
    for key, pattern in exp_patterns.items():
        match = re.search(pattern, html)
        if match:
            data['expenditures'][key] = int(match.group(1).replace(',', ''))
    
    # Per-pupil amounts
    pp_patterns = {
        'total_revenue_pp': r'Total Revenue:</b></font></td>\s*<td[^>]*><font[^>]*>\$[0-9,]+</font></td>\s*<td[^>]*><font[^>]*>\$([0-9,]+)',
        'total_expenditures_pp': r'Total Expenditures:</b></font></td>\s*<td[^>]*><font[^>]*>\$[0-9,]+</font></td>\s*<td[^>]*><font[^>]*>\$([0-9,]+)',
        'instructional_pp': r'Instructional Expenditures:</font></td>\s*<td[^>]*><font[^>]*>\$[0-9,]+</font></td>\s*<td[^>]*><font[^>]*>\$([0-9,]+)',
        'administration_pp': r'Administration:</font></td>\s*<td[^>]*><font[^>]*>\$[0-9,]+</font></td>\s*<td[^>]*><font[^>]*>\$([0-9,]+)',
    }
    
    data['per_pupil'] = {}
    for key, pattern in pp_patterns.items():
        match = re.search(pattern, html)
        if match:
            data['per_pupil'][key] = int(match.group(1).replace(',', ''))
    
    return data


def download_district_data(nces_id: str, district_info: dict) -> dict:
    """Download and parse data for a single district."""
    # Don't specify details param to get all sections (characteristics, staff, fiscal)
    url = f"{BASE_URL}?ID2={nces_id}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        data = parse_district_html(response.text)
        data['nces_id'] = nces_id
        data['district_name'] = district_info['name']
        data['vdoe_division_code'] = district_info['vdoe_code']
        data['source_url'] = url
        data['download_date'] = datetime.now().isoformat()
        data['data_year'] = {
            'directory': '2024-2025',
            'fiscal': '2021-2022'
        }
        
        return data
        
    except Exception as e:
        print(f"Error downloading {district_info['name']}: {e}")
        return None


def main():
    """Download data for all target districts."""
    base_dir = Path(__file__).parent.parent
    output_dir = base_dir / "data" / "raw" / "nces"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    all_data = []
    
    for nces_id, district_info in DISTRICTS.items():
        print(f"Downloading data for {district_info['name']}...")
        data = download_district_data(nces_id, district_info)
        
        if data:
            all_data.append(data)
            
            # Save individual district file
            filename = f"{district_info['name'].lower().replace(' ', '_')}.json"
            with open(output_dir / filename, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"  Saved to {filename}")
        
        time.sleep(1)  # Be polite to the server
    
    # Save combined file
    with open(output_dir / "all_districts.json", 'w') as f:
        json.dump(all_data, f, indent=2)
    print(f"\nSaved combined data to all_districts.json")
    
    # Create metadata
    metadata = {
        "download_date": datetime.now().isoformat(),
        "source": "NCES Common Core of Data",
        "source_url": "https://nces.ed.gov/ccd/districtsearch/",
        "data_years": {
            "directory_data": "2024-2025",
            "fiscal_data": "2021-2022"
        },
        "districts_downloaded": len(all_data),
        "files_created": [
            "all_districts.json"
        ] + [f"{d['name'].lower().replace(' ', '_')}.json" for d in DISTRICTS.values()]
    }
    
    with open(output_dir / "metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    return all_data


if __name__ == "__main__":
    main()
