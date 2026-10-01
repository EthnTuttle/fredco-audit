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

# Failed clips are not retried automatically, so make them visible in the log
# (a CDN change once left 11 meetings failed for 3 months with no warning).
# `|| true`: under pipefail a failing status would otherwise abort before commit.
FAILED=$($PYTHON scripts/bos_pipeline.py status 2>/dev/null | awk '$1=="failed"{print $2}' || true)
if [ "${FAILED:-0}" -gt 0 ]; then
    log "WARNING: $FAILED clip(s) in failed state — check 'bos_pipeline.py status', then 'run --retry-failed'"
fi

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
    # Audio is 200-700 MB per meeting and once bloated .git to 43 GB when a bare
    # `git add` swept it in. .gitignore keeps it out; don't also pass an
    # ':(exclude)' pathspec for it — naming an ignored path makes `git add` exit 1,
    # which under set -e silently killed every commit from 2026-08-13 on.
    # Instead, verify afterwards that nothing under audio/ got staged.
    git add -- data/bos_transcripts/
    if [ -n "$(git diff --cached --name-only -- data/bos_transcripts/audio)" ]; then
        git reset -q -- data/bos_transcripts/audio
        log "ERROR: audio files were staged despite .gitignore; unstaged them, aborting commit"
        exit 1
    fi
    git commit -m "Add BoS meeting transcripts (auto-pipeline $(date '+%Y-%m-%d'))"
    git push origin master >> "$LOG" 2>&1
    log "pushed to origin"
else
    log "no new transcripts to commit"
fi

log "=== cron run complete ==="
