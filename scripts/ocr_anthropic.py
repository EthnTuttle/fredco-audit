#!/usr/bin/env python3
"""
OCR processing using Anthropic's Batch API with Claude 3.5 Haiku.

Converts scanned PDF pages to text using vision capabilities of Claude 3.5 Haiku
via the Batch API (50% cost discount). Outputs JSON files compatible with the
existing parse_ocr_output.py pipeline.

Cost estimate: ~$38 for all 5 real estate tax books (~23,586 pages)
  - Input:  ~28M tokens @ $0.50/MTok (batch Haiku 4.5) = ~$14
  - Output: ~9.4M tokens @ $2.50/MTok (batch Haiku 4.5) = ~$24

Subcommands:
  submit    Convert PDF pages to images and submit batch requests
  status    Check status of submitted batches
  collect   Download results from completed batches
  test      Process a single page via Messages API (for testing)

Usage:
    # Install: pip3 install anthropic pdf2image Pillow
    # Set: export ANTHROPIC_API_KEY=sk-ant-...

    # Test with one page first
    python3 scripts/ocr_anthropic.py test --pdf "data/raw/real-estate/RE_Book_2024.pdf" --page 100

    # Submit all PDFs
    python3 scripts/ocr_anthropic.py submit

    # Submit just one PDF
    python3 scripts/ocr_anthropic.py submit --pdf "data/raw/real-estate/RE_2025_Book.pdf"

    # Check batch status
    python3 scripts/ocr_anthropic.py status

    # Collect results when done
    python3 scripts/ocr_anthropic.py collect
"""

import argparse
import base64
import io
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw" / "real-estate"
OCR_DIR = DATA_DIR / "processed" / "ocr"

# Tracking file for batch IDs
BATCH_TRACKING_FILE = OCR_DIR / "anthropic_batches.json"

# Model to use - Haiku 4.5 is cheapest vision-capable model
# $1/MTok input, $5/MTok output (batch: $0.50/MTok input, $2.50/MTok output)
MODEL = "claude-haiku-4-5-20251001"

# Batch size: pages per API batch submission
# Anthropic limit is 100,000 requests per batch, so we can do one PDF per batch
PAGES_PER_OUTPUT_FILE = 50  # Group results into 50-page JSON files (matching existing format)

# Image settings
TARGET_DPI = 200
TARGET_SIZE = (850, 1100)  # Match existing pipeline

# OCR prompt
SYSTEM_PROMPT = (
    "You are an OCR engine. Extract all text from the image exactly as printed. "
    "Preserve the layout structure including line breaks. "
    "Do not add any commentary or interpretation - only output the raw text content."
)

USER_PROMPT = (
    "This is a scanned page from a Frederick County, Virginia real estate tax book. "
    "Extract all text exactly as printed, preserving the layout. "
    "Include all property codes, owner names, addresses, acreage, zoning codes, "
    "account numbers, assessed values, and tax amounts."
)

# PDF files with page counts (same as ocr_parallel.py)
PDF_FILES = [
    ("data/raw/real-estate/Real Estate 2021 Tax Book.pdf", 4576),
    ("data/raw/real-estate/Real Estate 2022 Tax Book.pdf", 4645),
    ("data/raw/real-estate/RE 2023 Book.pdf", 4700),
    ("data/raw/real-estate/RE_Book_2024.pdf", 4808),
    ("data/raw/real-estate/RE_2025_Book.pdf", 4857),
]


def get_output_prefix(pdf_path: str) -> str:
    """Get the output filename prefix for a PDF (e.g., 'anthropic_RE_Book_2024')."""
    name = Path(pdf_path).stem.replace(" ", "_")
    return f"anthropic_{name}"


def get_output_path(pdf_path: str, start_page: int, end_page: int) -> Path:
    """Get the output path for a batch of pages."""
    prefix = get_output_prefix(pdf_path)
    return OCR_DIR / f"{prefix}_pages_{start_page}-{end_page}.json"


def is_batch_complete(pdf_path: str, start_page: int, end_page: int) -> bool:
    """Check if a batch of pages has already been processed."""
    return get_output_path(pdf_path, start_page, end_page).exists()


def image_to_base64(image) -> str:
    """Convert PIL Image to base64 string."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def load_batch_tracking() -> dict:
    """Load the batch tracking file."""
    if BATCH_TRACKING_FILE.exists():
        with open(BATCH_TRACKING_FILE) as f:
            return json.load(f)
    return {"batches": []}


def save_batch_tracking(tracking: dict):
    """Save the batch tracking file."""
    with open(BATCH_TRACKING_FILE, "w") as f:
        json.dump(tracking, f, indent=2)


def make_custom_id(pdf_path: str, page_num: int) -> str:
    """Create a custom_id for a batch request.

    Format: pdfname__page_NNNN (double underscore separator)
    """
    name = Path(pdf_path).stem.replace(" ", "_")
    return f"{name}__page_{page_num:05d}"


def parse_custom_id(custom_id: str) -> tuple[str, int]:
    """Parse a custom_id back to (pdf_stem, page_num)."""
    # Format: pdfname__page_NNNNN
    parts = custom_id.rsplit("__page_", 1)
    pdf_stem = parts[0]
    page_num = int(parts[1])
    return pdf_stem, page_num


def cmd_test(args):
    """Test OCR on a single page using the Messages API (not batch)."""
    try:
        import anthropic
        from pdf2image import convert_from_path
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Install with: pip3 install anthropic pdf2image Pillow")
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    pdf_path = BASE_DIR / args.pdf
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        sys.exit(1)

    page = args.page
    print(f"Testing OCR on {args.pdf} page {page}...")
    print(f"Model: {MODEL}")

    # Convert page to image
    print("Converting PDF page to image...")
    images = convert_from_path(
        pdf_path,
        first_page=page,
        last_page=page,
        dpi=TARGET_DPI,
        size=TARGET_SIZE,
    )
    image = images[0]
    img_b64 = image_to_base64(image)
    print(f"Image size: {image.size}, base64 length: {len(img_b64)}")

    # Send to Anthropic
    print("Sending to Anthropic API...")
    client = anthropic.Anthropic()
    start_time = time.time()

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": USER_PROMPT,
                    },
                ],
            }
        ],
    )

    elapsed = time.time() - start_time
    text = response.content[0].text

    print(f"\n{'='*60}")
    print(f"Time: {elapsed:.1f}s")
    print(f"Input tokens: {response.usage.input_tokens}")
    print(f"Output tokens: {response.usage.output_tokens}")
    print(f"Text length: {len(text)} chars")
    print(f"{'='*60}")
    print(text)
    print(f"{'='*60}")

    # Estimate cost (Haiku 4.5 pricing)
    input_cost = response.usage.input_tokens * 1.00 / 1_000_000  # Haiku 4.5 input
    output_cost = response.usage.output_tokens * 5.00 / 1_000_000  # Haiku 4.5 output
    batch_input_cost = response.usage.input_tokens * 0.50 / 1_000_000  # Batch 50% discount
    batch_output_cost = response.usage.output_tokens * 2.50 / 1_000_000
    print(f"\nCost (standard): ${input_cost + output_cost:.4f}")
    print(f"Cost (batch):    ${batch_input_cost + batch_output_cost:.4f}")

    total_pages = sum(p for _, p in PDF_FILES)
    est_batch_total = (batch_input_cost + batch_output_cost) * total_pages
    print(f"\nEstimated batch cost for all {total_pages} pages: ${est_batch_total:.2f}")


def cmd_submit(args):
    """Submit PDF pages as batch requests to Anthropic."""
    try:
        import anthropic
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request
        from pdf2image import convert_from_path
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Install with: pip3 install anthropic pdf2image Pillow")
        sys.exit(1)

    if not args.dry_run and not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    client = None if args.dry_run else anthropic.Anthropic()
    tracking = load_batch_tracking()

    # Determine which PDFs to process
    if args.pdf:
        pdfs = [(p, c) for p, c in PDF_FILES if args.pdf in p]
        if not pdfs:
            print(f"Error: PDF not found matching '{args.pdf}'")
            print("Available PDFs:")
            for p, c in PDF_FILES:
                print(f"  {p} ({c} pages)")
            sys.exit(1)
    else:
        pdfs = PDF_FILES

    # Count already-submitted pages per PDF from tracking data
    submitted_count_by_pdf = {}  # pdf_path -> total pages submitted
    for batch_info in tracking["batches"]:
        if batch_info.get("status") in ("submitted", "in_progress", "ended"):
            bp = batch_info["pdf_path"]
            submitted_count_by_pdf[bp] = submitted_count_by_pdf.get(bp, 0) + batch_info.get("requests_count", 0)

    for pdf_path, total_pages in pdfs:
        pdf_full_path = BASE_DIR / pdf_path
        if not pdf_full_path.exists():
            print(f"Warning: PDF not found: {pdf_full_path}, skipping")
            continue

        # Determine pages to process
        start_page = args.start_page or 1
        end_page = args.end_page or total_pages

        # Find pages that still need processing
        # Ground truth: if the output file exists with valid data, skip those pages
        pages_needed = []
        for page_num in range(start_page, end_page + 1):
            batch_start = ((page_num - 1) // PAGES_PER_OUTPUT_FILE) * PAGES_PER_OUTPUT_FILE + 1
            batch_end = min(batch_start + PAGES_PER_OUTPUT_FILE - 1, total_pages)
            if not is_batch_complete(pdf_path, batch_start, batch_end):
                pages_needed.append(page_num)

        # Deduplicate (since multiple pages map to same output batch)
        pages_needed = sorted(set(pages_needed))

        # Report already-submitted count for context
        already_submitted_count = submitted_count_by_pdf.get(pdf_path, 0)
        if already_submitted_count > 0:
            print(f"\n{Path(pdf_path).name}: {already_submitted_count} pages in prior batches")

        if not pages_needed:
            print(f"Skipping {Path(pdf_path).name}: all output files already exist")
            continue

        print(f"\n{'='*60}")
        print(f"Processing: {Path(pdf_path).name}")
        print(f"Pages: {len(pages_needed)} of {total_pages} (pages {pages_needed[0]}-{pages_needed[-1]})")
        print(f"{'='*60}")

        if args.dry_run:
            est_cost = len(pages_needed) * 0.0016  # ~$0.0016/page at batch Haiku 4.5 rates
            print(f"Dry run: would submit {len(pages_needed)} pages, est. cost: ${est_cost:.2f}")
            continue

        # Build batch requests
        # Process in chunks to avoid memory issues (convert 50 pages at a time)
        requests = []
        chunk_size = 50

        for chunk_start in range(0, len(pages_needed), chunk_size):
            chunk_pages = pages_needed[chunk_start:chunk_start + chunk_size]
            first_page = chunk_pages[0]
            last_page = chunk_pages[-1]

            print(f"  Converting pages {first_page}-{last_page} to images...", end="", flush=True)
            images = convert_from_path(
                pdf_full_path,
                first_page=first_page,
                last_page=last_page,
                dpi=TARGET_DPI,
                size=TARGET_SIZE,
            )

            for i, page_num in enumerate(chunk_pages):
                # The image index corresponds to position in the range
                img_idx = page_num - first_page
                if img_idx >= len(images):
                    print(f"\n  Warning: no image for page {page_num}, skipping")
                    continue

                img_b64 = image_to_base64(images[img_idx])
                custom_id = make_custom_id(pdf_path, page_num)

                req = Request(
                    custom_id=custom_id,
                    params=MessageCreateParamsNonStreaming(
                        model=MODEL,
                        max_tokens=4096,
                        system=SYSTEM_PROMPT,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": "image/png",
                                            "data": img_b64,
                                        },
                                    },
                                    {
                                        "type": "text",
                                        "text": USER_PROMPT,
                                    },
                                ],
                            }
                        ],
                    ),
                )
                requests.append(req)

            print(f" {len(requests)} requests built")

            # Free memory
            del images

        print(f"\nSubmitting batch with {len(requests)} requests...")

        # Anthropic batch limit is 100,000 requests or 256MB, whichever first
        # Each request with base64 image is ~200KB, so 256MB / 200KB = ~1280 max
        # Use 1000 to stay safely under the limit
        MAX_REQUESTS_PER_BATCH = 1000
        sub_batches = [
            requests[i:i + MAX_REQUESTS_PER_BATCH]
            for i in range(0, len(requests), MAX_REQUESTS_PER_BATCH)
        ]

        for batch_idx, sub_batch in enumerate(sub_batches):
            batch_label = f"[{batch_idx + 1}/{len(sub_batches)}] " if len(sub_batches) > 1 else ""
            print(f"  {batch_label}Submitting {len(sub_batch)} requests...", end="", flush=True)

            try:
                message_batch = client.messages.batches.create(requests=sub_batch)
                print(f" batch_id: {message_batch.id}")

                # Track this batch
                batch_info = {
                    "batch_id": message_batch.id,
                    "pdf_path": pdf_path,
                    "pdf_name": Path(pdf_path).name,
                    "total_pages": total_pages,
                    "requests_count": len(sub_batch),
                    "batch_index": batch_idx,
                    "total_sub_batches": len(sub_batches),
                    "status": "submitted",
                    "submitted_at": datetime.now().isoformat(),
                    "model": MODEL,
                }
                tracking["batches"].append(batch_info)
                save_batch_tracking(tracking)

            except Exception as e:
                print(f"\n  Error submitting batch: {e}")
                # Save what we have so far
                save_batch_tracking(tracking)
                print(f"\n  Progress saved. {len(tracking['batches'])} batches submitted so far.")
                print(f"  Fix the issue and re-run to continue from where we left off.")
                sys.exit(1)

    print(f"\nDone. Tracking file: {BATCH_TRACKING_FILE}")
    print("Run 'python3 scripts/ocr_anthropic.py status' to check progress")


def cmd_status(args):
    """Check status of all submitted batches."""
    try:
        import anthropic
    except ImportError:
        print("Error: pip3 install anthropic")
        sys.exit(1)

    tracking = load_batch_tracking()
    if not tracking["batches"]:
        print("No batches submitted yet.")
        return

    client = anthropic.Anthropic()

    print(f"{'Batch ID':<35} {'PDF':<25} {'Status':<15} {'Succeeded':>10} {'Errored':>8} {'Expired':>8}")
    print("-" * 110)

    for batch_info in tracking["batches"]:
        batch_id = batch_info["batch_id"]
        try:
            batch = client.messages.batches.retrieve(batch_id)
            batch_info["status"] = batch.processing_status
            counts = batch.request_counts

            status_display = batch.processing_status
            if batch.processing_status == "ended":
                if counts.errored == 0 and counts.expired == 0:
                    status_display = "ended (OK)"
                else:
                    status_display = "ended (issues)"

            print(
                f"{batch_id:<35} "
                f"{batch_info['pdf_name']:<25} "
                f"{status_display:<15} "
                f"{counts.succeeded:>10} "
                f"{counts.errored:>8} "
                f"{counts.expired:>8}"
            )
        except Exception as e:
            print(f"{batch_id:<35} {batch_info['pdf_name']:<25} ERROR: {e}")

    save_batch_tracking(tracking)


def cmd_collect(args):
    """Collect results from completed batches and write output JSON files."""
    try:
        import anthropic
    except ImportError:
        print("Error: pip3 install anthropic")
        sys.exit(1)

    tracking = load_batch_tracking()
    if not tracking["batches"]:
        print("No batches submitted yet.")
        return

    client = anthropic.Anthropic()

    for batch_info in tracking["batches"]:
        batch_id = batch_info["batch_id"]
        pdf_path = batch_info["pdf_path"]
        pdf_name = batch_info["pdf_name"]

        # Check if already collected
        if batch_info.get("collected"):
            if not args.force:
                print(f"Skipping {pdf_name} batch {batch_id}: already collected")
                continue

        # Check status
        try:
            batch = client.messages.batches.retrieve(batch_id)
        except Exception as e:
            print(f"Error retrieving {batch_id}: {e}")
            continue

        if batch.processing_status != "ended":
            print(f"Skipping {pdf_name} batch {batch_id}: status={batch.processing_status}")
            continue

        print(f"\nCollecting results for {pdf_name} batch {batch_id}...")
        counts = batch.request_counts
        print(f"  Succeeded: {counts.succeeded}, Errored: {counts.errored}, Expired: {counts.expired}")

        # Stream results
        # Collect all results indexed by page number
        results_by_page = {}
        error_count = 0

        for result in client.messages.batches.results(batch_id):
            custom_id = result.custom_id
            pdf_stem, page_num = parse_custom_id(custom_id)

            if result.result.type == "succeeded":
                message = result.result.message
                text = ""
                for block in message.content:
                    if hasattr(block, "text"):
                        text += block.text

                results_by_page[page_num] = {
                    "page": page_num,
                    "text": text,
                    "char_count": len(text),
                    "input_tokens": message.usage.input_tokens,
                    "output_tokens": message.usage.output_tokens,
                }
            elif result.result.type == "errored":
                error_count += 1
                error_msg = str(result.result.error) if hasattr(result.result, "error") else "unknown"
                results_by_page[page_num] = {
                    "page": page_num,
                    "text": f"ERROR: {error_msg}",
                    "char_count": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                }
            elif result.result.type == "expired":
                error_count += 1
                results_by_page[page_num] = {
                    "page": page_num,
                    "text": "ERROR: Request expired (24hr timeout)",
                    "char_count": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                }

        print(f"  Collected {len(results_by_page)} results ({error_count} errors)")

        # Find total pages for this PDF
        total_pages = batch_info.get("total_pages", 0)
        if not total_pages:
            for p, c in PDF_FILES:
                if pdf_path == p:
                    total_pages = c
                    break

        # Group into output files of PAGES_PER_OUTPUT_FILE pages each
        # Match the existing output file naming convention
        written_files = 0
        total_input_tokens = 0
        total_output_tokens = 0

        start = 1
        while start <= total_pages:
            end = min(start + PAGES_PER_OUTPUT_FILE - 1, total_pages)
            output_path = get_output_path(pdf_path, start, end)

            # Collect pages in this range
            pages_data = []
            for page_num in range(start, end + 1):
                if page_num in results_by_page:
                    page_result = results_by_page[page_num]
                    pages_data.append(page_result)
                    total_input_tokens += page_result.get("input_tokens", 0)
                    total_output_tokens += page_result.get("output_tokens", 0)

            if pages_data:
                # Write output file matching existing format
                output = {
                    "source_file": pdf_name,
                    "source_path": pdf_path,
                    "processed_date": datetime.now().isoformat(),
                    "model": MODEL,
                    "batch_id": batch_id,
                    "pages": sorted(pages_data, key=lambda p: p["page"]),
                    "total_pages": len(pages_data),
                    "total_time_sec": 0,  # Batch API doesn't give per-page timing
                }

                output_path.write_text(json.dumps(output, indent=2))
                written_files += 1

            start = end + 1

        # Calculate cost
        input_cost = total_input_tokens * 0.50 / 1_000_000  # Batch Haiku 4.5 input
        output_cost = total_output_tokens * 2.50 / 1_000_000  # Batch Haiku 4.5 output
        total_cost = input_cost + output_cost

        print(f"  Written {written_files} output files to {OCR_DIR}/")
        print(f"  Tokens: {total_input_tokens:,} input, {total_output_tokens:,} output")
        print(f"  Cost: ${total_cost:.2f} (input: ${input_cost:.2f}, output: ${output_cost:.2f})")

        # Mark as collected
        batch_info["collected"] = True
        batch_info["collected_at"] = datetime.now().isoformat()
        batch_info["results_count"] = len(results_by_page)
        batch_info["error_count"] = error_count
        batch_info["total_input_tokens"] = total_input_tokens
        batch_info["total_output_tokens"] = total_output_tokens
        batch_info["total_cost"] = round(total_cost, 4)
        save_batch_tracking(tracking)

    print("\nDone. Results written with 'anthropic_' prefix.")


def cmd_retry(args):
    """Find and retry errored pages using the standard Messages API."""
    try:
        import anthropic
        from pdf2image import convert_from_path
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Install with: pip3 install anthropic pdf2image Pillow")
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    import glob

    client = anthropic.Anthropic()

    # Find all errored pages in anthropic output files
    errors = []
    output_files = sorted(glob.glob(str(OCR_DIR / "anthropic_*.json")))
    output_files = [f for f in output_files if "batches" not in f]

    for filepath in output_files:
        with open(filepath) as fh:
            data = json.load(fh)
        for page in data["pages"]:
            if page["text"].startswith("ERROR"):
                errors.append({
                    "filepath": filepath,
                    "source_file": data["source_file"],
                    "source_path": data["source_path"],
                    "page": page["page"],
                })

    if not errors:
        print("No errored pages found. All pages successful!")
        return

    print(f"Found {len(errors)} errored page(s):")
    for e in errors:
        print(f"  {e['source_file']} page {e['page']}")

    if args.dry_run:
        return

    # Retry each errored page
    for e in errors:
        pdf_path = BASE_DIR / e["source_path"]
        page_num = e["page"]
        print(f"\nRetrying {e['source_file']} page {page_num}...", end="", flush=True)

        # Convert page to image
        images = convert_from_path(
            pdf_path,
            first_page=page_num,
            last_page=page_num,
            dpi=TARGET_DPI,
            size=TARGET_SIZE,
        )
        img_b64 = image_to_base64(images[0])

        # Send to API
        start_time = time.time()
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": img_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": USER_PROMPT,
                        },
                    ],
                }
            ],
        )
        elapsed = time.time() - start_time
        text = response.content[0].text

        print(f" OK ({len(text)} chars, {elapsed:.1f}s)")

        # Patch the output file
        with open(e["filepath"]) as fh:
            data = json.load(fh)

        for page in data["pages"]:
            if page["page"] == page_num:
                page["text"] = text
                page["char_count"] = len(text)
                page["input_tokens"] = response.usage.input_tokens
                page["output_tokens"] = response.usage.output_tokens
                break

        with open(e["filepath"], "w") as fh:
            json.dump(data, fh, indent=2)

        print(f"  Patched {e['filepath']}")

    print(f"\nDone. Retried {len(errors)} page(s).")


def main():
    parser = argparse.ArgumentParser(
        description="OCR processing using Anthropic Batch API with Claude Haiku 4.5"
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand")

    # test subcommand
    test_parser = subparsers.add_parser("test", help="Test OCR on a single page (Messages API)")
    test_parser.add_argument("--pdf", required=True, help="Path to PDF (relative to project root)")
    test_parser.add_argument("--page", type=int, default=100, help="Page number to test (default: 100)")

    # submit subcommand
    submit_parser = subparsers.add_parser("submit", help="Submit batch OCR requests")
    submit_parser.add_argument("--pdf", help="Process only this PDF (substring match)")
    submit_parser.add_argument("--start-page", type=int, help="Start page (default: 1)")
    submit_parser.add_argument("--end-page", type=int, help="End page (default: last)")
    submit_parser.add_argument("--dry-run", action="store_true", help="Show what would be submitted")
    submit_parser.add_argument("--force", action="store_true", help="Resubmit even if already submitted")

    # status subcommand
    status_parser = subparsers.add_parser("status", help="Check batch status")

    # collect subcommand
    collect_parser = subparsers.add_parser("collect", help="Collect batch results")
    collect_parser.add_argument("--force", action="store_true", help="Re-collect even if already done")

    # retry subcommand
    retry_parser = subparsers.add_parser("retry", help="Retry errored pages via Messages API")
    retry_parser.add_argument("--dry-run", action="store_true", help="Show errors without retrying")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Ensure output directory exists
    OCR_DIR.mkdir(parents=True, exist_ok=True)

    if args.command == "test":
        cmd_test(args)
    elif args.command == "submit":
        cmd_submit(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "collect":
        cmd_collect(args)
    elif args.command == "retry":
        cmd_retry(args)


if __name__ == "__main__":
    main()
