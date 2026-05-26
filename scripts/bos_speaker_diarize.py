#!/usr/bin/env python3
"""
Speaker diarization using faster-whisper + pyannote.

Assigns speaker labels to existing Whisper segments using pyannote/speaker-diarization-3.1.
If a transcript has no segments yet, falls back to transcribing with faster-whisper first.

Usage:
    python scripts/bos_speaker_diarize.py               # auto-detect GPU
    python scripts/bos_speaker_diarize.py --device cpu  # force CPU
    python scripts/bos_speaker_diarize.py --limit 5     # process 5 meetings
    python scripts/bos_speaker_diarize.py --dry-run
"""

import json
import sqlite3
import subprocess
import gc
import os
import sys
import argparse
import time
from pathlib import Path

import torch

# Fix numpy 2.x compatibility issue before importing pyannote
import numpy as np
np.NaN = np.nan

os.environ.setdefault("HF_HOME", str(Path.home() / ".cache" / "huggingface"))

BASE_DIR = Path(__file__).parent.parent
TRANSCRIPT_DIR = BASE_DIR / "data" / "bos_transcripts"
AUDIO_DIR = TRANSCRIPT_DIR / "audio" / "completed"
DB_PATH = TRANSCRIPT_DIR / "pipeline.db"

HF_TOKEN = os.environ.get("HF_TOKEN", None)

WHISPER_MODEL_GPU = "large-v3"
WHISPER_MODEL_CPU = "small"


def detect_device():
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        print(f"GPU: {name} ({vram_gb:.1f} GB VRAM)")
        return "cuda"
    print("No CUDA GPU found, using CPU")
    return "cpu"


def assign_speakers(seg_list, speaker_segments):
    """
    Assign the best-matching speaker label to each Whisper segment.

    Uses max-overlap rather than first-match so that segments spanning
    a speaker boundary get the label of whoever spoke longest in that window.
    """
    for seg in seg_list:
        seg_start, seg_end = seg["start"], seg["end"]
        best_speaker = "UNKNOWN"
        best_overlap = 0.0

        for ss in speaker_segments:
            overlap = min(ss["end"], seg_end) - max(ss["start"], seg_start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = ss["speaker"]

        seg["speaker"] = best_speaker


def diarize_meeting(clip_id, audio_file, output_dir, device):
    """Run speaker diarization on a single meeting."""
    audio_path = AUDIO_DIR / audio_file

    if not audio_path.exists():
        return clip_id, False, f"Audio file not found: {audio_path}"

    transcript_dir = None
    for d in output_dir.glob(f"*_clip{clip_id}_*"):
        if d.is_dir():
            transcript_dir = d
            break

    if not transcript_dir:
        return clip_id, False, f"Transcript directory not found for clip {clip_id}"

    transcript_path = transcript_dir / "transcript.json"
    if not transcript_path.exists():
        return clip_id, False, f"Transcript not found: {transcript_path}"

    try:
        print(f"[{clip_id}] Starting diarization...")

        with open(transcript_path) as f:
            transcript = json.load(f)

        # Prefer existing segments; only re-transcribe if none exist.
        # Preserve whatever whisper_model produced those segments.
        if "segments" in transcript and transcript["segments"]:
            seg_list = transcript["segments"]
            print(f"[{clip_id}] Using {len(seg_list)} existing segments")
            # Keep the whisper_model field that's already in the transcript (don't overwrite it).
            # If absent, note that we didn't touch the transcription.
            recorded_whisper_model = "large-v3"  # bos_pipeline.py always uses large-v3
        else:
            whisper_model_name = WHISPER_MODEL_GPU if device == "cuda" else WHISPER_MODEL_CPU
            compute_type = "float16" if device == "cuda" else "int8"
            print(f"[{clip_id}] No existing segments — transcribing with {whisper_model_name} ({device})...")
            from faster_whisper import WhisperModel
            model = WhisperModel(whisper_model_name, device=device, compute_type=compute_type)
            segments, _ = model.transcribe(
                str(audio_path),
                language="en",
                vad_filter=False,
            )
            seg_list = [
                {"id": i, "start": s.start, "end": s.end, "text": s.text}
                for i, s in enumerate(segments)
            ]
            del model
            gc.collect()
            if device == "cuda":
                torch.cuda.empty_cache()
            recorded_whisper_model = whisper_model_name

        # Convert to WAV — pyannote requires consistent sample alignment
        wav_path = audio_path.with_suffix(".wav")
        if not wav_path.exists():
            print(f"[{clip_id}] Converting to 16kHz mono WAV...")
            subprocess.run(
                ["ffmpeg", "-i", str(audio_path), "-ar", "16000", "-ac", "1", "-y", str(wav_path)],
                capture_output=True, check=True,
            )

        print(f"[{clip_id}] Running pyannote diarization ({device})...")
        import torchaudio
        from pyannote.audio import Pipeline

        diarize_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=HF_TOKEN,
        )
        diarize_pipeline.to(torch.device(device))

        # Load WAV ourselves to avoid pyannote 4.x torchcodec dependency
        waveform, sample_rate = torchaudio.load(str(wav_path))
        audio_input = {"waveform": waveform, "sample_rate": sample_rate}
        diarization = diarize_pipeline(audio_input, min_speakers=2, max_speakers=15)

        speaker_segments = [
            {"start": segment.start, "end": segment.end, "speaker": speaker}
            for segment, _, speaker in diarization.speaker_diarization.itertracks(yield_label=True)
        ]

        print(f"[{clip_id}] Assigning speakers to {len(seg_list)} segments...")
        assign_speakers(seg_list, speaker_segments)

        n_speakers = len({s["speaker"] for s in seg_list if s["speaker"] != "UNKNOWN"})
        n_unknown = sum(1 for s in seg_list if s["speaker"] == "UNKNOWN")
        print(f"[{clip_id}] Done — {n_speakers} speakers, {n_unknown}/{len(seg_list)} UNKNOWN")

        transcript["diarization"] = True
        transcript["diarization_model"] = "pyannote/speaker-diarization-3.1"
        transcript["whisper_model"] = recorded_whisper_model
        transcript["segments"] = seg_list

        with open(transcript_path, "w") as f:
            json.dump(transcript, f, indent=2)

        return clip_id, True, None

    except Exception as e:
        import traceback
        return clip_id, False, f"{e}\n{traceback.format_exc()[:500]}"


def get_meetings_to_diarize(conn, limit=None):
    query = """
        SELECT clip_id, title, meeting_date, meeting_url, audio_file
        FROM meetings
        WHERE audio_file IS NOT NULL
          AND audio_file != ''
          AND (diarized IS NULL OR diarized = 0)
        ORDER BY meeting_date DESC
    """
    if limit:
        query += f" LIMIT {limit}"
    return conn.execute(query).fetchall()


def ensure_columns(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(meetings)").fetchall()]
    if "diarized" not in cols:
        conn.execute("ALTER TABLE meetings ADD COLUMN diarized INTEGER DEFAULT 0")
        conn.commit()


def main():
    parser = argparse.ArgumentParser(description="BoS speaker diarization")
    parser.add_argument(
        "--device", choices=["cuda", "cpu"], default=None,
        help="Processing device (default: auto-detect)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max meetings to process")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run, don't process")
    args = parser.parse_args()

    device = args.device or detect_device()
    print(f"Device: {device}")

    conn = sqlite3.connect(str(DB_PATH))
    ensure_columns(conn)

    meetings = get_meetings_to_diarize(conn, args.limit)
    print(f"Found {len(meetings)} meetings to diarize")

    if args.dry_run:
        for m in meetings:
            print(f"  clip {m[0]}  {m[2]}  {m[1]}")
        conn.close()
        return

    processed = 0
    failed = 0

    for meeting in meetings:
        clip_id, title, meeting_date, meeting_url, audio_file = meeting
        print(f"\n[{processed + failed + 1}/{len(meetings)}] {meeting_date} clip{clip_id}: {title[:50]}")

        _, success, error = diarize_meeting(clip_id, audio_file, TRANSCRIPT_DIR, device)

        if success:
            conn.execute("UPDATE meetings SET diarized = 1 WHERE clip_id = ?", (clip_id,))
            conn.commit()
            processed += 1
        else:
            failed += 1
            print(f"  FAILED: {error[:200]}")

    print(f"\n=== Complete: {processed} diarized, {failed} failed ===")
    conn.close()


if __name__ == "__main__":
    main()
