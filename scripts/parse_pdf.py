#!/usr/bin/env python3
"""
Parse PDF budget documents and extract financial tables.

Usage:
    python scripts/parse_pdf.py --input data/raw/fcps/budgets/ --output data/processed/
    python scripts/parse_pdf.py --input data/raw/fcps/acfr/ --output data/processed/
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber
import pandas as pd

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"


def extract_fiscal_year(text: str) -> str:
    """
    Extract fiscal year from text (e.g., 'FY2024', 'FY 2024', '2023-2024').
    
    Returns fiscal year in format 'FY20XX'.
    """
    # Try FY20XX pattern
    match = re.search(r"FY\s*(\d{4})", text, re.IGNORECASE)
    if match:
        return f"FY{match.group(1)}"
    
    # Try YYYY-YYYY pattern (school year)
    match = re.search(r"(\d{4})\s*[-–]\s*(\d{4})", text)
    if match:
        return f"FY{match.group(2)}"
    
    # Try standalone year
    match = re.search(r"20(\d{2})", text)
    if match:
        return f"FY20{match.group(1)}"
    
    return "Unknown"


def clean_currency(value: str) -> float:
    """
    Convert currency string to float.
    
    Handles formats like '$1,234,567', '1234567', '(1,234)' for negatives.
    """
    if not value or pd.isna(value):
        return 0.0
    
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


def extract_tables_from_pdf(pdf_path: Path) -> list[dict[str, Any]]:
    """
    Extract all tables from a PDF file.
    
    Returns list of dictionaries with table data.
    """
    tables = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"  Processing {pdf_path.name} ({len(pdf.pages)} pages)")
            
            for page_num, page in enumerate(pdf.pages, 1):
                page_tables = page.extract_tables()
                
                for table_idx, table in enumerate(page_tables):
                    if table and len(table) > 1:
                        # Convert to DataFrame for easier processing
                        df = pd.DataFrame(table[1:], columns=table[0])
                        
                        # Clean up column names
                        df.columns = [str(col).strip() if col else f"col_{i}" 
                                     for i, col in enumerate(df.columns)]
                        
                        tables.append({
                            "page": page_num,
                            "table_index": table_idx,
                            "columns": list(df.columns),
                            "rows": len(df),
                            "data": df.to_dict(orient="records"),
                        })
    
    except Exception as e:
        print(f"  Error processing {pdf_path.name}: {e}")
    
    return tables


def identify_expenditure_tables(tables: list[dict]) -> list[dict]:
    """
    Identify tables that contain expenditure data.
    
    Looks for keywords like 'expenditure', 'instruction', 'administration'.
    """
    expenditure_tables = []
    
    keywords = [
        "expenditure", "expense", "spending",
        "instruction", "administration", "operation",
        "transportation", "facilities", "debt",
        "total", "budget", "actual"
    ]
    
    for table in tables:
        # Check columns for keywords
        col_text = " ".join(table["columns"]).lower()
        
        # Check first few rows for keywords
        row_text = ""
        for row in table["data"][:5]:
            row_text += " ".join(str(v) for v in row.values()).lower()
        
        combined_text = col_text + " " + row_text
        
        # Count keyword matches
        matches = sum(1 for kw in keywords if kw in combined_text)
        
        if matches >= 2:
            table["keyword_matches"] = matches
            expenditure_tables.append(table)
    
    return sorted(expenditure_tables, key=lambda x: x.get("keyword_matches", 0), reverse=True)


def parse_expenditure_table(table: dict) -> dict[str, Any]:
    """
    Parse an expenditure table into structured data.
    
    Returns dictionary with categorized expenditure amounts.
    """
    expenditures = {
        "instruction": 0,
        "administration": 0,
        "attendance_health": 0,
        "pupil_transportation": 0,
        "operations_maintenance": 0,
        "facilities": 0,
        "debt_service": 0,
        "technology": 0,
        "other": 0,
        "total": 0,
    }
    
    # Category keywords mapping
    category_patterns = {
        "instruction": r"instruction|teaching|classroom",
        "administration": r"admin|executive|board|superintendent|central office",
        "attendance_health": r"attendance|health|nurse|counselor|guidance",
        "pupil_transportation": r"transport|bus",
        "operations_maintenance": r"operation|maintenance|custod|util",
        "facilities": r"facilit|capital|construction|building",
        "debt_service": r"debt|bond|interest|principal",
        "technology": r"technolog|computer|it\s|information",
    }
    
    for row in table["data"]:
        # Try to find category and amount columns
        row_text = " ".join(str(v).lower() for v in row.values())
        
        # Find numeric values in the row
        amounts = []
        for value in row.values():
            amount = clean_currency(str(value))
            if amount > 0:
                amounts.append(amount)
        
        if not amounts:
            continue
        
        # Use the largest amount (often the total or actual)
        amount = max(amounts)
        
        # Categorize based on row text
        categorized = False
        for category, pattern in category_patterns.items():
            if re.search(pattern, row_text, re.IGNORECASE):
                expenditures[category] += amount
                categorized = True
                break
        
        if not categorized and "total" in row_text.lower():
            expenditures["total"] = amount
        elif not categorized and amount > 1000:
            expenditures["other"] += amount
    
    # Calculate total if not found
    if expenditures["total"] == 0:
        expenditures["total"] = sum(v for k, v in expenditures.items() if k != "total")
    
    return expenditures


def process_budget_pdf(pdf_path: Path) -> dict[str, Any]:
    """
    Process a budget PDF and extract structured financial data.
    """
    result = {
        "source_file": pdf_path.name,
        "source_path": str(pdf_path),
        "processed_date": datetime.now().isoformat(),
        "fiscal_year": extract_fiscal_year(pdf_path.name),
        "tables_found": 0,
        "expenditure_tables": 0,
        "expenditures": {},
        "raw_tables": [],
    }
    
    # Extract all tables
    all_tables = extract_tables_from_pdf(pdf_path)
    result["tables_found"] = len(all_tables)
    
    # Identify expenditure tables
    exp_tables = identify_expenditure_tables(all_tables)
    result["expenditure_tables"] = len(exp_tables)
    
    # Parse the best expenditure table
    if exp_tables:
        result["expenditures"] = parse_expenditure_table(exp_tables[0])
    
    # Keep raw tables for manual review
    result["raw_tables"] = all_tables[:10]  # Limit to first 10 tables
    
    return result


def process_acfr_pdf(pdf_path: Path) -> dict[str, Any]:
    """
    Process an Annual Comprehensive Financial Report (ACFR) PDF.
    
    ACFRs have more standardized formats for government financial statements.
    """
    result = {
        "source_file": pdf_path.name,
        "source_path": str(pdf_path),
        "processed_date": datetime.now().isoformat(),
        "fiscal_year": extract_fiscal_year(pdf_path.name),
        "document_type": "ACFR",
        "tables_found": 0,
        "expenditures": {},
        "revenues": {},
        "raw_tables": [],
    }
    
    # Extract all tables
    all_tables = extract_tables_from_pdf(pdf_path)
    result["tables_found"] = len(all_tables)
    
    # Look for Statement of Activities or similar
    for table in all_tables:
        col_text = " ".join(table["columns"]).lower()
        
        if "expenditure" in col_text or "expense" in col_text:
            exp_data = parse_expenditure_table(table)
            if exp_data["total"] > result.get("expenditures", {}).get("total", 0):
                result["expenditures"] = exp_data
        
        if "revenue" in col_text:
            # Similar parsing for revenues
            result["revenues"]["found"] = True
    
    # Keep raw tables for manual review
    result["raw_tables"] = all_tables[:15]
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Parse PDF budget documents and extract financial tables",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input directory containing PDF files"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROCESSED_DIR,
        help="Output directory for JSON files"
    )
    parser.add_argument(
        "--type",
        choices=["budget", "acfr", "auto"],
        default="auto",
        help="Document type (auto-detect by default)"
    )
    
    args = parser.parse_args()
    
    if not args.input.exists():
        print(f"Error: Input directory does not exist: {args.input}")
        sys.exit(1)
    
    args.output.mkdir(parents=True, exist_ok=True)
    
    print("FCPS PDF Parser")
    print("=" * 50)
    print(f"Input directory: {args.input}")
    print(f"Output directory: {args.output}")
    
    # Find all PDF files
    pdf_files = list(args.input.glob("*.pdf")) + list(args.input.glob("*.PDF"))
    
    if not pdf_files:
        print(f"\nNo PDF files found in {args.input}")
        sys.exit(0)
    
    print(f"\nFound {len(pdf_files)} PDF files")
    
    results = []
    
    for pdf_path in pdf_files:
        print(f"\nProcessing: {pdf_path.name}")
        
        # Auto-detect document type
        doc_type = args.type
        if doc_type == "auto":
            if "acfr" in pdf_path.name.lower() or "comprehensive" in pdf_path.name.lower():
                doc_type = "acfr"
            else:
                doc_type = "budget"
        
        # Process based on type
        if doc_type == "acfr":
            result = process_acfr_pdf(pdf_path)
        else:
            result = process_budget_pdf(pdf_path)
        
        results.append(result)
        
        # Save individual result
        output_file = args.output / f"{pdf_path.stem}.json"
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"  Saved: {output_file.name}")
    
    # Save combined results
    combined_output = args.output / "pdf_extraction_results.json"
    with open(combined_output, "w") as f:
        json.dump({
            "processed_date": datetime.now().isoformat(),
            "files_processed": len(results),
            "results": results,
        }, f, indent=2, default=str)
    
    print("\n" + "=" * 50)
    print(f"Processing complete!")
    print(f"Total files processed: {len(results)}")
    print(f"Combined results saved to: {combined_output}")
    print("\nNote: PDF extraction may be imperfect. Review raw_tables")
    print("in the output files and manually verify key figures.")


if __name__ == "__main__":
    main()
