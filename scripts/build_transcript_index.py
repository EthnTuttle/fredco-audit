#!/usr/bin/env python3
"""
Build the transcript search index for the web playground.

Reads all completed transcript JSON files and produces:
  playground/public/transcripts/manifest.json  — metadata only (for listing)
  playground/public/transcripts/index.json     — full text (for search)
  playground/public/transcripts/clip<id>.json  — individual transcripts (for reader)

Run from the repo root:
  python scripts/build_transcript_index.py
"""

import json
import os
import shutil
import sys
from pathlib import Path

TRANSCRIPTS_DIR = Path("data/bos_transcripts")
OUTPUT_DIR = Path("playground/public/transcripts")


def fmt_duration(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def main():
    if not TRANSCRIPTS_DIR.exists():
        print(f"ERROR: {TRANSCRIPTS_DIR} not found. Run from repo root.", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = []
    index = []
    copied = 0
    skipped = 0

    dirs = sorted(TRANSCRIPTS_DIR.iterdir())
    for entry in dirs:
        if not entry.is_dir():
            continue
        json_path = entry / "transcript.json"
        if not json_path.exists():
            skipped += 1
            continue

        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  WARN: skipping {entry.name}: {e}", file=sys.stderr)
            skipped += 1
            continue

        meta = data.get("meta", {})
        clip_id = meta.get("clip_id")
        if clip_id is None:
            print(f"  WARN: no clip_id in {entry.name}, skipping", file=sys.stderr)
            skipped += 1
            continue

        title = meta.get("title", "")
        meeting_date = meta.get("meeting_date", "")
        meeting_url = meta.get("meeting_url", "")
        transcribed_at = meta.get("transcribed_at", "")
        full_text = data.get("transcript", "")
        segments = data.get("segments", [])
        duration = segments[-1]["end"] if segments else 0

        # Diarization: present if any segment has a non-UNKNOWN speaker label
        has_diarization = any(
            s.get("speaker") not in (None, "UNKNOWN")
            for s in segments
        )

        manifest.append({
            "clip_id": clip_id,
            "title": title,
            "meeting_date": meeting_date,
            "meeting_url": meeting_url,
            "transcribed_at": transcribed_at,
            "duration": fmt_duration(duration),
            "segment_count": len(segments),
            "has_diarization": has_diarization,
        })

        index.append({
            "clip_id": clip_id,
            "meeting_date": meeting_date,
            "title": title,
            "text": full_text,
        })

        # Copy individual transcript for the reader
        dest = OUTPUT_DIR / f"clip{clip_id}.json"
        shutil.copy2(json_path, dest)
        copied += 1

    # Sort by date descending
    manifest.sort(key=lambda x: x["meeting_date"], reverse=True)
    index.sort(key=lambda x: x["meeting_date"], reverse=True)

    with open(OUTPUT_DIR / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, separators=(",", ":"))

    with open(OUTPUT_DIR / "index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, separators=(",", ":"))

    manifest_kb = (OUTPUT_DIR / "manifest.json").stat().st_size // 1024
    index_kb = (OUTPUT_DIR / "index.json").stat().st_size // 1024

    print(f"Done: {copied} transcripts indexed, {skipped} skipped")
    print(f"  manifest.json  {manifest_kb} KB")
    print(f"  index.json     {index_kb} KB")
    print(f"  clip*.json     {copied} files")


if __name__ == "__main__":
    main()
