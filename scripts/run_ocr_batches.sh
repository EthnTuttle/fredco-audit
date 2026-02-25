#!/bin/bash
# GPU OCR batch processing - runs alongside CPU script
# Processes DIFFERENT PDFs than the CPU script to avoid conflicts
#
# GPU script handles: 2021, 2023, 2025 (14,133 pages)
# CPU script handles: 2022, 2024 (9,453 pages)
#
# Run from project root: ./scripts/run_ocr_batches.sh
#
# To run both in parallel:
#   ./scripts/run_ocr_batches.sh &   # GPU - 2021, 2023, 2025
#   ./scripts/run_ocr_cpu.sh &       # CPU - 2022, 2024
#
# To monitor: tail -f data/processed/ocr/*.log

set -e

cd "$(dirname "$0")/.."
source .venv/bin/activate

BATCH_SIZE=100
OUTPUT_DIR="data/processed/ocr"
LOG_FILE="${OUTPUT_DIR}/ocr_gpu_progress.log"

mkdir -p "$OUTPUT_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [GPU] $1" | tee -a "$LOG_FILE"
}

# Process a single PDF in batches
process_pdf() {
    local pdf="$1"
    local total_pages="$2"
    local name=$(basename "$pdf" .pdf | tr ' ' '_')
    local pdf_log="${OUTPUT_DIR}/${name}_gpu.log"
    
    log "Starting $name ($total_pages pages) -> $pdf_log"
    
    local start=1
    while [ $start -le $total_pages ]; do
        end=$((start + BATCH_SIZE - 1))
        if [ $end -gt $total_pages ]; then
            end=$total_pages
        fi
        
        # Check if batch already processed (by either GPU or CPU)
        batch_file="${OUTPUT_DIR}/${name}_pages_${start}-${end}.json"
        lock_file="${OUTPUT_DIR}/${name}_pages_${start}-${end}.lock"
        
        if [ -f "$batch_file" ]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Skipping pages $start-$end (exists)" >> "$pdf_log"
            start=$((end + 1))
            continue
        fi
        
        # Check for lock file (another process working on this batch)
        if [ -f "$lock_file" ]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Skipping pages $start-$end (locked)" >> "$pdf_log"
            start=$((end + 1))
            continue
        fi
        
        # Create lock file
        echo "$$" > "$lock_file"
        
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Processing pages $start-$end (GPU)..." >> "$pdf_log"
        
        # Run OCR
        if python scripts/ocr_with_glm.py \
            --input "$pdf" \
            --pages "$start-$end" \
            --context frederick-tax \
            --output "$OUTPUT_DIR" >> "$pdf_log" 2>&1; then
            
            # Rename output to include page range
            local base_name=$(basename "$pdf" .pdf)
            temp_file="${OUTPUT_DIR}/${base_name}_ocr.json"
            if [ -f "$temp_file" ]; then
                mv "$temp_file" "$batch_file"
                echo "[$(date '+%Y-%m-%d %H:%M:%S')] Saved: $batch_file" >> "$pdf_log"
            fi
        else
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR processing pages $start-$end" >> "$pdf_log"
        fi
        
        # Remove lock file
        rm -f "$lock_file"
        
        start=$((end + 1))
    done
    
    log "Completed $name"
}

# Main
log "=========================================="
log "Starting GPU OCR batch processing"
log "Batch size: $BATCH_SIZE pages"
log "Output dir: $OUTPUT_DIR"
log "=========================================="

# GPU handles: 2021, 2023, and 2025 tax books
# (CPU script handles 2022, 2024)
PDFS="data/raw/real-estate/Real Estate 2021 Tax Book.pdf|4576
data/raw/real-estate/RE 2023 Book.pdf|4700
data/raw/real-estate/RE_2025_Book.pdf|4857"

# Process PDFs sequentially
echo "$PDFS" | while IFS='|' read -r pdf pages; do
    if [ -n "$pdf" ] && [ -n "$pages" ]; then
        process_pdf "$pdf" "$pages"
    fi
done

log "=========================================="
log "GPU OCR processing complete!"
log "=========================================="
