#!/usr/bin/env bash
# Daily BoS transcript pipeline: scrape → transcribe → commit → push
# Designed to be called from cron with flock for overlap protection.

set -euo pipefail

REPO=/home/radio/code/fredco-audit
PYTHON=/home/radio/Videos/Summit2025-Media/venv/bin/python
LOG=$REPO/data/bos_transcripts/pipeline.log

cd "$REPO"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

log "=== cron run start ==="

# Scrape for new meetings
log "scraping..."
$PYTHON scripts/bos_pipeline.py scrape >> "$LOG" 2>&1

# Transcribe pending (includes retry of stuck "downloading" states)
log "transcribing..."
$PYTHON scripts/bos_pipeline.py run --threads 14 >> "$LOG" 2>&1 || true

# Commit and push any new/changed transcripts
cd "$REPO"
CHANGED=$(git status --porcelain -- data/bos_transcripts/ | grep -c '' || true)

if [ "$CHANGED" -gt 0 ]; then
    log "committing $CHANGED changed transcript files..."
    git add data/bos_transcripts/
    git commit -m "Add BoS meeting transcripts (auto-pipeline $(date '+%Y-%m-%d'))"
    git push origin master >> "$LOG" 2>&1
    log "pushed to origin"
else
    log "no new transcripts to commit"
fi

log "=== cron run complete ==="
