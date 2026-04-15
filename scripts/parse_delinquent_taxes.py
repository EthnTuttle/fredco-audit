#!/usr/bin/env python3
"""
Parse Frederick County delinquent real estate tax PDF into structured JSON.

Source: https://frdnet.fcva.us/REDLQTAXES.pdf
Format: Fixed-width three-column PDF (Parcel ID | Owner Name | Amount)
Updated: daily by the county

Page 1 is a disclaimer; data starts on page 2.

Uses pdfplumber word-level extraction with x-position column splits:
  Parcel ID:  x0 < 133
  Owner name: 133 <= x0 < 420
  Amount:     x0 >= 420  (always starts with '$')

Output: data/processed/delinquent_real_estate_taxes.json
"""

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path

import pdfplumber

PDF_PATH = Path(__file__).parent.parent / "data" / "raw" / "misc" / "REDLQTAXES.pdf"
OUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "delinquent_real_estate_taxes.json"
SOURCE_URL = "https://frdnet.fcva.us/REDLQTAXES.pdf"

# x-coordinate boundaries (verified from word positions)
OWNER_START_X = 133
AMOUNT_START_X = 410

AMOUNT_RE = re.compile(r"^\$([\d,]+\.\d{2})$")


def extract_run_date(page) -> str | None:
    """Pull the run date from page header words."""
    for word in page.extract_words():
        m = re.match(r"DATE:(\d{1,2}/\d{1,2}/\d{4})", word["text"], re.IGNORECASE)
        if m:
            try:
                return datetime.strptime(m.group(1), "%m/%d/%Y").strftime("%Y-%m-%d")
            except ValueError:
                pass
    return None


def words_to_rows(page) -> list[dict]:
    """Convert page words to tax records using x-position column split."""
    words = page.extract_words(x_tolerance=3, y_tolerance=3)

    by_y: dict[int, list] = defaultdict(list)
    for w in words:
        by_y[round(w["top"])].append(w)

    rows = []
    for y in sorted(by_y):
        line_words = sorted(by_y[y], key=lambda w: w["x0"])

        parcel_words = [w["text"] for w in line_words if w["x0"] < OWNER_START_X]
        owner_words  = [w["text"] for w in line_words if OWNER_START_X <= w["x0"] < AMOUNT_START_X]
        amount_words = [w["text"] for w in line_words if w["x0"] >= AMOUNT_START_X]

        if not parcel_words or not amount_words:
            continue

        # Amount must be a dollar value
        amount_str = " ".join(amount_words)
        m = AMOUNT_RE.match(amount_str)
        if not m:
            continue

        try:
            amount = float(m.group(1).replace(",", ""))
        except ValueError:
            continue

        parcel_id = " ".join(parcel_words)
        owner_name = " ".join(owner_words) if owner_words else None

        rows.append({
            "parcel_id": parcel_id,
            "owner_name": owner_name,
            "amount_delinquent": amount,
        })

    return rows


def parse(pdf_path: Path = PDF_PATH) -> dict:
    records: list[dict] = []
    report_date: str | None = None

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            # Pick up run date from any page header
            if report_date is None:
                report_date = extract_run_date(page)

            # Page 1 is the disclaimer
            if page_num == 1:
                continue

            records.extend(words_to_rows(page))

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

    print(f"Parsing {PDF_PATH.name} ...")
    data = parse()
    records = data["records"]
    n = len(records)
    total = sum(r["amount_delinquent"] for r in records)
    print(f"  {n:,} records  (report date: {data['metadata']['report_date']})")
    print(f"  Total delinquent: ${total:,.2f}")

    # Spot-check a few records
    print("  Sample records:")
    for r in records[:5]:
        print(f"    {r['parcel_id']!r:25s}  {str(r['owner_name'])!r:35s}  ${r['amount_delinquent']:,.2f}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Written → {OUT_PATH}  ({OUT_PATH.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
