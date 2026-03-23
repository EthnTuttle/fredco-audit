#!/usr/bin/env python3
"""
Frederick County BoS Meeting Transcription Pipeline
====================================================
Scrapes the Granicus video archive for Frederick County, VA, downloads audio
from each meeting, transcribes it with OpenAI Whisper, and saves structured
transcripts. Audio files are deleted immediately after transcription to keep
storage requirements minimal.

The pipeline is interruptible and fully resumable: state is tracked in a
SQLite database, so re-running after a crash or network outage picks up
exactly where it left off.

Architecture: Producer-Consumer
--------------------------------
Download and transcription run on separate threads so that CPU is never idle
waiting for a download to finish, and the network is never idle waiting for
transcription to finish.

    ┌─────────────────────┐       queue        ┌──────────────────────┐
    │   Download Thread   │ ──(audio path)───► │  Transcribe Thread   │
    │  (network-bound)    │                    │  (CPU-bound)         │
    │  yt-dlp → .m4a      │   bounded by       │  Whisper → .json/.txt│
    │  staging/           │   --prefetch N     │  delete audio after  │
    └─────────────────────┘                    └──────────────────────┘

The queue is bounded by --prefetch (default 2): the download thread will
block once N audio files are queued, preventing unbounded disk use.

Usage
-----
# Step 1: Populate the meeting index (safe to re-run to pick up new meetings)
    python scripts/bos_pipeline.py scrape

# Step 2: Process all pending meetings (download overlaps with transcription)
    python scripts/bos_pipeline.py run

# Check progress at any time
    python scripts/bos_pipeline.py status

# Test on a single meeting before a full run
    python scripts/bos_pipeline.py run --limit 1 --dry-run

# Retry previously failed meetings
    python scripts/bos_pipeline.py run --retry-failed

Full option reference
---------------------
    python scripts/bos_pipeline.py --help
    python scripts/bos_pipeline.py run --help

Output
------
Transcripts are written to  data/bos_transcripts/<date>_clip<id>_<title>/
  transcript.json  — full Whisper output with per-segment timestamps
  transcript.txt   — plain-text transcript for human reading / LLM ingestion

Pipeline state is stored in  data/bos_transcripts/pipeline.db  (SQLite).
Pre-fetched audio is staged in  data/bos_transcripts/.staging/  (auto-cleaned).

Requirements
------------
    pip install openai-whisper yt-dlp requests beautifulsoup4
    # ffmpeg must be on PATH (used by Whisper for audio decoding)

Notes
-----
- Whisper large-v3 model (~1.5 GB) is downloaded on first use and cached in
  ~/.cache/whisper by default.
- Audio is downloaded as m4a (audio-only stream) to minimise bandwidth and
  storage. The staging file is deleted once transcription completes.
- yt-dlp uses the public Granicus HLS stream; no login is required.
- Thread count controls Whisper CPU threads AND PyTorch intraop threads.
  8 threads is a sensible default on a 24-core machine; reduce if you need
  the machine to stay fully responsive. The download thread uses negligible CPU.
- --prefetch controls how many audio files are queued ahead of transcription.
  Each file is ~50–200 MB; prefetch=2 caps staging at ~400 MB max.
"""

import argparse
import json
import logging
import queue
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent.parent
TRANSCRIPT_DIR = BASE_DIR / "data" / "bos_transcripts"
DB_PATH = TRANSCRIPT_DIR / "pipeline.db"
LOG_PATH = TRANSCRIPT_DIR / "pipeline.log"

GRANICUS_ARCHIVE_URL = "https://fcva.granicus.com/ViewPublisher.php?view_id=1"
GRANICUS_PLAYER_BASE = "https://fcva.granicus.com/MediaPlayer.php?view_id=1&clip_id={clip_id}"

# Meetings before this date (inclusive cutoff) are ignored
CUTOFF_DATE = date(2020, 1, 1)

# Default Whisper settings
DEFAULT_MODEL = "large-v3"
DEFAULT_THREADS = 8

# HTTP headers to avoid bot-detection blocks
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure root logger to write to both console and a log file."""
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ]
    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, handlers=handlers)
    return logging.getLogger(__name__)


log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def init_db(db_path: Path) -> sqlite3.Connection:
    """
    Open (or create) the pipeline SQLite database and ensure the schema exists.

    Table: meetings
        clip_id     — Granicus clip ID (integer primary key)
        title       — Meeting name as shown on the archive page
        meeting_date — ISO-8601 date string (YYYY-MM-DD)
        meeting_url — Full player URL
        status      — One of: pending / downloading / transcribing / done / failed
        error       — Last error message if status=failed, else NULL
        output_dir  — Relative path to transcript directory once done
        scraped_at  — When this row was first inserted
        updated_at  — When this row was last modified
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # safe for concurrent reads
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            clip_id      INTEGER PRIMARY KEY,
            title        TEXT    NOT NULL,
            meeting_date TEXT    NOT NULL,
            meeting_url  TEXT    NOT NULL,
            status       TEXT    NOT NULL DEFAULT 'pending',
            error        TEXT,
            output_dir   TEXT,
            scraped_at   TEXT    NOT NULL,
            updated_at   TEXT    NOT NULL
        )
    """)
    conn.commit()
    return conn


def upsert_meeting(conn: sqlite3.Connection, clip_id: int, title: str,
                   meeting_date: str, meeting_url: str) -> bool:
    """
    Insert a meeting row if it does not exist; skip if it already does.

    Returns True if a new row was inserted, False if it already existed.
    """
    now = datetime.utcnow().isoformat()
    cursor = conn.execute(
        "SELECT clip_id FROM meetings WHERE clip_id = ?", (clip_id,)
    )
    if cursor.fetchone():
        return False
    conn.execute(
        """INSERT INTO meetings (clip_id, title, meeting_date, meeting_url,
                                  status, scraped_at, updated_at)
           VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
        (clip_id, title, meeting_date, meeting_url, now, now),
    )
    conn.commit()
    return True


def set_status(conn: sqlite3.Connection, clip_id: int, status: str,
               error: Optional[str] = None, output_dir: Optional[str] = None) -> None:
    """Update the status (and optionally error/output_dir) for a meeting."""
    now = datetime.utcnow().isoformat()
    conn.execute(
        """UPDATE meetings
           SET status = ?, error = ?, output_dir = COALESCE(?, output_dir),
               updated_at = ?
           WHERE clip_id = ?""",
        (status, error, output_dir, now, clip_id),
    )
    conn.commit()


def _export_pipeline_status_csv() -> None:
    """Overwrite pipeline_status.csv with the current state of all meetings."""
    csv_path = TRANSCRIPT_DIR / "pipeline_status.csv"
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT clip_id, meeting_date, title, status, error, output_dir, updated_at "
            "FROM meetings ORDER BY clip_id"
        ).fetchall()
        with open(csv_path, "w", newline="") as f:
            import csv as csv_mod
            writer = csv_mod.writer(f)
            writer.writerow(["clip_id", "meeting_date", "title", "status",
                              "error", "output_dir", "updated_at"])
            writer.writerows(rows)
    finally:
        conn.close()


def _git_commit_transcript(out_dir: Path, clip_id: int,
                            meeting_date: str, title: str) -> None:
    """
    Commit and push the just-completed transcript plus updated pipeline state.

    Failures are logged as warnings but never raised — a git problem must
    never interrupt the transcription pipeline.
    """
    try:
        _export_pipeline_status_csv()

        files_to_add = [
            str(out_dir),
            str(DB_PATH),
            str(TRANSCRIPT_DIR / "pipeline_status.csv"),
            str(TRANSCRIPT_DIR / "pipeline.log"),
        ]

        subprocess.run(
            ["git", "add"] + files_to_add,
            cwd=BASE_DIR, check=True, capture_output=True,
        )

        msg = f"Add BoS transcript: {meeting_date} clip{clip_id} {title}"
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=BASE_DIR, check=True, capture_output=True,
        )

        subprocess.run(
            ["git", "push"],
            cwd=BASE_DIR, check=True, capture_output=True,
        )

        log.info("[git] Committed and pushed: %s", msg)

    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="replace").strip() if exc.stderr else ""
        log.warning("[git] git operation failed (clip %d): %s", clip_id, stderr or exc)
    except Exception as exc:
        log.warning("[git] Unexpected error during commit (clip %d): %s", clip_id, exc)


def get_pending(conn: sqlite3.Connection,
                include_failed: bool = False) -> list[sqlite3.Row]:
    """
    Return meetings that still need processing, ordered by date ascending
    (oldest first so the transcript corpus grows chronologically).
    """
    statuses = ("pending", "downloading", "transcribing")
    if include_failed:
        statuses = statuses + ("failed",)
    placeholders = ",".join("?" * len(statuses))
    return conn.execute(
        f"SELECT * FROM meetings WHERE status IN ({placeholders}) "
        f"ORDER BY meeting_date ASC",
        statuses,
    ).fetchall()


def get_summary(conn: sqlite3.Connection) -> dict:
    """Return a dict of status → count for the status subcommand."""
    rows = conn.execute(
        "SELECT status, COUNT(*) as n FROM meetings GROUP BY status"
    ).fetchall()
    return {r["status"]: r["n"] for r in rows}

# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def _parse_meeting_date(raw: str) -> Optional[str]:
    """
    Convert a Granicus date string like 'March 11, 2026' or 'February  4, 2026'
    into an ISO-8601 date string (YYYY-MM-DD).  Returns None if parsing fails.
    """
    # Collapse multiple spaces (Granicus sometimes has 'February  4')
    raw = re.sub(r"\s+", " ", raw).strip()
    # Strip the time portion if present (e.g. '- 5:19 PM')
    raw = re.sub(r"\s*-\s*\d+:\d+\s*(AM|PM).*$", "", raw).strip()
    for fmt in ("%B %d, %Y", "%B %d %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _safe_dirname(title: str) -> str:
    """Strip characters that are unsafe in directory names."""
    return re.sub(r"[^\w\-]", "_", title)[:60].strip("_")


def cmd_scrape(args) -> None:
    """
    Fetch the Granicus archive page and insert every meeting since
    CUTOFF_DATE into the pipeline database.

    How Granicus renders the archive
    ---------------------------------
    Each meeting row is a <tr> with cells:
        td[0]  Meeting title (e.g. "Board of Supervisors")
        td[1]  Date string with &nbsp; separators (e.g. "March\xa011,\xa02026")
        td[2]  Agenda link (optional)
        td[3]  eComment link (optional)
        td[4]  "Video" link — href is "javascript:void(0);" but onclick contains
               window.open('//fcva.granicus.com/MediaPlayer.php?view_id=1&clip_id=NNN',...)

    We scrape clip IDs from those onclick attributes and build the player URL
    explicitly, which yt-dlp can resolve via its generic HLS extractor.
    """
    conn = init_db(DB_PATH)
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    log.info("Fetching Granicus archive: %s", GRANICUS_ARCHIVE_URL)
    resp = session.get(GRANICUS_ARCHIVE_URL, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    inserted = 0
    already_in_db = 0
    too_old = 0
    parse_errors = 0

    # Find every "Video" link whose onclick reveals a clip_id
    for link in soup.find_all("a", onclick=re.compile(r"clip_id=\d+")):
        onclick = str(link.get("onclick") or "")
        m = re.search(r"clip_id=(\d+)", onclick)
        if not m:
            continue
        clip_id = int(m.group(1))

        # Walk up to the enclosing <tr>
        row = link.find_parent("tr")
        if not row:
            log.debug("clip %d: no parent <tr> found", clip_id)
            parse_errors += 1
            continue

        cells = row.find_all("td")
        if len(cells) < 2:
            log.debug("clip %d: too few cells (%d)", clip_id, len(cells))
            parse_errors += 1
            continue

        # td[0] = meeting title; replace non-breaking spaces, collapse whitespace
        title = re.sub(r"\s+", " ", cells[0].get_text(separator=" ")).strip()
        if not title:
            title = f"Meeting {clip_id}"

        # td[1] = date; \xa0 is &nbsp; used instead of regular spaces by Granicus
        raw_date = cells[1].get_text(separator=" ").replace("\xa0", " ")
        meeting_date = _parse_meeting_date(raw_date)

        if not meeting_date:
            log.debug(
                "clip %d (%s): could not parse date from %r",
                clip_id, title, raw_date,
            )
            parse_errors += 1
            continue

        # Filter out meetings before the cutoff date
        if date.fromisoformat(meeting_date) < CUTOFF_DATE:
            too_old += 1
            continue

        player_url = GRANICUS_PLAYER_BASE.format(clip_id=clip_id)
        was_new = upsert_meeting(conn, clip_id, title, meeting_date, player_url)
        if was_new:
            inserted += 1
            log.debug("  + %s  clip %-4d  %s", meeting_date, clip_id, title)
        else:
            already_in_db += 1

    log.info(
        "Scrape complete: %d new meetings inserted, %d already in DB, "
        "%d before %s (ignored), %d parse errors",
        inserted, already_in_db, too_old, CUTOFF_DATE.isoformat(), parse_errors,
    )
    conn.close()

# ---------------------------------------------------------------------------
# Processing: download → transcribe → save → purge audio
# ---------------------------------------------------------------------------

# Global flag: set by SIGINT/SIGTERM handler to allow graceful shutdown
_shutdown = False

def _handle_signal(signum, frame):
    """Allow Ctrl-C / SIGTERM to finish the current meeting then stop."""
    global _shutdown
    if not _shutdown:
        log.warning(
            "Interrupt received — finishing current meeting then stopping. "
            "Press Ctrl-C again to force-quit."
        )
        _shutdown = True
    else:
        log.warning("Force-quit requested.")
        sys.exit(1)


def _download_audio(clip_id: int, player_url: str, dest: Path,
                    rate_limit: Optional[str]) -> Path:
    """
    Use yt-dlp to extract the best audio stream from a Granicus clip and
    save it as an m4a file.

    Each clip gets its own isolated subdirectory inside *dest* so that
    parallel downloads never share a working directory and their HLS fragment
    temp files cannot collide.

    Returns the path of the downloaded file.

    Raises RuntimeError on failure.
    """
    import subprocess
    # Isolate every clip in its own subdir to prevent HLS temp-file collisions
    # when multiple yt-dlp processes run in parallel.
    clip_dir = dest / f"clip{clip_id}"
    clip_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(clip_dir / f"clip{clip_id}.%(ext)s")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-x",                          # extract audio only
        "--audio-format", "m4a",
        "--audio-quality", "0",        # best quality
        "--no-progress",               # clean log output
        "--no-warnings",
        "--retries", "25",             # retry HTTP errors (default 10)
        "--fragment-retries", "25",    # retry individual HLS fragment errors
        "--retry-sleep", "exp=1:30",   # exponential backoff: 1s, 2s, 4s … capped at 30s
        "-o", output_template,
        player_url,
    ]
    if rate_limit:
        cmd += ["--limit-rate", rate_limit]

    log.debug("yt-dlp command: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"yt-dlp failed (exit {result.returncode}): {result.stderr.strip()}"
        )

    # Find the downloaded file (extension may vary)
    candidates = list(clip_dir.glob(f"clip{clip_id}.*"))
    if not candidates:
        raise FileNotFoundError(
            f"yt-dlp reported success but no audio file found in {clip_dir}"
        )
    return candidates[0]


def _transcribe(audio_path: Path, model_name: str, threads: int) -> dict:
    """
    Transcribe *audio_path* using OpenAI Whisper and return the raw result dict.

    The result contains:
        text     — full transcript as a single string
        segments — list of dicts with start/end times and per-segment text
        language — detected language code

    Thread count is set on both PyTorch and the Whisper model to respect
    the user's CPU limit.
    """
    import torch
    import whisper

    torch.set_num_threads(threads)

    log.info("Loading Whisper model '%s' …", model_name)
    model = whisper.load_model(model_name)

    log.info("Transcribing %s …", audio_path.name)
    result = model.transcribe(
        str(audio_path),
        language="en",
        fp16=False,        # CPU-safe; GPU users can set this to True
        verbose=False,
    )
    return result


def _save_transcript(result: dict, out_dir: Path, meeting: sqlite3.Row) -> None:
    """
    Persist the Whisper output in two formats:

    transcript.json
        Full structured output: metadata + per-segment timestamps.

    transcript.txt
        Plain-text transcript for human reading and LLM ingestion.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- JSON (structured, with timestamps) ---
    payload = {
        "meta": {
            "clip_id": meeting["clip_id"],
            "title": meeting["title"],
            "meeting_date": meeting["meeting_date"],
            "meeting_url": meeting["meeting_url"],
            "transcribed_at": datetime.utcnow().isoformat(),
            "whisper_language": result.get("language", "en"),
        },
        "transcript": result["text"].strip(),
        "segments": [
            {
                "id": seg["id"],
                "start": round(seg["start"], 3),
                "end": round(seg["end"], 3),
                "text": seg["text"].strip(),
            }
            for seg in result.get("segments", [])
        ],
    }
    (out_dir / "transcript.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # --- Plain text ---
    header = (
        f"Frederick County Board of Supervisors\n"
        f"Meeting: {meeting['title']}\n"
        f"Date:    {meeting['meeting_date']}\n"
        f"Source:  {meeting['meeting_url']}\n"
        f"{'=' * 72}\n\n"
    )
    (out_dir / "transcript.txt").write_text(
        header + result["text"].strip() + "\n", encoding="utf-8"
    )


# Sentinel object placed on the ready_queue to signal the transcribe thread
# that the download thread has finished and no more audio files are coming.
_QUEUE_DONE = object()


def _download_worker(
    pending: list,
    ready_queue: "queue.Queue[object]",
    staging_dir: Path,
    rate_limit: Optional[str],
    download_workers: int = 1,
) -> None:
    """
    Download thread: dispatches audio downloads using a thread pool
    (*download_workers* parallel downloads) and puts completed
    (meeting, audio_path) tuples onto *ready_queue* in chronological order.

    The queue is bounded (maxsize = --prefetch), so this thread blocks
    once the transcriber falls behind, keeping disk usage bounded.

    On completion (or if _shutdown is set) puts _QUEUE_DONE as a sentinel
    so the transcribe thread knows to stop.
    """
    from concurrent.futures import ThreadPoolExecutor

    def _fetch_one(meeting: sqlite3.Row) -> tuple:
        """Download one clip in a pool worker; return (meeting, audio_path | None)."""
        clip_id = meeting["clip_id"]
        mdate   = meeting["meeting_date"]
        title   = meeting["title"]

        # Each worker needs its own DB connection (sqlite3 is not thread-safe)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=True)
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            # Check if already transcribed (DB may lag after a crash)
            dir_name = f"{mdate}_clip{clip_id}_{_safe_dirname(title)}"
            out_dir  = TRANSCRIPT_DIR / dir_name
            if (out_dir / "transcript.json").exists():
                log.info("[downloader] clip %d already has transcript — queuing skip", clip_id)
                return (meeting, None)  # None audio_path → transcribe thread skips

            # Each clip uses an isolated subdir; _download_audio returns the file path.
            clip_staging = staging_dir / f"clip{clip_id}"

            # If a stale subdir exists from a previous interrupted run, wipe it
            if clip_staging.exists():
                log.info("[downloader] Removing stale staging dir: %s", clip_staging.name)
                shutil.rmtree(clip_staging, ignore_errors=True)

            log.info("[downloader] ↓ clip %d | %s | %s", clip_id, mdate, title)
            set_status(conn, clip_id, "downloading")

            try:
                audio_path = _download_audio(clip_id, meeting["meeting_url"],
                                             staging_dir, rate_limit)
                mb = audio_path.stat().st_size / 1e6
                log.info("[downloader] ✓ clip %d saved (%.1f MB) — queued for transcription",
                         clip_id, mb)
                return (meeting, audio_path)

            except Exception as exc:
                err_str = str(exc)
                shutil.rmtree(clip_staging, ignore_errors=True)  # clean up partial subdir

                # Transient server errors (502, 503, timeouts) — reset to pending so
                # the next pipeline run retries automatically without --retry-failed.
                _TRANSIENT = ("502", "503", "timed out", "time out", "Bad Gateway",
                              "Service Unavailable", "Connection reset", "Connection refused")
                if any(t in err_str for t in _TRANSIENT):
                    log.warning("[downloader] TRANSIENT error clip %d — resetting to pending: %s",
                                clip_id, err_str.splitlines()[0])
                    set_status(conn, clip_id, "pending", error=None)
                else:
                    log.error("[downloader] FAILED download clip %d: %s", clip_id, exc,
                              exc_info=True)
                    set_status(conn, clip_id, "failed", error=f"download: {exc}")
                return (meeting, None)   # None → transcribe thread records failure

        finally:
            conn.close()

    try:
        futures = []
        with ThreadPoolExecutor(max_workers=download_workers,
                                thread_name_prefix="downloader") as pool:
            for meeting in pending:
                if _shutdown:
                    log.info("[downloader] Shutdown signal received — stopping downloads.")
                    pool.shutdown(wait=False, cancel_futures=True)
                    break
                futures.append(pool.submit(_fetch_one, meeting))

            # Drain futures in submission order to preserve chronological transcription.
            # fut.result() blocks until that specific download finishes; ready_queue.put()
            # then blocks if the queue is full, providing backpressure automatically.
            for fut in futures:
                if _shutdown:
                    break
                ready_queue.put(fut.result())

    finally:
        # Always signal the transcribe thread to stop, even if we crash or are killed
        ready_queue.put(_QUEUE_DONE)
        log.info("[downloader] All downloads dispatched.")


def _transcribe_worker(
    ready_queue: queue.Queue,
    model_name: str,
    threads: int,
    conn: sqlite3.Connection,
    counters: dict,
    no_git: bool = False,
) -> None:
    """
    Transcription thread: pulls (meeting, audio_path) tuples off *ready_queue*,
    transcribes each with Whisper, saves transcripts, and deletes the audio file.

    *counters* is a shared dict with keys 'done' and 'failed' that the main
    thread reads for the final summary.

    Stops when it receives the _QUEUE_DONE sentinel.
    """
    import torch
    import whisper

    torch.set_num_threads(threads)
    log.info("[transcriber] Loading Whisper model '%s' …", model_name)
    model = whisper.load_model(model_name)
    log.info("[transcriber] Model loaded. Waiting for audio …")

    while True:
        item = ready_queue.get()

        if item is _QUEUE_DONE:
            log.info("[transcriber] All meetings processed.")
            break

        meeting, audio_path = item  # type: ignore[misc]
        clip_id = meeting["clip_id"]
        mdate   = meeting["meeting_date"]
        title   = meeting["title"]

        log.info("─" * 60)
        log.info("[transcriber] clip %d | %s | %s", clip_id, mdate, title)

        # --- Skip cases ---
        if audio_path is None:
            # Either already done (transcript exists) or download failed
            dir_name = f"{mdate}_clip{clip_id}_{_safe_dirname(title)}"
            out_dir  = TRANSCRIPT_DIR / dir_name
            if (out_dir / "transcript.json").exists():
                log.info("[transcriber] clip %d transcript already exists — marking done", clip_id)
                set_status(conn, clip_id, "done",
                           output_dir=str(out_dir.relative_to(BASE_DIR)))
                counters["done"] += 1
            else:
                # Download already recorded the failure in the DB
                counters["failed"] += 1
            continue

        # --- Transcribe ---
        dir_name = f"{mdate}_clip{clip_id}_{_safe_dirname(title)}"
        out_dir  = TRANSCRIPT_DIR / dir_name

        try:
            set_status(conn, clip_id, "transcribing")
            log.info("[transcriber] Transcribing %s …", audio_path.name)
            result = model.transcribe(
                str(audio_path),
                language="en",
                fp16=False,
                verbose=False,
            )
            word_count = len(str(result["text"]).split())
            log.info("[transcriber] ~%d words transcribed", word_count)

            _save_transcript(result, out_dir, meeting)
            log.info("[transcriber] Saved → %s", out_dir.relative_to(BASE_DIR))

            set_status(conn, clip_id, "done",
                       output_dir=str(out_dir.relative_to(BASE_DIR)))
            counters["done"] += 1
            log.info("[transcriber] clip %d done ✓", clip_id)

            if not no_git:
                _git_commit_transcript(out_dir, clip_id, mdate, title)

        except Exception as exc:
            log.error("[transcriber] FAILED clip %d: %s", clip_id, exc, exc_info=True)
            set_status(conn, clip_id, "failed", error=f"transcribe: {exc}")
            counters["failed"] += 1

        finally:
            # Always delete the staging subdir (audio + any leftover fragments)
            if audio_path:
                clip_staging = audio_path.parent
                shutil.rmtree(clip_staging, ignore_errors=True)
                log.debug("[transcriber] Deleted staging dir: %s", clip_staging.name)


def cmd_run(args) -> None:
    """
    Process pending meetings using a producer-consumer pipeline.

    A dedicated download thread pre-fetches audio files into a staging
    directory while the main thread transcribes using Whisper.  The queue
    is bounded to --prefetch items so disk usage stays bounded.

    Registers SIGINT / SIGTERM handlers so both threads stop cleanly after
    the current unit of work finishes.
    """
    global _shutdown
    _shutdown = False
    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    conn = init_db(DB_PATH)
    pending = get_pending(conn, include_failed=args.retry_failed)

    if not pending:
        log.info("No pending meetings found. Run 'scrape' first, or use "
                 "--retry-failed to re-process failures.")
        conn.close()
        return

    limit   = args.limit if args.limit else len(pending)
    batch   = list(pending[:limit])
    prefetch = args.prefetch

    log.info(
        "Starting run: %d meetings | model=%s | threads=%d | dl-workers=%d | prefetch=%d%s%s",
        len(batch), args.model, args.threads, args.download_workers, prefetch,
        f" | rate-limit={args.rate_limit}" if args.rate_limit else "",
        " | DRY-RUN" if args.dry_run else "",
    )

    if args.dry_run:
        for meeting in batch:
            log.info("  [dry-run] clip %d | %s | %s",
                     meeting["clip_id"], meeting["meeting_date"], meeting["title"])
        conn.close()
        return

    # Create / clean the staging directory
    staging_dir = TRANSCRIPT_DIR / ".staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    # Bounded queue: download thread blocks once prefetch slots are full
    ready_queue: queue.Queue = queue.Queue(maxsize=prefetch)
    counters = {"done": 0, "failed": 0}

    # --- Start download thread ---
    # Note: the download thread opens its own DB connection — sqlite3 connections
    # are not thread-safe and cannot be shared between threads.
    dl_thread = threading.Thread(
        target=_download_worker,
        args=(batch, ready_queue, staging_dir, args.rate_limit, args.download_workers),
        name="downloader",
        daemon=True,   # dies if main thread exits unexpectedly
    )
    dl_thread.start()
    log.info("Download thread started (workers: %d, prefetch queue depth: %d).",
             args.download_workers, prefetch)

    # --- Run transcription on the main thread ---
    # (Whisper holds a large model in memory; keeping it on main is cleaner.)
    _transcribe_worker(ready_queue, args.model, args.threads, conn, counters,
                       no_git=args.no_git)

    # Wait for download thread to finish (it should already be done by now)
    dl_thread.join(timeout=10)

    # Remove staging dir if empty
    try:
        staging_dir.rmdir()
    except OSError:
        pass   # non-empty means a partial download survived; leave it for next run

    summary = get_summary(conn)
    log.info("─" * 60)
    log.info(
        "Run finished: %d done, %d failed this session. "
        "DB totals: %s",
        counters["done"], counters["failed"],
        " | ".join(f"{k}={v}" for k, v in sorted(summary.items())),
    )
    conn.close()

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def cmd_status(args) -> None:
    """Print a human-readable summary of pipeline progress."""
    if not DB_PATH.exists():
        print("Pipeline database not found. Run 'scrape' first.")
        return

    conn = init_db(DB_PATH)
    summary = get_summary(conn)
    total = sum(summary.values())

    print(f"\nBoS Transcription Pipeline — {DB_PATH}")
    print(f"{'─' * 50}")
    for status in ("done", "pending", "transcribing", "downloading", "failed"):
        count = summary.get(status, 0)
        bar = "█" * (count * 30 // max(total, 1))
        print(f"  {status:<14} {count:>4}  {bar}")
    print(f"  {'TOTAL':<14} {total:>4}")
    print()

    # Show recent failures if any
    failed = conn.execute(
        "SELECT clip_id, meeting_date, title, error FROM meetings "
        "WHERE status = 'failed' ORDER BY updated_at DESC LIMIT 10"
    ).fetchall()
    if failed:
        print("Recent failures:")
        for row in failed:
            print(f"  clip {row['clip_id']} {row['meeting_date']} {row['title']}")
            if row["error"]:
                print(f"    error: {row['error'][:120]}")
        print()

    # Show recent completions
    done = conn.execute(
        "SELECT clip_id, meeting_date, title, output_dir FROM meetings "
        "WHERE status = 'done' ORDER BY updated_at DESC LIMIT 5"
    ).fetchall()
    if done:
        print("Recently completed:")
        for row in done:
            print(f"  ✓ {row['meeting_date']}  clip {row['clip_id']}  {row['title']}")
        print()

    conn.close()

# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Construct and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="bos_pipeline.py",
        description=(
            "Frederick County BoS meeting transcription pipeline.\n\n"
            "Three subcommands:\n"
            "  scrape  — populate the meeting index from Granicus\n"
            "  run     — download + transcribe all pending meetings\n"
            "  status  — show progress summary\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug-level logging"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # ---- scrape ----
    p_scrape = sub.add_parser(
        "scrape",
        help="Fetch the Granicus archive and populate the meeting index",
        description=(
            "Fetches https://fcva.granicus.com/ViewPublisher.php?view_id=1 "
            "and inserts every meeting since 2020 into the pipeline database. "
            "Safe to re-run; existing rows are not overwritten."
        ),
    )
    p_scrape.set_defaults(func=cmd_scrape)

    # ---- run ----
    p_run = sub.add_parser(
        "run",
        help="Process pending meetings (download → transcribe → save)",
        description=(
            "Processes meetings in chronological order. Interruptible with "
            "Ctrl-C — the current meeting finishes cleanly before stopping. "
            "Re-running resumes from where the previous run left off."
        ),
    )
    p_run.add_argument(
        "--model", default=DEFAULT_MODEL, metavar="NAME",
        help=(
            f"Whisper model to use (default: {DEFAULT_MODEL}). "
            "Options: tiny.en, base.en, small.en, medium.en, large-v3, etc. "
            "Larger models are more accurate but slower and use more RAM."
        ),
    )
    p_run.add_argument(
        "--threads", type=int, default=DEFAULT_THREADS, metavar="N",
        help=(
            f"CPU threads for Whisper / PyTorch (default: {DEFAULT_THREADS}). "
            "Reduce this if you need the machine to stay responsive."
        ),
    )
    p_run.add_argument(
        "--rate-limit", default=None, metavar="RATE",
        help=(
            "yt-dlp download rate limit, e.g. '2M' for 2 MB/s. "
            "Useful on metered connections. No limit by default."
        ),
    )
    p_run.add_argument(
        "--limit", type=int, default=None, metavar="N",
        help="Only process N meetings this session (useful for testing).",
    )
    p_run.add_argument(
        "--retry-failed", action="store_true",
        help="Include previously failed meetings in this run.",
    )
    p_run.add_argument(
        "--prefetch", type=int, default=4, metavar="N",
        help=(
            "Number of audio files to pre-download ahead of transcription "
            "(default: 4). Higher values overlap more download/transcribe time "
            "at the cost of more staging disk space (~50–200 MB per slot). "
            "Should be >= --download-workers."
        ),
    )
    p_run.add_argument(
        "--download-workers", type=int, default=3, metavar="N",
        dest="download_workers",
        help=(
            "Number of parallel audio downloads (default: 3). "
            "Downloads are network-bound so running several in parallel keeps "
            "the transcription queue full. Should be <= --prefetch."
        ),
    )
    p_run.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be processed without downloading or transcribing.",
    )
    p_run.add_argument(
        "--no-git", action="store_true",
        help="Disable automatic git commit+push after each transcript is saved.",
    )
    p_run.set_defaults(func=cmd_run)

    # ---- status ----
    p_status = sub.add_parser(
        "status",
        help="Show pipeline progress summary",
    )
    p_status.set_defaults(func=cmd_status)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    setup_logging(verbose=args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()
