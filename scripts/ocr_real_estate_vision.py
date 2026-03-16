#!/usr/bin/env python3
"""
Vision-based OCR for Frederick County Real Estate Tax Books

Uses Ollama vision models (GLM-OCR, LLaVA, etc.) to extract property records
from PDF tax books with high accuracy.

Requirements:
- Ollama >= 0.7 with a vision model (glm-ocr, llava, minicpm-v)
- pdftoppm (from poppler-utils) for PDF to image conversion
- Python packages: requests, Pillow

Usage:
    # Test on 10 pages first
    python scripts/ocr_real_estate_vision.py --test 10

    # Process a single year
    python scripts/ocr_real_estate_vision.py --year 2025

    # Process all years
    python scripts/ocr_real_estate_vision.py --all

    # Resume from checkpoint
    python scripts/ocr_real_estate_vision.py --all --resume

    # Use specific model
    python scripts/ocr_real_estate_vision.py --all --model llava:34b
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

# Configuration
OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "glm-ocr"  # Best for document OCR
FALLBACK_MODELS = ["minicpm-v", "llava:13b", "llava:7b"]

# Tax book files
TAX_BOOKS = {
    2021: "Real Estate 2021 Tax Book.pdf",
    2022: "Real Estate 2022 Tax Book.pdf",
    2023: "RE 2023 Book.pdf",
    2024: "RE_Book_2024.pdf",
    2025: "RE_2025_Book.pdf",
}

TAX_RATES = {
    2021: 0.61,
    2022: 0.61,
    2023: 0.51,
    2024: 0.51,
    2025: 0.48,
}

# Districts in Frederick County
DISTRICTS = [
    "Back Creek", "Gainesboro", "Opequon", "Red Bud",
    "Shawnee", "Stonewall", "Stephens City", "Middletown"
]

# Directories
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
RAW_DIR = DATA_DIR / "raw" / "fcva" / "real-estate-tax"
OUTPUT_DIR = DATA_DIR / "processed"
CHECKPOINT_DIR = DATA_DIR / "checkpoints"


@dataclass
class PropertyRecord:
    """A single property record from the tax book."""
    year: int
    parcel_code: Optional[str] = None
    owner_name: Optional[str] = None
    owner_address: Optional[str] = None
    owner_city_state_zip: Optional[str] = None
    description: Optional[str] = None
    land_value: int = 0
    improvement_value: int = 0
    total_value: int = 0
    tax_amount: float = 0.0
    acreage: Optional[float] = None
    property_class: Optional[int] = None
    zone: Optional[str] = None
    account_number: Optional[str] = None
    district: Optional[str] = None
    first_half_tax: float = 0.0
    second_half_tax: float = 0.0
    deed_book: Optional[str] = None
    deferred_value: int = 0
    source_page: Optional[int] = None
    ocr_confidence: Optional[float] = None


def check_ollama() -> tuple[bool, str]:
    """Check if Ollama is running and get version."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/version", timeout=5)
        if resp.status_code == 200:
            version = resp.json().get("version", "unknown")
            return True, version
    except requests.exceptions.ConnectionError:
        pass
    return False, "not running"


def get_available_models() -> list[str]:
    """Get list of models available in Ollama."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            return [m["name"] for m in models]
    except:
        pass
    return []


def select_vision_model(preferred: str = DEFAULT_MODEL) -> Optional[str]:
    """Select the best available vision model."""
    available = get_available_models()
    
    # Check preferred model
    if preferred in available:
        return preferred
    
    # Check preferred without tag
    for m in available:
        if m.startswith(preferred.split(":")[0]):
            return m
    
    # Check fallbacks
    for fallback in FALLBACK_MODELS:
        if fallback in available:
            return fallback
        for m in available:
            if m.startswith(fallback.split(":")[0]):
                return m
    
    return None


def pdf_to_image(pdf_path: Path, page_num: int, dpi: int = 150) -> bytes:
    """Convert a single PDF page to PNG image bytes."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        # pdftoppm uses 0-indexed pages internally but -f/-l are 1-indexed
        result = subprocess.run([
            "pdftoppm",
            "-png",
            "-f", str(page_num),
            "-l", str(page_num),
            "-r", str(dpi),
            "-singlefile",
            str(pdf_path),
            tmp_path.replace(".png", "")
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"pdftoppm failed: {result.stderr}")
        
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def image_to_base64(image_bytes: bytes) -> str:
    """Convert image bytes to base64 string."""
    return base64.b64encode(image_bytes).decode("utf-8")


def extract_records_from_page(
    model: str,
    image_base64: str,
    year: int,
    page_num: int,
    timeout: int = 120
) -> list[PropertyRecord]:
    """Use vision model to extract property records from a page image."""
    
    prompt = f"""You are extracting property tax records from a Frederick County, Virginia real estate tax book page.

This is page {page_num} from the {year} tax year (tax rate: ${TAX_RATES.get(year, 0.50):.2f} per $100).

For EACH property record visible on this page, extract:
- parcel_code: The property identifier (format like "49A-05-1-F-73" or "85--A--102-C")
- owner_name: Property owner's name (just the name, not address)
- owner_address: Street address of owner
- owner_city_state_zip: City, state, and ZIP of owner
- description: Property description (subdivision name, lot number, etc.)
- land_value: Land assessed value (integer, no commas)
- improvement_value: Improvement/building value (integer, 0 if blank)
- total_value: Total assessed value (integer)
- tax_amount: Annual tax amount (decimal)
- acreage: Property size in acres (decimal, null if not shown)
- property_class: Class number 1-9 (from "CL X" notation)
- zone: Zoning code (from "ZN XX" notation)
- account_number: Account number (from "ACCT-XXXXXXX")
- district: Magisterial district (Back Creek, Gainesboro, Opequon, Red Bud, Shawnee, Stonewall, Stephens City, or Middletown)
- first_half_tax: First half tax amount (from "FH XXX.XX")
- second_half_tax: Second half tax amount (from "SH XXX.XX")
- deferred_value: Deferred tax value if shown (integer, 0 if none)

Return a JSON array of objects, one per property. Skip page headers, totals, and class summary rows.
Only include actual property records with parcel codes and values.

Return ONLY valid JSON, no markdown formatting or explanation."""

    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_base64],
        "stream": False,
        "options": {
            "temperature": 0.1,  # Low temperature for accuracy
            "num_predict": 8192,  # Allow long responses for multiple records
        }
    }
    
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            timeout=timeout
        )
        resp.raise_for_status()
        
        result = resp.json()
        response_text = result.get("response", "")
        
        # Try to parse JSON from response
        records = parse_json_response(response_text, year, page_num)
        return records
        
    except requests.exceptions.Timeout:
        print(f"    [!] Timeout on page {page_num}")
        return []
    except Exception as e:
        print(f"    [!] Error on page {page_num}: {e}")
        return []


def parse_json_response(text: str, year: int, page_num: int) -> list[PropertyRecord]:
    """Parse JSON response from vision model into PropertyRecord objects."""
    records = []
    
    # Try to extract JSON from the response
    # Sometimes models wrap JSON in markdown code blocks
    json_match = re.search(r'\[[\s\S]*\]', text)
    if not json_match:
        return []
    
    try:
        data = json.loads(json_match.group())
        if not isinstance(data, list):
            data = [data]
        
        for item in data:
            if not isinstance(item, dict):
                continue
            
            # Skip if no parcel code (probably a header/total row)
            if not item.get("parcel_code"):
                continue
            
            record = PropertyRecord(
                year=year,
                parcel_code=clean_string(item.get("parcel_code")),
                owner_name=clean_string(item.get("owner_name")),
                owner_address=clean_string(item.get("owner_address")),
                owner_city_state_zip=clean_string(item.get("owner_city_state_zip")),
                description=clean_string(item.get("description")),
                land_value=parse_int(item.get("land_value")),
                improvement_value=parse_int(item.get("improvement_value")),
                total_value=parse_int(item.get("total_value")),
                tax_amount=parse_float(item.get("tax_amount")),
                acreage=parse_float(item.get("acreage")),
                property_class=parse_int(item.get("property_class")),
                zone=clean_string(item.get("zone")),
                account_number=clean_string(item.get("account_number")),
                district=normalize_district(item.get("district")),
                first_half_tax=parse_float(item.get("first_half_tax")),
                second_half_tax=parse_float(item.get("second_half_tax")),
                deferred_value=parse_int(item.get("deferred_value")),
                source_page=page_num,
            )
            
            # Basic validation
            if record.total_value > 0 or record.land_value > 0:
                records.append(record)
                
    except json.JSONDecodeError as e:
        print(f"    [!] JSON parse error on page {page_num}: {e}")
    
    return records


def clean_string(value) -> Optional[str]:
    """Clean and normalize a string value."""
    if value is None:
        return None
    s = str(value).strip()
    # Remove multiple spaces
    s = re.sub(r'\s+', ' ', s)
    return s if s else None


def parse_int(value) -> int:
    """Parse an integer value, handling commas and strings."""
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).replace(",", "").replace("$", "").strip())
    except:
        return 0


def parse_float(value) -> float:
    """Parse a float value, handling commas and strings."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except:
        return 0.0


def normalize_district(value) -> Optional[str]:
    """Normalize district name to standard form."""
    if not value:
        return None
    
    value = str(value).strip().upper()
    
    mappings = {
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
        "MIDDLETOWN": "Middletown",
    }
    
    return mappings.get(value.replace(" ", ""), mappings.get(value))


def get_pdf_page_count(pdf_path: Path) -> int:
    """Get the number of pages in a PDF."""
    result = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        capture_output=True,
        text=True
    )
    for line in result.stdout.split("\n"):
        if line.startswith("Pages:"):
            return int(line.split(":")[1].strip())
    return 0


def load_checkpoint(year: int) -> tuple[int, list[dict]]:
    """Load checkpoint for a year. Returns (last_page, records)."""
    checkpoint_file = CHECKPOINT_DIR / f"ocr_checkpoint_{year}.json"
    if checkpoint_file.exists():
        with open(checkpoint_file, "r") as f:
            data = json.load(f)
            return data.get("last_page", 0), data.get("records", [])
    return 0, []


def save_checkpoint(year: int, last_page: int, records: list[dict]):
    """Save checkpoint for a year."""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_file = CHECKPOINT_DIR / f"ocr_checkpoint_{year}.json"
    with open(checkpoint_file, "w") as f:
        json.dump({
            "year": year,
            "last_page": last_page,
            "records": records,
            "saved_at": datetime.now().isoformat()
        }, f)


def process_year(
    year: int,
    model: str,
    resume: bool = False,
    test_pages: int = 0,
    skip_first_pages: int = 5  # Skip title/intro pages
) -> list[PropertyRecord]:
    """Process all pages of a single year's tax book."""
    
    pdf_file = TAX_BOOKS.get(year)
    if not pdf_file:
        print(f"[{year}] No PDF file configured")
        return []
    
    pdf_path = RAW_DIR / pdf_file
    if not pdf_path.exists():
        print(f"[{year}] PDF not found: {pdf_path}")
        return []
    
    total_pages = get_pdf_page_count(pdf_path)
    print(f"[{year}] Processing {pdf_file} ({total_pages} pages)")
    
    # Load checkpoint if resuming
    start_page = skip_first_pages + 1
    records = []
    
    if resume:
        last_page, saved_records = load_checkpoint(year)
        if last_page > 0:
            start_page = last_page + 1
            records = [PropertyRecord(**r) for r in saved_records]
            print(f"[{year}] Resuming from page {start_page} ({len(records)} records loaded)")
    
    # Determine end page
    end_page = total_pages
    if test_pages > 0:
        end_page = min(start_page + test_pages - 1, total_pages)
        print(f"[{year}] TEST MODE: Processing pages {start_page}-{end_page}")
    
    # Process pages
    pages_processed = 0
    start_time = time.time()
    
    for page_num in range(start_page, end_page + 1):
        try:
            # Convert page to image
            image_bytes = pdf_to_image(pdf_path, page_num)
            image_b64 = image_to_base64(image_bytes)
            
            # Extract records
            page_records = extract_records_from_page(model, image_b64, year, page_num)
            records.extend(page_records)
            
            pages_processed += 1
            
            # Progress update
            if pages_processed % 10 == 0:
                elapsed = time.time() - start_time
                rate = pages_processed / elapsed
                remaining = (end_page - page_num) / rate if rate > 0 else 0
                print(f"  [{year}] Page {page_num}/{end_page} | "
                      f"{len(records)} records | "
                      f"{rate:.1f} pages/sec | "
                      f"ETA: {remaining/60:.1f} min")
            
            # Checkpoint every 100 pages
            if pages_processed % 100 == 0:
                save_checkpoint(year, page_num, [asdict(r) for r in records])
                
        except KeyboardInterrupt:
            print(f"\n[{year}] Interrupted at page {page_num}")
            save_checkpoint(year, page_num, [asdict(r) for r in records])
            raise
        except Exception as e:
            print(f"  [{year}] Error on page {page_num}: {e}")
            continue
    
    # Final save
    elapsed = time.time() - start_time
    print(f"[{year}] Complete: {len(records)} records from {pages_processed} pages "
          f"in {elapsed/60:.1f} minutes")
    
    return records


def main():
    parser = argparse.ArgumentParser(
        description="Vision-based OCR for Frederick County Real Estate Tax Books"
    )
    parser.add_argument("--year", type=int, help="Process a single year")
    parser.add_argument("--all", action="store_true", help="Process all years")
    parser.add_argument("--test", type=int, default=0, 
                        help="Test mode: process only N pages per year")
    parser.add_argument("--resume", action="store_true", 
                        help="Resume from checkpoint")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL,
                        help=f"Ollama model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--list-models", action="store_true",
                        help="List available Ollama models and exit")
    
    args = parser.parse_args()
    
    # Check Ollama
    running, version = check_ollama()
    if not running:
        print("ERROR: Ollama is not running. Start it with: ollama serve")
        sys.exit(1)
    print(f"Ollama version: {version}")
    
    # List models if requested
    if args.list_models:
        models = get_available_models()
        print(f"\nAvailable models ({len(models)}):")
        for m in models:
            print(f"  - {m}")
        sys.exit(0)
    
    # Select model
    model = select_vision_model(args.model)
    if not model:
        print(f"ERROR: No vision model available. Install one with:")
        print(f"  ollama pull {DEFAULT_MODEL}")
        print(f"  # or: ollama pull llava:13b")
        sys.exit(1)
    print(f"Using model: {model}")
    
    # Determine years to process
    years = []
    if args.year:
        years = [args.year]
    elif args.all:
        years = sorted(TAX_BOOKS.keys())
    else:
        parser.print_help()
        sys.exit(1)
    
    print(f"Years to process: {years}")
    print()
    
    # Process each year
    all_records = []
    for year in years:
        try:
            records = process_year(
                year=year,
                model=model,
                resume=args.resume,
                test_pages=args.test
            )
            all_records.extend(records)
        except KeyboardInterrupt:
            print("\nInterrupted by user")
            break
    
    # Save final output
    if all_records:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        output = {
            "metadata": {
                "source": "Frederick County Commissioner of Revenue",
                "source_url": "https://www.fcva.us/departments/commissioner-of-the-revenue",
                "description": "Real Estate Tax Assessment Data (Vision OCR)",
                "ocr_model": model,
                "processed_date": datetime.now().isoformat(),
                "total_records": len(all_records),
                "years": years,
            },
            "records": [asdict(r) for r in all_records]
        }
        
        # Write output
        if args.test:
            output_file = OUTPUT_DIR / "real_estate_tax_ocr_test.json"
        else:
            output_file = OUTPUT_DIR / "real_estate_tax_ocr.json"
        
        print(f"\nWriting {len(all_records)} records to {output_file}...")
        with open(output_file, "w") as f:
            json.dump(output, f, indent=2)
        
        print(f"Output: {output_file} ({output_file.stat().st_size / 1024 / 1024:.1f} MB)")
        
        # Print summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        by_year = {}
        for r in all_records:
            by_year.setdefault(r.year, []).append(r)
        
        for year in sorted(by_year.keys()):
            recs = by_year[year]
            total_value = sum(r.total_value for r in recs)
            total_tax = sum(r.tax_amount for r in recs)
            print(f"\n{year}:")
            print(f"  Records:     {len(recs):>10,}")
            print(f"  Total Value: ${total_value:>14,}")
            print(f"  Total Tax:   ${total_tax:>14,.2f}")


if __name__ == "__main__":
    main()
