#!/usr/bin/env python3
"""
BoS Diarization Pipeline

Downloads audio locally, copies to a processing server, and syncs results back.

Usage:
    python scripts/bos_diarization_pipeline.py --server bigdeal [--phase all]
    python scripts/bos_diarization_pipeline.py --server dell-debian [--phase all]

Server profiles
    bigdeal    — MSI GTX 1060 6GB, GPU diarization (fast)
    dell-debian — CPU-only fallback
"""

import argparse
import os
import subprocess
import time
import sqlite3
import json
from pathlib import Path
from datetime import datetime
import shutil

BASE_DIR = Path(__file__).parent.parent
TRANSCRIPT_DIR = BASE_DIR / "data" / "bos_transcripts"
AUDIO_DIR = TRANSCRIPT_DIR / "audio"
COMPLETED_DIR = AUDIO_DIR / "completed"
DB_PATH = TRANSCRIPT_DIR / "pipeline.db"
LOG_FILE = TRANSCRIPT_DIR / "diarization_pipeline.log"

# Server profiles: ssh_host → (remote_repo_dir, venv_python, diarize_device)
SERVER_PROFILES = {
    "bigdeal": {
        "host": "bigdeal",
        "dir": "/home/bigdeal/fredco-audit",
        "venv": "/home/bigdeal/fredco-audit/.venv/bin/python",
        "device": "cuda",
    },
    "dell-debian": {
        "host": "dell-debian",
        "dir": "/home/radio/fredco-audit",
        "venv": "/home/radio/fredco-audit/.venv/bin/python",
        "device": "cpu",
    },
}

# Set by main() after parsing --server
SERVER = None
SERVER_DIR = None
SERVER_AUDIO_DIR = None
SERVER_VENV = None
DIARIZE_DEVICE = None

def log(msg):
    """Log to file and print."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    LOG_FILE.write_text(line + "\n")

def run_local(cmd, capture=True):
    """Run a local command."""
    log(f"Local: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=capture, text=True)
    if result.returncode != 0 and capture:
        log(f"  Error: {result.stderr[:200]}")
    return result

def run_ssh(cmd, capture=True):
    """Run a command on dell-debian via SSH."""
    full_cmd = f"ssh {SERVER} \"{cmd}\""
    log(f"SSH: {cmd}")
    result = subprocess.run(full_cmd, shell=True, capture_output=capture, text=True, check=False)
    if result.returncode != 0 and capture:
        log(f"  SSH Error: {result.stderr[:200]}")
    return result

def get_meetings_without_audio(limit=None):
    """Get meetings that are done but don't have audio. Most recent first."""
    if not DB_PATH.exists():
        log(f"Database not found at {DB_PATH}")
        return []

    conn = sqlite3.connect(str(DB_PATH))
    query = """
        SELECT clip_id, title, meeting_date, meeting_url
        FROM meetings
        WHERE status = 'done'
        AND (audio_file IS NULL OR audio_file = '')
        ORDER BY meeting_date DESC, clip_id DESC
    """
    if limit:
        query += f" LIMIT {limit}"
    cursor = conn.execute(query)
    meetings = cursor.fetchall()
    conn.close()
    return meetings

def get_meetings_to_diarize(limit=None):
    """Get meetings that have audio but no diarization. Most recent first."""
    if not DB_PATH.exists():
        return []

    conn = sqlite3.connect(str(DB_PATH))
    query = """
        SELECT clip_id, title, meeting_date, meeting_url, audio_file
        FROM meetings
        WHERE audio_file IS NOT NULL
        AND audio_file != ''
        AND (diarized IS NULL OR diarized = 0)
        ORDER BY meeting_date DESC, clip_id DESC
    """
    if limit:
        query += f" LIMIT {limit}"
    cursor = conn.execute(query)
    meetings = cursor.fetchall()
    conn.close()
    return meetings

def download_audio_one(clip_id, meeting_url):
    """Download audio for a single meeting."""
    output_path = AUDIO_DIR / f"clip{clip_id}.mp4"
    output_m4a = AUDIO_DIR / f"clip{clip_id}.m4a"

    # Check for existing completed download
    for existing in [output_m4a, output_path]:
        if existing.exists():
            size = existing.stat().st_size
            if size > 1000000:
                return True, None

    # Check for partial download to resume
    part_file = AUDIO_DIR / f"clip{clip_id}.mp4.part"
    initial_size = 0
    if part_file.exists():
        initial_size = part_file.stat().st_size
        log(f"  Resuming partial download for clip {clip_id} ({initial_size / 1e6:.1f} MB)")

    # Download as mp4 (no -x extraction), then convert with ffmpeg
    # Use best effort with fragments for large files - no timeout, let yt-dlp handle retries
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--no-progress",
        "--no-warnings",
        "--retries", "infinite",
        "--fragment-retries", "infinite",
        "--retry-sleep", "exp=1:60",
        "-o", str(output_path),
        meeting_url
    ]

    try:
        # No timeout - let yt-dlp run until complete or explicit failure
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Check if download succeeded
        if result.returncode != 0:
            # Check for permanent failures
            if "HTTP Error 404" in result.stderr or "Unable to extract" in result.stderr:
                return False, f"Permanent error: {result.stderr[:100]}"
            # Network errors - don't fail permanently, try again on next run
            log(f"  Warning: {result.stderr[:80] if result.stderr else 'unknown'}")
        
        # Convert mp4 to m4a with ffmpeg if needed
        if output_path.exists() and not output_m4a.exists():
            conv_cmd = [
                "ffmpeg", "-y", "-i", str(output_path),
                "-vn", "-acodec", "copy", str(output_m4a)
            ]
            conv_result = subprocess.run(conv_cmd, capture_output=True, text=True, timeout=600)
            if conv_result.returncode == 0 and output_m4a.exists():
                output_path.unlink()  # Remove mp4 after conversion
        
        final_file = output_m4a if output_m4a.exists() else output_path
        if final_file.exists():
            size = final_file.stat().st_size
            if size > 1000000:
                return True, None
            else:
                return False, f"File too small: {size}"
        
        # Check if we made progress on partial download
        if part_file.exists():
            final_size = part_file.stat().st_size
            if final_size > initial_size + 10000000:  # Made 10MB progress
                log(f"  Made progress: {initial_size/1e6:.1f}MB -> {final_size/1e6:.1f}MB, will retry")
                return False, "Incomplete but making progress"
        
        return False, "No output file found"
        
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)

def phase_download(limit=None):
    """Phase 1: Download audio locally."""
    log("=== Phase 1: Download Audio Locally ===")

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    meetings = get_meetings_without_audio(limit)

    if not meetings:
        log("No meetings need audio download")
        return

    log(f"Found {len(meetings)} meetings to download")

    completed = 0
    failed = 0

    for meeting in meetings:
        clip_id, title, meeting_date, meeting_url = meeting
        log(f"Downloading clip {clip_id} ({meeting_date})...")

        success, error = download_audio_one(clip_id, meeting_url)

        if success:
            # Move to completed folder
            COMPLETED_DIR.mkdir(parents=True, exist_ok=True)
            final_path = COMPLETED_DIR / f"clip{clip_id}.m4a"
            
            # Find the downloaded file (could be .mp4 or .m4a)
            downloaded = None
            for ext in ['.m4a', '.mp4']:
                f = AUDIO_DIR / f"clip{clip_id}{ext}"
                if f.exists() and f.stat().st_size > 1000000:
                    downloaded = f
                    break
            
            if downloaded:
                shutil.move(str(downloaded), str(final_path))
            
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute(
                "UPDATE meetings SET audio_file = ? WHERE clip_id = ?",
                (f"clip{clip_id}.m4a", clip_id)
            )
            conn.commit()
            conn.close()
            completed += 1
            log(f"  ✓ Downloaded clip {clip_id}")
        else:
            failed += 1
            log(f"  ✗ Failed clip {clip_id}: {error[:100] if error else 'unknown'}")
            # Skip failed meetings - will retry on next run
            time.sleep(5)  # Longer delay after failure
            continue

        time.sleep(1)

    log(f"=== Download Complete: {completed} OK, {failed} failed ===")

def phase_copy_to_server():
    """Phase 2: Rsync all done meetings' audio to the processing server."""
    log(f"=== Phase 2: Bulk Copy Audio to {SERVER} ===")

    run_ssh(f"mkdir -p {SERVER_AUDIO_DIR}")

    conn = sqlite3.connect(str(DB_PATH))
    meetings = conn.execute("""
        SELECT clip_id, audio_file
        FROM meetings
        WHERE status = 'done'
          AND audio_file IS NOT NULL AND audio_file != ''
          AND (audio_copied IS NULL OR audio_copied = 0)
        ORDER BY meeting_date DESC
    """).fetchall()

    if not meetings:
        log("All audio already copied")
        conn.close()
        return

    log(f"{len(meetings)} files to copy")
    copied = failed = 0

    for clip_id, audio_file in meetings:
        local_file = COMPLETED_DIR / audio_file
        if not local_file.exists():
            log(f"  SKIP clip {clip_id}: local file missing")
            continue

        size_mb = local_file.stat().st_size // 1_000_000
        log(f"  clip {clip_id} ({size_mb} MB)…")
        result = subprocess.run(
            ["rsync", "-az", "--progress",
             str(local_file), f"{SERVER}:{SERVER_AUDIO_DIR}/"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            conn.execute("UPDATE meetings SET audio_copied=1 WHERE clip_id=?", (clip_id,))
            conn.commit()
            copied += 1
            log(f"    ✓ clip {clip_id}")
        else:
            failed += 1
            log(f"    ✗ clip {clip_id}: {result.stderr[:120]}")

    conn.close()
    log(f"=== Copy done: {copied} copied, {failed} failed ===")

def phase_watch(interval=60, max_runtime=None):
    """Phase 2b: Watch completed folder, copy new files to server continuously."""
    log("=== Phase 2b: Watch Mode - Copying to Server ===")

    # Ensure audio_copied column exists
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.execute("PRAGMA table_info(meetings)")
    columns = [row[1] for row in cursor.fetchall()]
    if "audio_copied" not in columns:
        conn.execute("ALTER TABLE meetings ADD COLUMN audio_copied INTEGER DEFAULT 0")
        conn.commit()
    conn.close()

    start_time = time.time()
    run_ssh(f"mkdir -p {SERVER_AUDIO_DIR}")

    log(f"Watching {COMPLETED_DIR} for new files...")

    while True:
        if max_runtime and (time.time() - start_time) > max_runtime:
            log(f"Watch timeout reached ({max_runtime}s), stopping...")
            break

        COMPLETED_DIR.mkdir(parents=True, exist_ok=True)

        # Get files already copied
        conn = sqlite3.connect(str(DB_PATH))
        copied = conn.execute(
            "SELECT audio_file FROM meetings WHERE audio_copied = 1"
        ).fetchall()
        copied_files = {c[0] for c in copied if c[0]}
        conn.close()

        # Check for new files in completed folder
        new_files = []
        for audio_file in COMPLETED_DIR.glob("*.m4a"):
            if audio_file.name not in copied_files:
                new_files.append(audio_file)

        if new_files:
            log(f"Found {len(new_files)} new files to copy")

        for audio_file in new_files:
            clip_id = audio_file.stem.replace("clip", "")
            log(f"  Copying {audio_file.name}...")

            # Use local subprocess for scp (not run_ssh which wraps in SSH)
            result = subprocess.run(
                f"scp -o ConnectTimeout=30 {audio_file} {SERVER}:{SERVER_AUDIO_DIR}/",
                shell=True, capture_output=True, text=True
            )

            if result.returncode == 0:
                conn = sqlite3.connect(str(DB_PATH))
                conn.execute(
                    "UPDATE meetings SET audio_copied = 1 WHERE clip_id = ?",
                    (clip_id,)
                )
                conn.commit()
                conn.close()
                log(f"    ✓ Copied clip {clip_id}")
            else:
                log(f"    ✗ Failed to copy clip {clip_id}: {result.stderr[:100] if result.stderr else 'unknown'}")

        time.sleep(interval)

def phase_process():
    """Phase 3: Start diarization on the processing server."""
    log(f"=== Phase 3: Start Diarization on {SERVER} (device={DIARIZE_DEVICE}) ===")

    run_ssh(f"cd {SERVER_DIR} && mkdir -p data/bos_transcripts/audio/completed")

    log("Ensuring diarization script exists...")
    run_ssh(f"ls {SERVER_DIR}/scripts/bos_speaker_diarize.py")

    log("Starting diarization in background...")
    run_ssh(
        f"cd {SERVER_DIR} && nohup {SERVER_VENV} -u scripts/bos_speaker_diarize.py"
        f" --device {DIARIZE_DEVICE}"
        f" > diarize.log 2>&1 &",
        capture=False,
    )

    log("Diarization started. Use --monitor to track progress.")

def phase_monitor():
    """Monitor diarization progress."""
    log(f"=== Monitoring Diarization on {SERVER} ===")

    result = run_ssh("ps aux | grep bos_speaker_diarize | grep -v grep | wc -l")
    if result.returncode == 0:
        log(f"Running diarize processes: {result.stdout.strip()}")

    result = run_ssh(f"tail -20 {SERVER_DIR}/diarize.log")
    if result.returncode == 0:
        log(f"Last 20 lines of log:\n{result.stdout}")

    result = run_ssh(
        f'sqlite3 {SERVER_DIR}/data/bos_transcripts/pipeline.db'
        f' "SELECT COUNT(*) FROM meetings WHERE diarized = 1"'
    )
    if result.returncode == 0:
        log(f"Completed diarizations: {result.stdout.strip()}")

def phase_sync():
    """Phase 4: Rsync transcript JSONs back from server and update local DB."""
    log(f"=== Phase 4: Sync Results from {SERVER} ===")

    # Rsync all transcript.json files back, excluding audio files
    log("Rsyncing transcript JSONs back...")
    result = subprocess.run(
        [
            "rsync", "-az", "--progress",
            "--include=*/",
            "--include=*/transcript.json",
            "--include=*/transcript.txt",
            "--exclude=*",
            f"{SERVER}:{SERVER_DIR}/data/bos_transcripts/",
            str(TRANSCRIPT_DIR) + "/",
        ],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        log("Rsync complete")
    else:
        log(f"Rsync error: {result.stderr[:200]}")

    # Update local DB to mark diarized clips
    log("Updating local DB from server...")
    result = run_ssh(
        f'sqlite3 {SERVER_DIR}/data/bos_transcripts/pipeline.db'
        f' "SELECT clip_id FROM meetings WHERE diarized = 1"'
    )
    if result.returncode == 0 and result.stdout.strip():
        conn = sqlite3.connect(str(DB_PATH))
        for line in result.stdout.strip().splitlines():
            clip_id = line.strip()
            if clip_id:
                conn.execute("UPDATE meetings SET diarized = 1 WHERE clip_id = ?", (clip_id,))
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM meetings WHERE diarized=1").fetchone()[0]
        conn.close()
        log(f"Marked {n} meetings as diarized locally")

    log("=== Sync Complete — run build_transcript_index.py to publish ===")

def phase_cleanup():
    """Phase 5: Clean up audio from server."""
    log("=== Phase 5: Cleanup Server ===")

    log("Removing audio files from server...")
    run_ssh(f"rm -f {SERVER_AUDIO_DIR}/*.m4a {SERVER_AUDIO_DIR}/*.mp4*")

    log("Checking disk space...")
    result = run_ssh("df -h /home")
    if result.returncode == 0:
        log(result.stdout)

    log("=== Cleanup Complete ===")

def phase_names():
    """Phase 6: Run name matching locally."""
    log("=== Phase 6: Name Matching ===")

    log("Running name matcher...")
    result = run_local(f"cd {BASE_DIR} && python3 scripts/bos_name_matcher.py")

    if result.returncode == 0:
        log("Name matching complete")
    else:
        log(f"Name matching failed: {result.stderr}")

def main():
    parser = argparse.ArgumentParser(description="BoS Diarization Pipeline")
    parser.add_argument(
        "--server", choices=list(SERVER_PROFILES.keys()), default="bigdeal",
        help="Processing server (default: bigdeal)",
    )
    parser.add_argument("--phase", choices=["download", "copy", "watch", "process", "monitor", "sync", "names", "cleanup", "all"],
                       default="all", help="Phase to run")
    parser.add_argument("--monitor", action="store_true", help="Monitor running process")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of meetings to process")
    parser.add_argument("--watch-timeout", type=int, default=None, help="Watch mode timeout in seconds")
    args = parser.parse_args()

    # Wire server globals from the selected profile
    global SERVER, SERVER_DIR, SERVER_AUDIO_DIR, SERVER_VENV, DIARIZE_DEVICE
    profile = SERVER_PROFILES[args.server]
    SERVER = profile["host"]
    SERVER_DIR = profile["dir"]
    SERVER_AUDIO_DIR = f"{SERVER_DIR}/data/bos_transcripts/audio/completed"
    SERVER_VENV = profile["venv"]
    DIARIZE_DEVICE = profile["device"]
    log(f"Using server: {SERVER} (device: {DIARIZE_DEVICE})")

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    if args.monitor:
        phase_monitor()
        return

    if args.phase == "download":
        phase_download(args.limit)
    elif args.phase == "copy":
        phase_copy_to_server()
    elif args.phase == "watch":
        phase_watch(max_runtime=args.watch_timeout)
    elif args.phase == "process":
        phase_process()
    elif args.phase == "monitor":
        phase_monitor()
    elif args.phase == "sync":
        phase_sync()
    elif args.phase == "names":
        phase_names()
    elif args.phase == "cleanup":
        phase_cleanup()
    elif args.phase == "all":
        log("=== Starting Full Diarization Pipeline ===")
        phase_download(args.limit)
        phase_copy_to_server()
        phase_process()
        log("Diarization started. Run with --monitor to track progress.")
        log("When complete, run: python3 scripts/bos_diarization_pipeline.py --phase sync")
        log("Then: python3 scripts/bos_diarization_pipeline.py --phase names")
        log("Then: python3 scripts/bos_diarization_pipeline.py --phase cleanup")

if __name__ == "__main__":
    main()