#!/usr/bin/env python3
"""
Daily refresh pipeline for Frederick County live public-records PDFs.

Downloads two PDFs that the county regenerates every day, re-parses them
into JSON, converts to Parquet, and patches the SHA-256 / size entries in
playground/src/engines/data.ts so the playground's integrity check stays
current.

Usage:
    python scripts/refresh_daily_reports.py          # full run
    python scripts/refresh_daily_reports.py --dry-run  # skip download/parse/convert

Cron (daily at 6 AM, with overlap guard):
    0 6 * * *  cd /home/radio/code/fredco-audit && \
      flock -n data/misc_reports/refresh.lock \
        python3 scripts/refresh_daily_reports.py >> data/misc_reports/refresh.log 2>&1
"""

import argparse
import hashlib
import logging
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
RAW_MISC   = ROOT / "data" / "raw" / "misc"
PROCESSED  = ROOT / "data" / "processed"
PARQUET    = ROOT / "data" / "parquet"
LOG_DIR    = ROOT / "data" / "misc_reports"
DATA_TS    = ROOT / "playground" / "src" / "engines" / "data.ts"

SCRIPTS    = Path(__file__).parent

# ---------------------------------------------------------------------------
# PDFs to refresh
# ---------------------------------------------------------------------------
REPORTS = [
    {
        "url":     "https://frdnet.fcva.us/buslicinfc.pdf",
        "pdf":     RAW_MISC / "buslicinfc.pdf",
        "parser":  SCRIPTS / "parse_business_licenses.py",
        "parquet": PARQUET / "business_licenses.parquet",
    },
    {
        "url":     "https://frdnet.fcva.us/REDLQTAXES.pdf",
        "pdf":     RAW_MISC / "REDLQTAXES.pdf",
        "parser":  SCRIPTS / "parse_delinquent_taxes.py",
        "parquet": PARQUET / "delinquent_real_estate_taxes.parquet",
    },
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s  %(levelname)-7s  %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[logging.StreamHandler(sys.stdout)],
    )

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
def download(url: str, dest: Path, retries: int = 3, timeout: int = 60) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, retries + 1):
        try:
            log.info("Downloading %s (attempt %d/%d)", url, attempt, retries)
            r = requests.get(url, timeout=timeout, stream=True)
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
            size_kb = dest.stat().st_size / 1024
            log.info("  → %s  (%.0f KB)", dest.name, size_kb)
            return True
        except Exception as exc:
            log.warning("  Download failed: %s", exc)
            if attempt < retries:
                time.sleep(5 * attempt)
    return False

# ---------------------------------------------------------------------------
# Parse (runs parse script as subprocess to isolate errors)
# ---------------------------------------------------------------------------
def run_parser(script: Path) -> bool:
    log.info("Running %s", script.name)
    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    result = subprocess.run(
        [python, str(script)],
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        log.info("  %s", line)
    if result.returncode != 0:
        for line in result.stderr.splitlines():
            log.error("  STDERR: %s", line)
        log.error("  Parser exited with code %d", result.returncode)
        return False
    return True

# ---------------------------------------------------------------------------
# Parquet conversion (runs convert_to_parquet.py for just these two files)
# ---------------------------------------------------------------------------
def run_conversion() -> bool:
    log.info("Running convert_to_parquet.py")
    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    result = subprocess.run(
        [python, str(SCRIPTS / "convert_to_parquet.py")],
        capture_output=True,
        text=True,
    )
    # Only log lines relevant to our two files
    keywords = ("business_licenses", "delinquent_real_estate", "Error", "failed", "Skipping")
    for line in result.stdout.splitlines():
        if any(k in line for k in keywords):
            log.info("  %s", line)
    if result.returncode != 0:
        for line in result.stderr.splitlines():
            log.error("  STDERR: %s", line)
        return False
    return True

# ---------------------------------------------------------------------------
# Manifest patch  (updates data.ts in-place)
# ---------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def patch_manifest(parquet_path: Path, ts_path: Path) -> bool:
    """Update the size and sha256 for one parquet file in data.ts."""
    if not parquet_path.exists():
        log.error("Parquet not found, skipping manifest patch: %s", parquet_path)
        return False
    if not ts_path.exists():
        log.error("data.ts not found: %s", ts_path)
        return False

    sha256 = sha256_file(parquet_path)
    size   = parquet_path.stat().st_size
    name   = parquet_path.name

    src = ts_path.read_text()

    # Match the multi-line manifest entry:
    #   'business_licenses.parquet': {
    #     size: 12345,
    #     sha256: 'abc...'
    #   },
    pattern = (
        r"('" + re.escape(name) + r"':\s*\{\s*\n\s*size:\s*)"
        r"\d+"
        r"(\s*,\s*\n\s*sha256:\s*')"
        r"[0-9a-f]+"
        r"(')"
    )
    replacement = rf"\g<1>{size}\g<2>{sha256}\g<3>"
    patched, n = re.subn(pattern, replacement, src)

    if n == 0:
        log.warning(
            "  No manifest entry found for '%s' in %s — "
            "add it manually then re-run.",
            name, ts_path.name,
        )
        return False

    ts_path.write_text(patched)
    log.info("  Patched data.ts: %s  size=%d  sha256=%s…", name, size, sha256[:12])
    return True

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Refresh daily county report PDFs")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip download/parse/convert; only patch manifest")
    args = parser.parse_args()

    setup_logging()
    log.info("=" * 60)
    log.info("Daily county report refresh  %s", datetime.now().isoformat())
    log.info("=" * 60)

    errors = 0

    for report in REPORTS:
        log.info("--- %s ---", report["pdf"].name)

        if not args.dry_run:
            if not download(report["url"], report["pdf"]):
                log.error("Download failed for %s — skipping", report["pdf"].name)
                errors += 1
                continue

            if not run_parser(report["parser"]):
                log.error("Parse failed for %s — skipping parquet conversion", report["pdf"].name)
                errors += 1
                continue

    if not args.dry_run:
        if not run_conversion():
            log.error("Parquet conversion failed")
            errors += 1

    # Always patch manifest (even in dry-run, if parquets already exist)
    for report in REPORTS:
        if not patch_manifest(report["parquet"], DATA_TS):
            errors += 1

    log.info("=" * 60)
    if errors:
        log.error("Finished with %d error(s)", errors)
        sys.exit(1)
    else:
        log.info("Refresh complete — no errors")


if __name__ == "__main__":
    main()
