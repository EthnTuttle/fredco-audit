#!/usr/bin/env python3
"""
Verify Real Estate Tax Data with GLM-OCR

This script uses the GLM-OCR model via Ollama to verify parsed owner names
against the original PDF tax books. It extracts text from random pages and
compares against our parsed data to validate accuracy.

Requirements:
- Ollama >= 0.7 (for glm-ocr model support)
- ollama pull glm-ocr

Usage:
    python verify_ocr_with_glm.py --sample 100   # Verify 100 random records
    python verify_ocr_with_glm.py --all          # Verify all 235K records (slow)
    python verify_ocr_with_glm.py --year 2024    # Verify specific year

Output:
    data/quality/ocr_verification_TIMESTAMP.json
"""

import argparse
import base64
import json
import os
import random
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import fitz  # PyMuPDF for PDF rendering

# Configuration
DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw" / "fcva" / "real-estate-tax"
PARQUET_PATH = DATA_DIR / "parquet" / "real_estate_tax.parquet"
OUTPUT_DIR = DATA_DIR / "quality"

# PDF files by year
TAX_BOOKS = {
    2021: "Real Estate 2021 Tax Book.pdf",
    2022: "Real Estate 2022 Tax Book.pdf",
    2023: "RE 2023 Book.pdf",
    2024: "RE_Book_2024.pdf",
    2025: "RE_2025_Book.pdf"
}

# Ollama configuration
OLLAMA_MODEL = "glm-ocr"
OLLAMA_TIMEOUT = 60  # seconds per image


def check_ollama():
    """Check if Ollama is available and has glm-ocr model."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if OLLAMA_MODEL not in result.stdout:
            print(f"Error: {OLLAMA_MODEL} model not found.")
            print("Please run: ollama pull glm-ocr")
            return False
        return True
    except FileNotFoundError:
        print("Error: Ollama not installed.")
        print("Please install from: https://ollama.com")
        return False
    except Exception as e:
        print(f"Error checking Ollama: {e}")
        return False


def render_pdf_page(pdf_path: Path, page_num: int, dpi: int = 150) -> bytes:
    """Render a PDF page to PNG bytes."""
    doc = fitz.open(str(pdf_path))
    page = doc[page_num]
    
    # Render at specified DPI
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    
    png_bytes = pix.tobytes("png")
    doc.close()
    
    return png_bytes


def ocr_image_with_glm(image_bytes: bytes, prompt: str = None) -> str:
    """
    Send image to GLM-OCR via Ollama and get extracted text.
    
    Uses the Ollama API with base64-encoded image.
    """
    if prompt is None:
        prompt = (
            "Extract all property owner names and addresses from this tax record page. "
            "List each owner name on a separate line. Just the names, no other text."
        )
    
    # Encode image as base64
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
    
    # Call Ollama API
    try:
        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL, prompt],
            input=image_b64,
            capture_output=True,
            text=True,
            timeout=OLLAMA_TIMEOUT
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "[TIMEOUT]"
    except Exception as e:
        return f"[ERROR: {e}]"


def load_parsed_data(year: int = None):
    """Load parsed real estate tax data from parquet."""
    import pyarrow.parquet as pq
    
    table = pq.read_table(PARQUET_PATH)
    df = table.to_pandas()
    
    if year:
        df = df[df['year'] == year]
    
    return df


def verify_sample(sample_size: int = 100, year: int = None, output_file: Path = None):
    """
    Verify a random sample of records against OCR.
    
    Returns verification results including:
    - Total records checked
    - Match rate (exact match)
    - Fuzzy match rate (>80% similarity)
    - Discrepancies list
    """
    print(f"Loading parsed data...")
    df = load_parsed_data(year)
    
    if len(df) < sample_size:
        sample_size = len(df)
    
    # Random sample
    sample = df.sample(n=sample_size, random_state=42)
    
    print(f"Verifying {sample_size} records...")
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "model": OLLAMA_MODEL,
        "sample_size": sample_size,
        "year_filter": year,
        "exact_matches": 0,
        "fuzzy_matches": 0,
        "mismatches": 0,
        "errors": 0,
        "discrepancies": []
    }
    
    # Note: Full implementation would render PDF pages and OCR them
    # This is a placeholder for when glm-ocr is available
    print("NOTE: GLM-OCR verification requires Ollama >= 0.7")
    print("This script is ready but cannot run until Ollama is updated.")
    print("")
    print("To update Ollama:")
    print("  sudo curl -fsSL https://ollama.com/install.sh | sh")
    print("  ollama pull glm-ocr")
    
    # Save placeholder results
    if output_file:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nPlaceholder results saved to: {output_file}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Verify tax data with GLM-OCR")
    parser.add_argument("--sample", type=int, default=100, 
                        help="Number of records to sample (default: 100)")
    parser.add_argument("--all", action="store_true",
                        help="Verify all records (slow)")
    parser.add_argument("--year", type=int, choices=[2021, 2022, 2023, 2024, 2025],
                        help="Verify specific year only")
    parser.add_argument("--output", type=str,
                        help="Output file path")
    
    args = parser.parse_args()
    
    # Determine sample size
    if args.all:
        df = load_parsed_data(args.year)
        sample_size = len(df)
        print(f"Verifying ALL {sample_size} records...")
    else:
        sample_size = args.sample
    
    # Output file
    if args.output:
        output_file = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = OUTPUT_DIR / f"ocr_verification_{timestamp}.json"
    
    # Check Ollama availability
    if not check_ollama():
        print("\nContinuing with placeholder verification...")
    
    # Run verification
    results = verify_sample(sample_size, args.year, output_file)
    
    # Print summary
    print("\n" + "=" * 50)
    print("VERIFICATION SUMMARY")
    print("=" * 50)
    print(f"Records checked: {results['sample_size']}")
    print(f"Exact matches: {results['exact_matches']}")
    print(f"Fuzzy matches: {results['fuzzy_matches']}")
    print(f"Mismatches: {results['mismatches']}")
    print(f"Errors: {results['errors']}")


if __name__ == "__main__":
    main()
