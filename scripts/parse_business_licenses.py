#!/usr/bin/env python3
"""
Parse Frederick County business license PDF into structured JSON.

Source: https://frdnet.fcva.us/buslicinfc.pdf
Format: Fixed-width two-column PDF (Trade Name | Owner Name)
Updated: daily by the county

Uses pdfplumber word-level extraction with x-position column split.
Column boundary: x < 248 = trade name, x >= 248 = owner name.

Output: data/processed/business_licenses.json
"""

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path

import pdfplumber

PDF_PATH = Path(__file__).parent.parent / "data" / "raw" / "misc" / "buslicinfc.pdf"
OUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "business_licenses.json"
SOURCE_URL = "https://frdnet.fcva.us/buslicinfc.pdf"

# x-coordinate boundary between the two columns (verified from word positions)
COL_SPLIT_X = 240


def extract_report_date(page) -> str | None:
    """Pull the report date from page words."""
    for word in page.extract_words():
        m = re.match(r"Date:(\d{1,2}/\d{1,2}/\d{4})", word["text"])
        if m:
            try:
                return datetime.strptime(m.group(1), "%m/%d/%Y").strftime("%Y-%m-%d")
            except ValueError:
                pass
    return None


def words_to_rows(page) -> list[dict]:
    """Convert page words to (trade_name, owner_name) rows using x-position split."""
    words = page.extract_words(x_tolerance=3, y_tolerance=3)

    # Group words by their y-position (rounded to handle minor float drift)
    by_y: dict[float, list] = defaultdict(list)
    for w in words:
        by_y[round(w["top"])].append(w)

    rows = []
    for y in sorted(by_y):
        line_words = sorted(by_y[y], key=lambda w: w["x0"])

        left_words = [w["text"] for w in line_words if w["x0"] < COL_SPLIT_X]
        right_words = [w["text"] for w in line_words if w["x0"] >= COL_SPLIT_X]

        if not left_words:
            continue

        trade_name = " ".join(left_words)
        raw_right = " ".join(right_words)

        # Skip header lines
        if trade_name in ("Trade Name", "Trade") or "Businesses Licensed" in trade_name:
            continue
        if re.match(r"^Date:", trade_name) or re.match(r"^Page:", trade_name):
            continue

        # Right column "." means owner unknown
        owner_name: str | None = None if raw_right in ("", ".") else raw_right

        rows.append({"trade_name": trade_name, "owner_name": owner_name})

    return rows


def parse(pdf_path: Path = PDF_PATH) -> dict:
    records: list[dict] = []
    report_date: str | None = None

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            if page_num == 1:
                report_date = extract_report_date(page)
            records.extend(words_to_rows(page))

    return {
        "metadata": {
            "source": "Frederick County Commissioner of the Revenue",
            "source_url": SOURCE_URL,
            "description": "Businesses Licensed in Frederick County",
            "report_date": report_date or date.today().isoformat(),
            "processed_date": datetime.now().isoformat(),
            "total_records": len(records),
        },
        "records": records,
    }


def main():
    if not PDF_PATH.exists():
        print(f"ERROR: PDF not found at {PDF_PATH}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing {PDF_PATH.name} ...")
    data = parse()
    n = data["metadata"]["total_records"]
    print(f"  {n:,} records  (report date: {data['metadata']['report_date']})")

    # Spot-check: count records where owner_name was captured
    with_owner = sum(1 for r in data["records"] if r["owner_name"])
    print(f"  {with_owner:,} have owner names ({with_owner/n*100:.0f}%)")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Written → {OUT_PATH}  ({OUT_PATH.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
