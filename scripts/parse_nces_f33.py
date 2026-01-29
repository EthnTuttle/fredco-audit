#!/usr/bin/env python3
"""
Parse NCES F-33 School District Finance Survey data for Virginia districts.
Extracts financial data for Frederick County and peer districts.
"""

import csv
import json
import os
from pathlib import Path

# Target districts with NCES IDs
DISTRICTS = {
    "5101470": {"name": "Frederick County", "vdoe_code": "069"},
    "5100870": {"name": "Clarke County", "vdoe_code": "043"},
    "5101320": {"name": "Fauquier County", "vdoe_code": "061"},
    "5103510": {"name": "Shenandoah County", "vdoe_code": "171"},
    "5103870": {"name": "Warren County", "vdoe_code": "187"},
    "5102250": {"name": "Loudoun County", "vdoe_code": "107"},
}

# Fields to extract (use header names for lookup)
FIELDS_TO_EXTRACT = [
    "V33",       # Fall Membership
    "TOTALREV",  # Total Revenue
    "TFEDREV",   # Total Federal Revenue
    "TSTREV",    # Total State Revenue
    "TLOCREV",   # Total Local Revenue
    "TOTALEXP",  # Total Expenditures
    "TCURELSC",  # Total Current Elementary/Secondary
    "TCURINST",  # Total Current Instruction
    "TCURSSVC",  # Total Current Support Services
    "E17",       # Support Services - Pupils
    "E07",       # Support Services - Instructional Staff
    "E08",       # Support Services - General Administration
    "E09",       # Support Services - School Administration
    "TCUROTH",   # Total Current Other
    "E11",       # Operations and Maintenance
    "TNONELSE",  # Total Non-Elementary/Secondary
    "TCAPOUT",   # Total Capital Outlay
]


def parse_value(val):
    """Parse numeric value, handling missing data codes."""
    if val in ["-1", "-2", "-3", "-9", "M", "N", "R", ""]:
        return None
    try:
        return int(val)
    except ValueError:
        try:
            return float(val)
        except ValueError:
            return val


def extract_district_data(filepath, fiscal_year):
    """Extract financial data for target districts from F-33 file."""
    results = []
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f, delimiter='\t')
        header = next(reader)
        
        # Build column index from header
        col_idx = {col: i for i, col in enumerate(header)}
        
        for row in reader:
            if len(row) < 10:
                continue
            leaid = row[col_idx.get("LEAID", 0)]
            if leaid in DISTRICTS:
                district_info = DISTRICTS[leaid]
                
                data = {
                    "fiscal_year": f"FY20{fiscal_year}",
                    "school_year": f"20{fiscal_year-1}-{fiscal_year}",
                    "nces_id": leaid,
                    "vdoe_code": district_info["vdoe_code"],
                    "division_name": district_info["name"],
                    "source": "NCES F-33",
                    "source_file": os.path.basename(filepath),
                }
                
                # Extract key fields using header-based lookup
                def get_field(name):
                    if name in col_idx and col_idx[name] < len(row):
                        return parse_value(row[col_idx[name]])
                    return None
                
                try:
                    data["enrollment"] = get_field("V33")
                    data["total_revenue"] = get_field("TOTALREV")
                    data["federal_revenue"] = get_field("TFEDREV")
                    data["state_revenue"] = get_field("TSTREV")
                    data["local_revenue"] = get_field("TLOCREV")
                    data["total_expenditures"] = get_field("TOTALEXP")
                    data["current_expenditures"] = get_field("TCURELSC")
                    data["instruction_expenditures"] = get_field("TCURINST")
                    data["support_services"] = get_field("TCURSSVC")
                    data["pupil_support"] = get_field("E17")
                    data["instructional_staff_support"] = get_field("E07")
                    data["general_administration"] = get_field("E08")
                    data["school_administration"] = get_field("E09")
                    data["other_current"] = get_field("TCUROTH")
                    data["operations_maintenance"] = get_field("E11")
                    data["non_elementary_secondary"] = get_field("TNONELSE")
                    data["capital_outlay"] = get_field("TCAPOUT")
                    
                    # Calculate derived metrics
                    if data["total_expenditures"] and data["enrollment"]:
                        data["per_pupil_total"] = round(data["total_expenditures"] / data["enrollment"], 2)
                    if data["instruction_expenditures"] and data["enrollment"]:
                        data["per_pupil_instruction"] = round(data["instruction_expenditures"] / data["enrollment"], 2)
                    if data["general_administration"] and data["school_administration"] and data["total_expenditures"]:
                        total_admin = data["general_administration"] + data["school_administration"]
                        data["total_administration"] = total_admin
                        data["admin_pct"] = round(total_admin / data["total_expenditures"] * 100, 2)
                        if data["enrollment"]:
                            data["per_pupil_admin"] = round(total_admin / data["enrollment"], 2)
                    if data["instruction_expenditures"] and data["total_expenditures"]:
                        data["instruction_pct"] = round(data["instruction_expenditures"] / data["total_expenditures"] * 100, 2)
                        
                except (IndexError, TypeError) as e:
                    print(f"Warning: Error parsing {leaid} in FY{fiscal_year}: {e}")
                
                results.append(data)
    
    return results


def main():
    base_dir = Path(__file__).parent.parent
    raw_dir = base_dir / "data" / "raw" / "nces" / "historical"
    output_dir = base_dir / "data" / "processed" / "nces"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    all_data = []
    
    # Process each fiscal year
    files = {
        19: "sdf19_1a.txt",
        20: "sdf20_1a.txt",
        21: "sdf21_1a.txt",
        22: "sdf22_1a.txt",
    }
    
    for fy, filename in files.items():
        filepath = raw_dir / filename
        if filepath.exists():
            print(f"Processing FY20{fy} ({filename})...")
            data = extract_district_data(filepath, fy)
            all_data.extend(data)
            print(f"  Found {len(data)} districts")
        else:
            print(f"File not found: {filepath}")
    
    # Save combined data
    output_file = output_dir / "f33_virginia_districts.json"
    with open(output_file, 'w') as f:
        json.dump(all_data, f, indent=2)
    print(f"\nSaved combined data to {output_file}")
    
    # Also save as CSV for easier analysis
    csv_file = output_dir / "f33_virginia_districts.csv"
    if all_data:
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=all_data[0].keys())
            writer.writeheader()
            writer.writerows(all_data)
        print(f"Saved CSV to {csv_file}")
    
    # Print summary
    print("\n" + "="*60)
    print("NCES F-33 DATA SUMMARY")
    print("="*60)
    
    by_year = {}
    for d in all_data:
        fy = d["fiscal_year"]
        if fy not in by_year:
            by_year[fy] = []
        by_year[fy].append(d)
    
    for fy in sorted(by_year.keys()):
        print(f"\n{fy}:")
        for d in sorted(by_year[fy], key=lambda x: x["division_name"]):
            enroll = d.get("enrollment", "N/A")
            total_exp = d.get("total_expenditures")
            per_pupil = d.get("per_pupil_total")
            admin_pct = d.get("admin_pct")
            inst_pct = d.get("instruction_pct")
            
            if total_exp:
                total_exp_m = f"${total_exp/1e6:.1f}M"
            else:
                total_exp_m = "N/A"
            
            print(f"  {d['division_name']:20} | Enroll: {enroll:>6} | Total: {total_exp_m:>10} | "
                  f"Per-Pupil: ${per_pupil:,.0f}" if per_pupil else f"  {d['division_name']:20} | Data incomplete")
    
    return all_data


if __name__ == "__main__":
    main()
