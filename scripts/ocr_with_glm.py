#!/usr/bin/env python3
"""
OCR processing using GLM-OCR via Ollama.

Converts PDF pages to images and processes with GLM-OCR for high-quality
text and table extraction.

Usage:
    python scripts/ocr_with_glm.py --input data/raw/real-estate/ --output data/processed/ocr/
    python scripts/ocr_with_glm.py --input data/raw/real-estate/RE_2025_Book.pdf --pages 1-10
"""

import argparse
import base64
import json
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests
from pdf2image import convert_from_path
from PIL import Image

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
OCR_DIR = PROCESSED_DIR / "ocr"

# Ollama API endpoint (use chat API for vision models)
OLLAMA_API = "http://localhost:11434/api/chat"

# Target image size for GLM-OCR (larger sizes cause tensor errors)
TARGET_IMAGE_SIZE = (850, 1100)

# Timeout for Ollama API calls (10 minutes - let it cook)
OLLAMA_TIMEOUT = 600

# Known OCR corrections for Frederick County documents
# The model consistently misreads certain text in the header font
OCR_CORRECTIONS = {
    r"PREBRIICK": "FREDERICK",
    r"PREDERICK": "FREDERICK",
    r"PREBERRICK": "FREDERICK",
    r"PREDERCK": "FREDERICK",
    r"FREDRICK": "FREDERICK",
    r"WINNEBER": "WINCHESTER",
    r"WINNCESTER": "WINCHESTER",
    r"\bEN\s+(RA|RP|R4|R5|M1|B1|B2)\b": r"ZN \1",  # EN RA -> ZN RA (zone code misread)
}

# Pre-defined context hints for specific document types
DOCUMENT_CONTEXTS = {
    "frederick-tax": "This document is from Frederick County, Virginia. The text uses tight character spacing.",
    "fcps-budget": "This is a Frederick County Public Schools budget document from Virginia.",
    "county-budget": "This is a Frederick County, Virginia government budget document.",
}


def apply_corrections(text: str) -> str:
    """Apply known OCR corrections to text."""
    for pattern, replacement in OCR_CORRECTIONS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def image_to_base64(image_path: Path) -> str:
    """Convert image file to base64 string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def build_prompt(base_prompt: str, context: Optional[str] = None) -> str:
    """
    Build the full prompt with optional context.
    
    Args:
        base_prompt: Base OCR prompt like "Text Recognition:"
        context: Optional context hint about the document
        
    Returns:
        Full prompt string
    """
    if context:
        # Look up predefined context or use as-is
        context_text = DOCUMENT_CONTEXTS.get(context, context)
        return f"{context_text} {base_prompt}"
    return base_prompt


def call_glm_ocr(
    image_path: Path,
    prompt: str = "Text Recognition:",
    context: Optional[str] = None,
) -> str:
    """
    Call GLM-OCR via Ollama chat API.
    
    Args:
        image_path: Path to image file
        prompt: OCR prompt - "Text Recognition:", "Table Recognition:", or JSON schema
        context: Optional context hint (predefined key or custom text)
        
    Returns:
        OCR result text
    """
    image_b64 = image_to_base64(image_path)
    full_prompt = build_prompt(prompt, context)
    
    payload = {
        "model": "glm-ocr",
        "messages": [
            {
                "role": "user",
                "content": full_prompt,
                "images": [image_b64]
            }
        ],
        "stream": False,
    }
    
    try:
        response = requests.post(OLLAMA_API, json=payload, timeout=OLLAMA_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        message = result.get("message", {})
        return message.get("content", "")
    except requests.RequestException as e:
        print(f"  Error calling Ollama: {e}")
        return f"ERROR: {e}"


def pdf_to_images(
    pdf_path: Path,
    output_dir: Path,
    dpi: int = 200,
    first_page: Optional[int] = None,
    last_page: Optional[int] = None,
    target_size: tuple[int, int] = TARGET_IMAGE_SIZE,
):
    """
    Convert PDF pages to images, resized for GLM-OCR.
    
    Args:
        pdf_path: Path to PDF file
        output_dir: Directory to save images
        dpi: Capture resolution (higher = sharper before resize)
        first_page: First page to convert (1-indexed)
        last_page: Last page to convert (1-indexed)
        target_size: Target image dimensions for OCR
        
    Yields:
        Tuple of (page_number, image_path)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Build kwargs for convert_from_path
    kwargs = {"dpi": dpi, "fmt": "png"}
    if first_page is not None:
        kwargs["first_page"] = first_page
    if last_page is not None:
        kwargs["last_page"] = last_page
    
    # Convert PDF to images
    images = convert_from_path(pdf_path, **kwargs)
    
    for i, image in enumerate(images):
        page_num = (first_page or 1) + i
        
        # Resize to target size for GLM-OCR compatibility
        resized = image.resize(target_size, Image.LANCZOS)
        
        image_path = output_dir / f"page_{page_num:05d}.png"
        resized.save(image_path, "PNG", optimize=True)
        yield page_num, image_path


def process_pdf_with_ocr(
    pdf_path: Path,
    output_dir: Path,
    prompt: str = "Text Recognition:",
    context: Optional[str] = None,
    first_page: Optional[int] = None,
    last_page: Optional[int] = None,
    dpi: int = 200,
    save_images: bool = False,
    apply_ocr_corrections: bool = True,
) -> dict[str, Any]:
    """
    Process a PDF file with GLM-OCR.
    
    Args:
        pdf_path: Path to PDF file
        output_dir: Directory for output files
        prompt: OCR prompt to use
        context: Optional context hint (predefined key or custom text)
        first_page: First page to process (1-indexed)
        last_page: Last page to process (1-indexed)
        dpi: Image capture resolution
        save_images: Whether to keep page images
        apply_ocr_corrections: Whether to apply known text corrections
        
    Returns:
        Dictionary with OCR results
    """
    pdf_name = pdf_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create temp directory for images
    if save_images:
        image_dir = output_dir / f"{pdf_name}_images"
        image_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir = tempfile.mkdtemp()
        image_dir = Path(temp_dir)
    
    result = {
        "source_file": pdf_path.name,
        "source_path": str(pdf_path),
        "processed_date": datetime.now().isoformat(),
        "prompt": prompt,
        "context": context,
        "dpi": dpi,
        "target_size": list(TARGET_IMAGE_SIZE),
        "corrections_applied": apply_ocr_corrections,
        "pages": [],
        "errors": [],
    }
    
    print(f"Processing: {pdf_path.name}")
    print(f"  Converting PDF to images (DPI={dpi}, target={TARGET_IMAGE_SIZE})...")
    
    start_time = time.time()
    page_count = 0
    
    try:
        for page_num, image_path in pdf_to_images(
            pdf_path, image_dir, dpi, first_page, last_page
        ):
            page_count += 1
            
            print(f"  Page {page_num}: OCR processing...", end=" ", flush=True)
            page_start = time.time()
            
            # Call GLM-OCR
            ocr_text = call_glm_ocr(image_path, prompt, context)
            
            # Apply corrections if enabled
            if apply_ocr_corrections and not ocr_text.startswith("ERROR:"):
                ocr_text = apply_corrections(ocr_text)
            
            page_time = time.time() - page_start
            print(f"done ({page_time:.1f}s, {len(ocr_text)} chars)")
            
            page_result = {
                "page": page_num,
                "text": ocr_text,
                "char_count": len(ocr_text),
                "processing_time_sec": round(page_time, 2),
            }
            
            if ocr_text.startswith("ERROR:"):
                result["errors"].append({"page": page_num, "error": ocr_text})
            
            result["pages"].append(page_result)
            
            # Clean up image if not saving
            if not save_images:
                image_path.unlink()
    
    except Exception as e:
        result["errors"].append({"page": "general", "error": str(e)})
        print(f"  Error: {e}")
    
    finally:
        # Clean up temp directory
        if not save_images and image_dir.exists():
            try:
                for f in image_dir.iterdir():
                    f.unlink()
                image_dir.rmdir()
            except:
                pass
    
    total_time = time.time() - start_time
    result["total_pages"] = page_count
    result["total_time_sec"] = round(total_time, 2)
    result["pages_per_sec"] = round(page_count / total_time, 2) if total_time > 0 else 0
    
    print(f"  Completed: {page_count} pages in {total_time:.1f}s ({result['pages_per_sec']:.2f} pages/sec)")
    
    return result


def parse_page_range(page_range: str) -> tuple[int, int]:
    """Parse page range string like '1-10' or '5'."""
    if "-" in page_range:
        parts = page_range.split("-")
        return int(parts[0]), int(parts[1])
    else:
        page = int(page_range)
        return page, page


def main():
    parser = argparse.ArgumentParser(
        description="OCR processing using GLM-OCR via Ollama",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--input", "-i",
        type=Path,
        required=True,
        help="Input PDF file or directory"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=OCR_DIR,
        help="Output directory for OCR results"
    )
    parser.add_argument(
        "--pages", "-p",
        type=str,
        default=None,
        help="Page range to process (e.g., '1-10', '5'). Default: all pages"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="Text Recognition:",
        help="OCR prompt: 'Text Recognition:', 'Table Recognition:', or custom"
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="Image capture resolution (default: 200)"
    )
    parser.add_argument(
        "--save-images",
        action="store_true",
        help="Save page images alongside OCR output"
    )
    parser.add_argument(
        "--no-corrections",
        action="store_true",
        help="Disable automatic OCR text corrections"
    )
    parser.add_argument(
        "--context", "-c",
        type=str,
        default=None,
        help=f"Context hint for OCR. Predefined: {', '.join(DOCUMENT_CONTEXTS.keys())}. Or custom text."
    )
    
    args = parser.parse_args()
    
    if not args.input.exists():
        print(f"Error: Input does not exist: {args.input}")
        sys.exit(1)
    
    # Parse page range
    first_page: Optional[int] = None
    last_page: Optional[int] = None
    if args.pages:
        first_page, last_page = parse_page_range(args.pages)
    
    # Get list of PDFs to process
    if args.input.is_file():
        pdf_files = [args.input]
    else:
        pdf_files = list(args.input.glob("*.pdf")) + list(args.input.glob("*.PDF"))
    
    if not pdf_files:
        print(f"No PDF files found in {args.input}")
        sys.exit(0)
    
    print("=" * 60)
    print("GLM-OCR PDF Processing")
    print("=" * 60)
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    print(f"PDFs to process: {len(pdf_files)}")
    print(f"Prompt: {args.prompt}")
    print(f"DPI: {args.dpi}")
    print(f"Target size: {TARGET_IMAGE_SIZE}")
    print(f"Corrections: {'disabled' if args.no_corrections else 'enabled'}")
    if args.context:
        print(f"Context: {args.context}")
    if args.pages:
        print(f"Pages: {first_page}-{last_page}")
    print("=" * 60)
    
    args.output.mkdir(parents=True, exist_ok=True)
    
    all_results = []
    
    for pdf_path in pdf_files:
        result = process_pdf_with_ocr(
            pdf_path=pdf_path,
            output_dir=args.output,
            prompt=args.prompt,
            context=args.context,
            first_page=first_page,
            last_page=last_page,
            dpi=args.dpi,
            save_images=args.save_images,
            apply_ocr_corrections=not args.no_corrections,
        )
        
        # Save individual result
        output_file = args.output / f"{pdf_path.stem}_ocr.json"
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        print(f"  Saved: {output_file}")
        
        all_results.append(result)
    
    # Save combined results
    if len(all_results) > 1:
        combined_output = args.output / "ocr_results_combined.json"
        with open(combined_output, "w") as f:
            json.dump({
                "processed_date": datetime.now().isoformat(),
                "files_processed": len(all_results),
                "results": all_results,
            }, f, indent=2)
        print(f"\nCombined results saved to: {combined_output}")
    
    print("\n" + "=" * 60)
    print("Processing complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
