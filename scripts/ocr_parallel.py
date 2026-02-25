#!/usr/bin/env python3
"""
Parallel OCR processing using multiple workers and model variants.

Uses both glm-ocr:latest (GPU/F16) and glm-ocr:q8_0 (CPU/Q8) models
with configurable parallelism via Ollama's OLLAMA_NUM_PARALLEL setting.

Features:
- Dynamic work queue with all PDFs and page batches
- File-based pause/resume control
- Graceful shutdown on Ctrl+C
- Resumable (skips completed batches)
- Progress display

Control files (in data/processed/ocr/):
- PAUSE: Touch to pause after current batches, remove to resume
- STOP: Touch to stop after current batches complete

Usage:
    python scripts/ocr_parallel.py --workers 6
    python scripts/ocr_parallel.py --workers 6 --dry-run  # Test without processing

To pause:   touch data/processed/ocr/PAUSE
To resume:  rm data/processed/ocr/PAUSE
To stop:    touch data/processed/ocr/STOP
"""

import argparse
import base64
import json
import multiprocessing as mp
import os
import re
import signal
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from queue import Empty
from typing import Any, Optional

import requests
from pdf2image import convert_from_path
from PIL import Image

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
OCR_DIR = PROCESSED_DIR / "ocr"

# Control files
PAUSE_FILE = OCR_DIR / "PAUSE"
STOP_FILE = OCR_DIR / "STOP"

# Ollama API endpoint
OLLAMA_API = "http://localhost:11434/api/chat"

# Target image size for GLM-OCR
TARGET_IMAGE_SIZE = (850, 1100)

# Timeout for Ollama API calls (10 minutes)
OLLAMA_TIMEOUT = 600

# Models - use F16 only (Q8 has GGML assertion errors with images)
# glm-ocr:q8_0 crashes with: GGML_ASSERT(a->ne[2] * 4 == b->ne[0]) failed
MODEL_F16 = "glm-ocr:latest"  # F16 (2.2GB) - works correctly
MODEL_Q8 = "glm-ocr:latest"   # Use F16 for both since Q8 is broken

# Batch size (pages per batch) - smaller batches = faster completion feedback
BATCH_SIZE = 50

# PDF files with page counts
PDF_FILES = [
    ("data/raw/real-estate/Real Estate 2021 Tax Book.pdf", 4576),
    ("data/raw/real-estate/Real Estate 2022 Tax Book.pdf", 4645),
    ("data/raw/real-estate/RE 2023 Book.pdf", 4700),
    ("data/raw/real-estate/RE_Book_2024.pdf", 4808),
    ("data/raw/real-estate/RE_2025_Book.pdf", 4857),
]

# OCR corrections
OCR_CORRECTIONS = {
    r"PREBRIICK": "FREDERICK",
    r"PREDERICK": "FREDERICK",
    r"PREBERRICK": "FREDERICK",
    r"PREDERCK": "FREDERICK",
    r"FREDRICK": "FREDERICK",
    r"WINNEBER": "WINCHESTER",
    r"WINNCESTER": "WINCHESTER",
    r"\bEN\s+(RA|RP|R4|R5|M1|B1|B2)\b": r"ZN \1",
}

# Context for Frederick County tax documents
CONTEXT_HINT = "This document is from Frederick County, Virginia. The text uses tight character spacing."


def apply_corrections(text: str) -> str:
    """Apply known OCR corrections to text."""
    for pattern, replacement in OCR_CORRECTIONS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def image_to_base64(image: Image.Image) -> str:
    """Convert PIL Image to base64 string."""
    import io
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def process_page_with_ollama(image: Image.Image, model: str) -> tuple[str, float]:
    """Process a single page image with Ollama OCR."""
    start_time = time.time()
    
    # Resize image if needed
    if image.size != TARGET_IMAGE_SIZE:
        image = image.resize(TARGET_IMAGE_SIZE, Image.Resampling.LANCZOS)
    
    # Convert to base64
    img_base64 = image_to_base64(image)
    
    # Build prompt
    prompt = f"{CONTEXT_HINT}\n\nText Recognition:"
    
    # Make API request
    # Use smaller context window to reduce memory usage (4096 is plenty for OCR)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [img_base64],
            }
        ],
        "stream": False,
        "options": {
            "num_ctx": 4096,  # Small context window - OCR doesn't need much
        },
    }
    
    try:
        response = requests.post(OLLAMA_API, json=payload, timeout=OLLAMA_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        text = result.get("message", {}).get("content", "")
        text = apply_corrections(text)
        elapsed = time.time() - start_time
        return text, elapsed
    except Exception as e:
        elapsed = time.time() - start_time
        return f"ERROR: {str(e)}", elapsed


def get_batch_output_path(pdf_path: str, start_page: int, end_page: int) -> Path:
    """Get the output path for a batch."""
    name = Path(pdf_path).stem.replace(" ", "_")
    return OCR_DIR / f"{name}_pages_{start_page}-{end_page}.json"


def get_batch_lock_path(pdf_path: str, start_page: int, end_page: int) -> Path:
    """Get the lock file path for a batch."""
    name = Path(pdf_path).stem.replace(" ", "_")
    return OCR_DIR / f"{name}_pages_{start_page}-{end_page}.lock"


def is_batch_complete(pdf_path: str, start_page: int, end_page: int) -> bool:
    """Check if a batch has already been processed."""
    return get_batch_output_path(pdf_path, start_page, end_page).exists()


def is_batch_locked(pdf_path: str, start_page: int, end_page: int) -> bool:
    """Check if a batch is currently being processed."""
    return get_batch_lock_path(pdf_path, start_page, end_page).exists()


def generate_work_queue() -> list[tuple[str, int, int, int]]:
    """Generate list of all batches to process: (pdf_path, start, end, total_pages)."""
    batches = []
    for pdf_path, total_pages in PDF_FILES:
        start = 1
        while start <= total_pages:
            end = min(start + BATCH_SIZE - 1, total_pages)
            if not is_batch_complete(pdf_path, start, end):
                batches.append((pdf_path, start, end, total_pages))
            start = end + 1
    return batches


def process_batch(pdf_path: str, start_page: int, end_page: int, model: str, worker_id: int) -> dict:
    """Process a batch of pages from a PDF."""
    output_path = get_batch_output_path(pdf_path, start_page, end_page)
    lock_path = get_batch_lock_path(pdf_path, start_page, end_page)
    
    # Skip if already done
    if output_path.exists():
        return {"status": "skipped", "reason": "already_complete"}
    
    # Skip if locked by another worker
    if lock_path.exists():
        return {"status": "skipped", "reason": "locked"}
    
    # Create lock file
    try:
        lock_path.write_text(f"{worker_id}")
    except Exception as e:
        return {"status": "error", "reason": f"lock_failed: {e}"}
    
    try:
        # Convert PDF pages to images
        pdf_full_path = BASE_DIR / pdf_path
        images = convert_from_path(
            pdf_full_path,
            first_page=start_page,
            last_page=end_page,
            dpi=200,
            size=TARGET_IMAGE_SIZE,
        )
        
        pages_data = []
        total_time = 0
        
        for i, image in enumerate(images):
            page_num = start_page + i
            text, elapsed = process_page_with_ollama(image, model)
            total_time += elapsed
            
            pages_data.append({
                "page": page_num,
                "text": text,
                "char_count": len(text),
                "processing_time_sec": round(elapsed, 2),
            })
        
        # Save results
        result = {
            "source_file": Path(pdf_path).name,
            "source_path": pdf_path,
            "processed_date": datetime.now().isoformat(),
            "model": model,
            "worker_id": worker_id,
            "pages": pages_data,
            "total_pages": len(pages_data),
            "total_time_sec": round(total_time, 2),
        }
        
        output_path.write_text(json.dumps(result, indent=2))
        
        return {
            "status": "success",
            "pages": len(pages_data),
            "time": round(total_time, 2),
            "output": str(output_path),
        }
        
    except Exception as e:
        return {"status": "error", "reason": str(e)}
    
    finally:
        # Remove lock file
        try:
            lock_path.unlink()
        except:
            pass


def worker_process(worker_id: int, model: str, task_queue: mp.Queue, result_queue: mp.Queue, shutdown_event: mp.Event):
    """Worker process that pulls tasks from queue and processes them."""
    print(f"    Worker {worker_id} started in process {os.getpid()}", flush=True)
    try:
        _worker_loop(worker_id, model, task_queue, result_queue, shutdown_event)
    except Exception as e:
        print(f"    Worker {worker_id} crashed: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        result_queue.put({"worker_id": worker_id, "status": "shutdown"})
        print(f"    Worker {worker_id} exiting", flush=True)


def _worker_loop(worker_id: int, model: str, task_queue: mp.Queue, result_queue: mp.Queue, shutdown_event: mp.Event):
    """Inner worker loop."""
    while not shutdown_event.is_set():
        # Check for pause
        while PAUSE_FILE.exists() and not shutdown_event.is_set():
            time.sleep(1)
        
        # Check for stop
        if STOP_FILE.exists():
            break
        
        try:
            task = task_queue.get(timeout=1)
        except Empty:
            continue
        
        if task is None:  # Poison pill
            break
        
        pdf_path, start_page, end_page, total_pages = task
        
        result = process_batch(pdf_path, start_page, end_page, model, worker_id)
        result["worker_id"] = worker_id
        result["model"] = model
        result["pdf"] = Path(pdf_path).name
        result["pages_range"] = f"{start_page}-{end_page}"
        
        result_queue.put(result)


def configure_ollama(num_parallel: int, max_loaded_models: int = 2):
    """Configure Ollama environment variables."""
    os.environ["OLLAMA_NUM_PARALLEL"] = str(num_parallel)
    os.environ["OLLAMA_MAX_LOADED_MODELS"] = str(max_loaded_models)
    print(f"Ollama configured: OLLAMA_NUM_PARALLEL={num_parallel}, OLLAMA_MAX_LOADED_MODELS={max_loaded_models}")


def preload_models():
    """Preload both models into Ollama memory using the generate endpoint."""
    print("Preloading models...", flush=True)
    
    # Use the generate endpoint with keep_alive to load models without actually generating
    generate_url = "http://localhost:11434/api/generate"
    
    for model in [MODEL_F16, MODEL_Q8]:
        try:
            # Just load the model without generating anything
            # Use small context window to reduce memory usage
            payload = {
                "model": model,
                "prompt": "",
                "keep_alive": "10m",  # Keep model loaded for 10 minutes
                "options": {
                    "num_ctx": 4096,  # Small context window for OCR
                },
            }
            response = requests.post(generate_url, json=payload, timeout=30)
            if response.status_code == 200:
                print(f"  {model}: loaded", flush=True)
            else:
                print(f"  {model}: failed to load ({response.status_code})", flush=True)
        except Exception as e:
            print(f"  {model}: error loading - {e}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Parallel OCR processing with multiple workers")
    parser.add_argument("--workers", "-w", type=int, default=6, help="Number of workers (default: 6)")
    parser.add_argument("--parallel", "-p", type=int, default=6, help="Ollama parallel requests per model (default: 6)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without doing it")
    parser.add_argument("--no-preload", action="store_true", help="Skip preloading models")
    args = parser.parse_args()
    
    # Ensure output directory exists
    OCR_DIR.mkdir(parents=True, exist_ok=True)
    
    # Remove old control files
    if PAUSE_FILE.exists():
        PAUSE_FILE.unlink()
    if STOP_FILE.exists():
        STOP_FILE.unlink()
    
    # Configure Ollama
    configure_ollama(args.parallel, max_loaded_models=2)
    
    # Generate work queue
    batches = generate_work_queue()
    
    if not batches:
        print("No batches to process - all complete!")
        return
    
    total_pages = sum(end - start + 1 for _, start, end, _ in batches)
    print(f"\nWork queue: {len(batches)} batches, ~{total_pages} pages remaining")
    print(f"Workers: {args.workers} ({args.workers // 2} on {MODEL_F16}, {args.workers - args.workers // 2} on {MODEL_Q8})")
    
    if args.dry_run:
        print("\nDry run - batches that would be processed:")
        for pdf, start, end, total in batches[:10]:
            print(f"  {Path(pdf).name}: pages {start}-{end}")
        if len(batches) > 10:
            print(f"  ... and {len(batches) - 10} more")
        return
    
    # Preload models
    if not args.no_preload:
        preload_models()
    
    print(f"\nStarting {args.workers} workers...", flush=True)
    print("Control: touch PAUSE to pause, touch STOP to stop, Ctrl+C for immediate stop", flush=True)
    print("-" * 60, flush=True)
    
    # Create queues and events
    task_queue = mp.Queue()
    result_queue = mp.Queue()
    shutdown_event = mp.Event()
    
    # Fill task queue
    for batch in batches:
        task_queue.put(batch)
    
    # Add poison pills
    for _ in range(args.workers):
        task_queue.put(None)
    
    # Assign models to workers (half F16, half Q8)
    worker_models = []
    for i in range(args.workers):
        if i < args.workers // 2:
            worker_models.append(MODEL_F16)
        else:
            worker_models.append(MODEL_Q8)
    
    # Start workers
    workers = []
    for i in range(args.workers):
        model = worker_models[i]
        p = mp.Process(target=worker_process, args=(i, model, task_queue, result_queue, shutdown_event))
        p.start()
        workers.append(p)
        print(f"  Worker {i}: {model}", flush=True)
    
    # Handle Ctrl+C
    def signal_handler(sig, frame):
        print("\n\nShutting down gracefully (waiting for current batches)...")
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Monitor progress
    completed = 0
    errors = 0
    active_workers = args.workers
    start_time = time.time()
    
    try:
        while active_workers > 0:
            try:
                result = result_queue.get(timeout=1)
            except Empty:
                continue
            
            if result.get("status") == "shutdown":
                active_workers -= 1
                continue
            
            if result.get("status") == "success":
                completed += 1
                elapsed = time.time() - start_time
                rate = completed / elapsed * 3600 if elapsed > 0 else 0
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"Worker {result['worker_id']} ({result['model'].split(':')[1]}): "
                      f"{result['pdf']} p{result['pages_range']} - "
                      f"{result['pages']} pages in {result['time']}s "
                      f"[{completed}/{len(batches)} batches, {rate:.0f}/hr]")
            
            elif result.get("status") == "error":
                errors += 1
                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"Worker {result['worker_id']} ERROR: {result.get('reason', 'unknown')}")
            
            elif result.get("status") == "skipped":
                pass  # Normal skip
    
    except KeyboardInterrupt:
        shutdown_event.set()
    
    # Wait for workers
    for p in workers:
        p.join(timeout=5)
        if p.is_alive():
            p.terminate()
    
    # Summary
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("Processing complete!")
    print(f"  Completed: {completed} batches")
    print(f"  Errors: {errors}")
    print(f"  Time: {elapsed/60:.1f} minutes")
    print(f"  Rate: {completed/elapsed*3600:.0f} batches/hour" if elapsed > 0 else "")
    print("=" * 60)


if __name__ == "__main__":
    main()
