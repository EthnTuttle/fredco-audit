#!/usr/bin/env python3
"""
Parse Excel files from VDOE and APA sources.

Usage:
    python scripts/parse_excel.py --source vdoe --output data/processed/
    python scripts/parse_excel.py --source apa --output data/processed/
    python scripts/parse_excel.py --all --output data/processed/
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# Division codes for filtering
DIVISION_CODES = {
    "069": "Frederick County",
    "043": "Clarke County",
    "061": "Fauquier County",
    "171": "Shenandoah County",
    "187": "Warren County",
    "107": "Loudoun County",
}

TARGET_DIVISIONS = list(DIVISION_CODES.keys())


def extract_fiscal_year_from_filename(filename: str) -> str:
    """
    Extract fiscal year from filename.
    
    Examples: 'table15_2023-24.xlsm' -> 'FY2024'
    """
    # Try YYYY-YY pattern
    match = re.search(r"(\d{4})-(\d{2})", filename)
    if match:
        year = int(match.group(1))
        return f"FY{year + 1}"
    
    # Try YYYY pattern
    match = re.search(r"20(\d{2})", filename)
    if match:
        return f"FY20{match.group(1)}"
    
    return "Unknown"


def clean_numeric(value: Any) -> float:
    """Convert value to float, handling various formats."""
    if pd.isna(value) or value is None:
        return 0.0
    
    if isinstance(value, (int, float)):
        return float(value)
    
    value = str(value).strip()
    
    # Handle parentheses for negatives
    is_negative = "(" in value and ")" in value
    
    # Remove currency symbols, commas, spaces, parentheses
    cleaned = re.sub(r"[$,\s()%]", "", value)
    
    try:
        result = float(cleaned)
        return -result if is_negative else result
    except ValueError:
        return 0.0


def find_division_column(df: pd.DataFrame) -> str:
    """Find the column containing division codes or names."""
    possible_names = [
        "division", "div", "code", "division code", "div code",
        "division number", "division name", "school division",
        "locality", "county"
    ]
    
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if any(name in col_lower for name in possible_names):
            return col
    
    # Check first column
    if len(df.columns) > 0:
        first_col = df.columns[0]
        # Check if it contains division codes
        sample = df[first_col].astype(str).head(20)
        if sample.str.match(r"^\d{3}$").any():
            return first_col
    
    return ""


def filter_to_target_divisions(df: pd.DataFrame) -> pd.DataFrame:
    """Filter dataframe to only include target divisions."""
    div_col = find_division_column(df)
    
    if not div_col:
        print("  Warning: Could not identify division column")
        return df
    
    # Try matching by code
    df_filtered = df[df[div_col].astype(str).str.strip().isin(TARGET_DIVISIONS)]
    
    if len(df_filtered) > 0:
        return df_filtered
    
    # Try matching by name
    division_names = [name.lower() for name in DIVISION_CODES.values()]
    df_filtered = df[df[div_col].astype(str).str.lower().str.strip().apply(
        lambda x: any(name in x for name in division_names)
    )]
    
    return df_filtered


def parse_vdoe_table3(file_path: Path) -> dict[str, Any]:
    """
    Parse VDOE Table 3 (Enrollment/ADM data).
    
    Returns structured enrollment data for target divisions.
    """
    result = {
        "source_file": file_path.name,
        "fiscal_year": extract_fiscal_year_from_filename(file_path.name),
        "table": "Table 3",
        "description": "Enrollment (Average Daily Membership)",
        "processed_date": datetime.now().isoformat(),
        "data": [],
    }
    
    try:
        # Read Excel file - try multiple sheets
        xl = pd.ExcelFile(file_path, engine="openpyxl")
        
        for sheet_name in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=sheet_name, header=None)
            
            # Find header row (look for 'division' or 'ADM')
            header_row = None
            for idx, row in df.iterrows():
                row_text = " ".join(str(v).lower() for v in row.values if pd.notna(v))
                if "division" in row_text or "adm" in row_text or "enrollment" in row_text:
                    header_row = idx
                    break
            
            if header_row is not None:
                df = pd.read_excel(xl, sheet_name=sheet_name, header=header_row)
                df_filtered = filter_to_target_divisions(df)
                
                if len(df_filtered) > 0:
                    for _, row in df_filtered.iterrows():
                        div_col = find_division_column(df_filtered)
                        div_code = str(row[div_col]).strip()[:3] if div_col else "Unknown"
                        
                        record = {
                            "division_code": div_code,
                            "division_name": DIVISION_CODES.get(div_code, "Unknown"),
                            "enrollment": {},
                        }
                        
                        # Look for ADM columns
                        for col in df_filtered.columns:
                            col_lower = str(col).lower()
                            if "adm" in col_lower or "membership" in col_lower or "enrollment" in col_lower:
                                if "total" in col_lower or "all" in col_lower:
                                    record["enrollment"]["adm_total"] = clean_numeric(row[col])
                                elif "elementary" in col_lower or "elem" in col_lower:
                                    record["enrollment"]["adm_elementary"] = clean_numeric(row[col])
                                elif "middle" in col_lower:
                                    record["enrollment"]["adm_middle"] = clean_numeric(row[col])
                                elif "high" in col_lower or "secondary" in col_lower:
                                    record["enrollment"]["adm_high"] = clean_numeric(row[col])
                                else:
                                    record["enrollment"]["adm"] = clean_numeric(row[col])
                        
                        if record["enrollment"]:
                            result["data"].append(record)
    
    except Exception as e:
        result["error"] = str(e)
        print(f"  Error parsing {file_path.name}: {e}")
    
    return result


def parse_vdoe_table13(file_path: Path) -> dict[str, Any]:
    """
    Parse VDOE Table 13 (Instructional Staff Counts and Salaries).
    
    Returns structured staffing data for target divisions.
    """
    result = {
        "source_file": file_path.name,
        "fiscal_year": extract_fiscal_year_from_filename(file_path.name),
        "table": "Table 13",
        "description": "Instructional Staff Counts and Salaries",
        "processed_date": datetime.now().isoformat(),
        "data": [],
    }
    
    try:
        xl = pd.ExcelFile(file_path, engine="openpyxl")
        
        for sheet_name in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=sheet_name, header=None)
            
            # Find header row
            header_row = None
            for idx, row in df.iterrows():
                row_text = " ".join(str(v).lower() for v in row.values if pd.notna(v))
                if "division" in row_text and ("teacher" in row_text or "salary" in row_text or "staff" in row_text):
                    header_row = idx
                    break
            
            if header_row is not None:
                df = pd.read_excel(xl, sheet_name=sheet_name, header=header_row)
                df_filtered = filter_to_target_divisions(df)
                
                if len(df_filtered) > 0:
                    for _, row in df_filtered.iterrows():
                        div_col = find_division_column(df_filtered)
                        div_code = str(row[div_col]).strip()[:3] if div_col else "Unknown"
                        
                        record = {
                            "division_code": div_code,
                            "division_name": DIVISION_CODES.get(div_code, "Unknown"),
                            "staffing": {},
                            "salaries": {},
                        }
                        
                        for col in df_filtered.columns:
                            col_lower = str(col).lower()
                            value = clean_numeric(row[col])
                            
                            # Staff counts
                            if "teacher" in col_lower and "number" in col_lower:
                                record["staffing"]["teachers"] = value
                            elif "admin" in col_lower and "number" in col_lower:
                                record["staffing"]["administrators"] = value
                            elif "aide" in col_lower or "paraprofessional" in col_lower:
                                record["staffing"]["instructional_aides"] = value
                            elif "counselor" in col_lower:
                                record["staffing"]["counselors"] = value
                            elif "librarian" in col_lower:
                                record["staffing"]["librarians"] = value
                            
                            # Salaries
                            elif "salary" in col_lower:
                                if "teacher" in col_lower:
                                    record["salaries"]["avg_teacher_salary"] = value
                                elif "admin" in col_lower:
                                    record["salaries"]["avg_admin_salary"] = value
                        
                        if record["staffing"] or record["salaries"]:
                            result["data"].append(record)
    
    except Exception as e:
        result["error"] = str(e)
        print(f"  Error parsing {file_path.name}: {e}")
    
    return result


def parse_vdoe_table15(file_path: Path) -> dict[str, Any]:
    """
    Parse VDOE Table 15 (Per Pupil Expenditures by Source).
    
    Returns structured expenditure data for target divisions.
    """
    result = {
        "source_file": file_path.name,
        "fiscal_year": extract_fiscal_year_from_filename(file_path.name),
        "table": "Table 15",
        "description": "Sources of Financial Support and Per Pupil Expenditures",
        "processed_date": datetime.now().isoformat(),
        "data": [],
    }
    
    try:
        xl = pd.ExcelFile(file_path, engine="openpyxl")
        
        for sheet_name in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=sheet_name, header=None)
            
            # Find header row
            header_row = None
            for idx, row in df.iterrows():
                row_text = " ".join(str(v).lower() for v in row.values if pd.notna(v))
                if "division" in row_text and ("expenditure" in row_text or "per pupil" in row_text):
                    header_row = idx
                    break
            
            if header_row is not None:
                df = pd.read_excel(xl, sheet_name=sheet_name, header=header_row)
                df_filtered = filter_to_target_divisions(df)
                
                if len(df_filtered) > 0:
                    for _, row in df_filtered.iterrows():
                        div_col = find_division_column(df_filtered)
                        div_code = str(row[div_col]).strip()[:3] if div_col else "Unknown"
                        
                        record = {
                            "division_code": div_code,
                            "division_name": DIVISION_CODES.get(div_code, "Unknown"),
                            "expenditures": {},
                            "per_pupil": {},
                            "revenue_sources": {},
                        }
                        
                        for col in df_filtered.columns:
                            col_lower = str(col).lower()
                            value = clean_numeric(row[col])
                            
                            # Per pupil expenditures
                            if "per pupil" in col_lower:
                                if "total" in col_lower:
                                    record["per_pupil"]["total"] = value
                                elif "instruction" in col_lower:
                                    record["per_pupil"]["instruction"] = value
                                elif "admin" in col_lower:
                                    record["per_pupil"]["administration"] = value
                                elif "operation" in col_lower:
                                    record["per_pupil"]["operations"] = value
                                elif "transport" in col_lower:
                                    record["per_pupil"]["transportation"] = value
                                else:
                                    record["per_pupil"]["other"] = value
                            
                            # Revenue sources
                            elif "state" in col_lower and ("revenue" in col_lower or "fund" in col_lower):
                                record["revenue_sources"]["state"] = value
                            elif "local" in col_lower and ("revenue" in col_lower or "fund" in col_lower):
                                record["revenue_sources"]["local"] = value
                            elif "federal" in col_lower and ("revenue" in col_lower or "fund" in col_lower):
                                record["revenue_sources"]["federal"] = value
                            
                            # Total expenditures
                            elif "total" in col_lower and "expenditure" in col_lower:
                                record["expenditures"]["total"] = value
                        
                        if record["per_pupil"] or record["expenditures"]:
                            result["data"].append(record)
    
    except Exception as e:
        result["error"] = str(e)
        print(f"  Error parsing {file_path.name}: {e}")
    
    return result


def parse_apa_comparative(file_path: Path) -> dict[str, Any]:
    """
    Parse Virginia APA Comparative Report.
    
    Focuses on Exhibit C-6 (Education expenditures by category).
    """
    result = {
        "source_file": file_path.name,
        "description": "Virginia APA Comparative Report - Education Expenditures",
        "processed_date": datetime.now().isoformat(),
        "exhibits": [],
    }
    
    try:
        xl = pd.ExcelFile(file_path, engine="openpyxl")
        
        # Look for C-6 sheet or education-related sheets
        target_sheets = []
        for sheet_name in xl.sheet_names:
            sheet_lower = sheet_name.lower()
            if "c-6" in sheet_lower or "education" in sheet_lower or "school" in sheet_lower:
                target_sheets.append(sheet_name)
        
        # If no specific sheets found, process all
        if not target_sheets:
            target_sheets = xl.sheet_names
        
        for sheet_name in target_sheets:
            df = pd.read_excel(xl, sheet_name=sheet_name, header=None)
            
            # Find header row
            header_row = None
            for idx, row in df.iterrows():
                row_text = " ".join(str(v).lower() for v in row.values if pd.notna(v))
                if any(kw in row_text for kw in ["locality", "county", "city", "expenditure"]):
                    header_row = idx
                    break
            
            if header_row is not None:
                df = pd.read_excel(xl, sheet_name=sheet_name, header=header_row)
                
                # Filter for Frederick County and peers
                locality_col = None
                for col in df.columns:
                    if any(name in str(col).lower() for name in ["locality", "county", "city", "jurisdiction"]):
                        locality_col = col
                        break
                
                if locality_col:
                    division_names = [name.lower() for name in DIVISION_CODES.values()]
                    df_filtered = df[df[locality_col].astype(str).str.lower().str.strip().apply(
                        lambda x: any(name.split()[0] in x for name in division_names)
                    )]
                    
                    if len(df_filtered) > 0:
                        exhibit_data = {
                            "sheet_name": sheet_name,
                            "records": df_filtered.to_dict(orient="records"),
                        }
                        result["exhibits"].append(exhibit_data)
    
    except Exception as e:
        result["error"] = str(e)
        print(f"  Error parsing {file_path.name}: {e}")
    
    return result


def process_vdoe_files(output_dir: Path) -> list[dict]:
    """Process all VDOE table files."""
    results = []
    vdoe_dir = RAW_DIR / "vdoe"
    
    # Process Table 3 (Enrollment)
    table3_dir = vdoe_dir / "table-3"
    if table3_dir.exists():
        print("\nProcessing VDOE Table 3 (Enrollment)...")
        for file_path in table3_dir.glob("*.xls*"):
            print(f"  Processing: {file_path.name}")
            result = parse_vdoe_table3(file_path)
            results.append(result)
    
    # Process Table 13 (Staffing)
    table13_dir = vdoe_dir / "table-13"
    if table13_dir.exists():
        print("\nProcessing VDOE Table 13 (Staffing)...")
        for file_path in table13_dir.glob("*.xls*"):
            print(f"  Processing: {file_path.name}")
            result = parse_vdoe_table13(file_path)
            results.append(result)
    
    # Process Table 15 (Per Pupil Expenditures)
    table15_dir = vdoe_dir / "table-15"
    if table15_dir.exists():
        print("\nProcessing VDOE Table 15 (Per Pupil Expenditures)...")
        for file_path in table15_dir.glob("*.xls*"):
            print(f"  Processing: {file_path.name}")
            result = parse_vdoe_table15(file_path)
            results.append(result)
    
    # Save combined VDOE results
    if results:
        output_file = output_dir / "vdoe_data.json"
        with open(output_file, "w") as f:
            json.dump({
                "processed_date": datetime.now().isoformat(),
                "source": "VDOE Superintendent's Annual Report",
                "tables": results,
            }, f, indent=2)
        print(f"\nSaved: {output_file}")
    
    return results


def process_apa_files(output_dir: Path) -> list[dict]:
    """Process APA comparative report files."""
    results = []
    apa_dir = RAW_DIR / "apa" / "comparative"
    
    if apa_dir.exists():
        print("\nProcessing APA Comparative Report...")
        for file_path in apa_dir.glob("*.xls*"):
            print(f"  Processing: {file_path.name}")
            result = parse_apa_comparative(file_path)
            results.append(result)
    
    # Save APA results
    if results:
        output_file = output_dir / "apa_data.json"
        with open(output_file, "w") as f:
            json.dump({
                "processed_date": datetime.now().isoformat(),
                "source": "Virginia Auditor of Public Accounts",
                "reports": results,
            }, f, indent=2)
        print(f"\nSaved: {output_file}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Parse Excel files from VDOE and APA sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--source",
        choices=["vdoe", "apa"],
        help="Process specific source"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all sources"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROCESSED_DIR,
        help="Output directory for JSON files"
    )
    
    args = parser.parse_args()
    
    if not args.all and not args.source:
        parser.print_help()
        sys.exit(1)
    
    args.output.mkdir(parents=True, exist_ok=True)
    
    print("FCPS Excel Parser")
    print("=" * 50)
    print(f"Target divisions: {', '.join(DIVISION_CODES.values())}")
    print(f"Output directory: {args.output}")
    
    if args.all or args.source == "vdoe":
        process_vdoe_files(args.output)
    
    if args.all or args.source == "apa":
        process_apa_files(args.output)
    
    print("\n" + "=" * 50)
    print("Processing complete!")
    print("\nNote: Excel parsing may need adjustment based on actual")
    print("file formats. Review output and adjust parsers as needed.")


if __name__ == "__main__":
    main()
