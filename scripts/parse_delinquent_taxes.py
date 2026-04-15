#!/usr/bin/env python3
"""
Parse Frederick County delinquent real estate tax PDF into structured JSON.

Source: https://frdnet.fcva.us/REDLQTAXES.pdf
Format: Fixed-width monospace text (Parcel ID | Owner Name | Amount Delinquent)
Updated: daily by the county

Page 1 is a disclaimer page; data starts on page 2.

Output: data/processed/delinquent_real_estate_taxes.json
"""

import json
import re
import sys
from datetime import datetime, date
from pathlib import Path

import pdfplumber

PDF_PATH = Path(__file__).parent.parent / "data" / "raw" / "misc" / "REDLQTAXES.pdf"
OUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "delinquent_real_estate_taxes.json"

SOURCE_URL = "https://frdnet.fcva.us/REDLQTAXES.pdf"

# Matches the dollar amount at end of a data line: e.g. "$8,503.59"
AMOUNT_RE = re.compile(r"\s+\$([\d,]+\.\d{2})\s*$")

# Lines to skip
SKIP_PATTERNS = [
    re.compile(r"^\s*$"),
    re.compile(r"RUN DATE:", re.IGNORECASE),
    re.compile(r"DELINQUENT REAL ESTATE TAXES", re.IGNORECASE),
    re.compile(r"\*\*\*\*\s*END OF REPORT", re.IGNORECASE),
    re.compile(r"This list of delinquent", re.IGNORECASE),
    re.compile(r"is subject to correction", re.IGNORECASE),
    re.compile(r"made subsequent", re.IGNORECASE),
    re.compile(r"Detail information", re.IGNORECASE),
    re.compile(r"may be obtained", re.IGNORECASE),
    re.compile(r"HTTPS?://", re.IGNORECASE),
    re.compile(r"and then clicking", re.IGNORECASE),
]


def should_skip(line: str) -> bool:
    return any(p.search(line) for p in SKIP_PATTERNS)


def extract_run_date(text: str) -> str | None:
    """Extract RUN DATE from page header (e.g. 'RUN DATE:  4/13/2026')."""
    m = re.search(r"RUN DATE:\s*(\d{1,2}/\d{1,2}/(\d{4}))", text, re.IGNORECASE)
    if m:
        try:
            return datetime.strptime(m.group(1), "%m/%d/%Y").strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def parse_data_line(line: str) -> dict | None:
    """Parse one data line into {parcel_id, owner_name, amount_delinquent}.

    Line format (fixed-width):
        PARCEL_ID   OWNER NAME                    $AMOUNT.CC
    """
    # Must end with a dollar amount
    m = AMOUNT_RE.search(line)
    if not m:
        return None

    amount_str = m.group(1).replace(",", "")
    try:
        amount = float(amount_str)
    except ValueError:
        return None

    # Strip the amount (and leading whitespace before it) from the line
    rest = line[: m.start()].strip()
    if not rest:
        return None

    # Split parcel ID from owner name on the first run of 2+ spaces.
    # Parcel IDs use single spaces between components (e.g. "58A01 X 6 22");
    # the column separator is always 2+ spaces.
    parts = re.split(r" {2,}", rest, maxsplit=1)
    parcel_id = parts[0].strip()
    owner_name = parts[1].strip() if len(parts) > 1 else None

    if not parcel_id:
        return None

    # Normalise parcel: collapse internal runs of spaces to a single space
    parcel_id = re.sub(r" +", " ", parcel_id)

    return {
        "parcel_id": parcel_id,
        "owner_name": owner_name if owner_name else None,
        "amount_delinquent": amount,
    }


def parse(pdf_path: Path = PDF_PATH) -> dict:
    records: list[dict] = []
    report_date: str | None = None

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""

            # Pick up the run date from any page that carries it
            if report_date is None:
                report_date = extract_run_date(text)

            # Page 1 is the disclaimer; skip its lines for data but keep for date
            if page_num == 1:
                continue

            for line in text.splitlines():
                if should_skip(line):
                    continue
                record = parse_data_line(line)
                if record:
                    records.append(record)

    return {
        "metadata": {
            "source": "Frederick County Commissioner of the Revenue",
            "source_url": SOURCE_URL,
            "description": "Delinquent Real Estate Tax Accounts - Frederick County",
            "report_date": report_date or date.today().isoformat(),
            "processed_date": datetime.now().isoformat(),
            "total_records": len(records),
            "note": (
                "Subject to correction for payments made subsequent "
                "to report preparation."
            ),
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
    total = sum(r["amount_delinquent"] for r in data["records"])
    print(
        f"  Parsed {n:,} delinquent tax records "
        f"(report date: {data['metadata']['report_date']}, "
        f"total delinquent: ${total:,.2f})"
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Written → {OUT_PATH}  ({OUT_PATH.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
