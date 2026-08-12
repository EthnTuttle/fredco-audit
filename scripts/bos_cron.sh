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

# bos_pipeline.py already writes to $LOG via its own logging FileHandler, so
# redirecting its stdout here too wrote every line twice. Keep stderr (tracebacks
# and warnings bypass logging) and drop the duplicate stdout.

# Scrape for new meetings
log "scraping..."
$PYTHON scripts/bos_pipeline.py scrape >/dev/null 2>> "$LOG"

# Transcribe pending (includes retry of stuck "downloading" states)
log "transcribing..."
$PYTHON scripts/bos_pipeline.py run --threads 14 >/dev/null 2>> "$LOG" || true

# Commit and push any new/changed transcripts
cd "$REPO"
# pipeline.log changes on every run, so counting it here made CHANGED always
# non-zero and produced a daily empty "Add BoS transcripts" commit. Exclude it
# from the trigger only — the `git add` below still commits it alongside real
# transcripts, preserving the failure history it is tracked for.
CHANGED=$(git status --porcelain -- data/bos_transcripts/ \
    ':(exclude)data/bos_transcripts/audio' \
    ':(exclude)data/bos_transcripts/pipeline.log' | grep -c '' || true)

if [ "$CHANGED" -gt 0 ]; then
    log "committing $CHANGED changed transcript files..."
    # Explicit exclude as well as .gitignore: audio is 200-700 MB per meeting and
    # once bloated .git to 43 GB when a bare `git add` swept it in.
    git add -- data/bos_transcripts/ ':(exclude)data/bos_transcripts/audio'
    git commit -m "Add BoS meeting transcripts (auto-pipeline $(date '+%Y-%m-%d'))"
    git push origin master >> "$LOG" 2>&1
    log "pushed to origin"
else
    log "no new transcripts to commit"
fi

log "=== cron run complete ==="
