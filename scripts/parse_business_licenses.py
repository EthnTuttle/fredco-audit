#!/usr/bin/env python3
"""
Parse Frederick County business license PDF into structured JSON.

Source: https://frdnet.fcva.us/buslicinfc.pdf
Format: Fixed-width monospace text, two columns (Trade Name | Owner Name)
Updated: daily by the county

Output: data/processed/business_licenses.json
"""

import json
import re
import sys
from datetime import datetime, date
from pathlib import Path

import pdfplumber

PDF_PATH = Path(__file__).parent.parent / "data" / "raw" / "misc" / "buslicinfc.pdf"
OUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "business_licenses.json"

SOURCE_URL = "https://frdnet.fcva.us/buslicinfc.pdf"

# Lines to skip (header / column-header patterns)
SKIP_PATTERNS = [
    re.compile(r"^Businesses Licensed", re.IGNORECASE),
    re.compile(r"^Date:\s*"),
    re.compile(r"^Trade Name\s+Name"),
    re.compile(r"^\s*Page:\s*\d+"),
    re.compile(r"^\s*$"),
]


def should_skip(line: str) -> bool:
    return any(p.search(line) for p in SKIP_PATTERNS)


def parse_data_line(line: str) -> tuple[str, str | None] | None:
    """Split a data line into (trade_name, owner_name).

    Lines are fixed-width.  The two columns are separated by two or more
    consecutive spaces.  When the Name column contains only '.' the owner
    is unknown (→ None).
    """
    stripped = line.strip()
    if not stripped:
        return None

    # Split on first run of 2+ spaces
    parts = re.split(r" {2,}", stripped, maxsplit=1)
    trade_name = parts[0].strip()
    if not trade_name:
        return None

    raw_name = parts[1].strip() if len(parts) > 1 else ""
    owner_name: str | None = None if raw_name in ("", ".") else raw_name

    return trade_name, owner_name


def extract_report_date(text: str) -> str:
    """Pull the report date from the first few lines of page 1."""
    m = re.search(r"Date:\s*(\d{1,2}/\d{1,2}/(\d{4}))", text)
    if m:
        # Reformat M/D/YYYY → YYYY-MM-DD
        try:
            return datetime.strptime(m.group(1), "%m/%d/%Y").strftime("%Y-%m-%d")
        except ValueError:
            pass
    return date.today().isoformat()


def parse(pdf_path: Path = PDF_PATH) -> dict:
    records: list[dict] = []
    report_date: str | None = None

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""

            if page_num == 1:
                report_date = extract_report_date(text)

            for line in text.splitlines():
                if should_skip(line):
                    continue
                result = parse_data_line(line)
                if result is None:
                    continue
                trade_name, owner_name = result
                records.append({"trade_name": trade_name, "owner_name": owner_name})

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

    print(f"Parsing {PDF_PATH} ...")
    data = parse()
    n = data["metadata"]["total_records"]
    print(f"  Parsed {n:,} business license records (report date: {data['metadata']['report_date']})")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Written → {OUT_PATH}  ({OUT_PATH.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
