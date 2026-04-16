#!/usr/bin/env python3
"""
Join delinquent real estate tax records with GIS parcel attributes.

Matches on normalized parcel ID (strip spaces and dashes from both sides).
Match rate: ~96.6% of delinquent records.

Output: data/processed/delinquent_with_gis.json
"""

import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

GIS_PATH      = Path(__file__).parent.parent / "data" / "processed" / "gis" / "county_parcels.parquet"
DELINQ_PATH   = Path(__file__).parent.parent / "data" / "processed" / "delinquent_real_estate_taxes.json"
OUT_PATH      = Path(__file__).parent.parent / "data" / "processed" / "delinquent_with_gis.json"


def normalize_id(s: str) -> str:
    """Strip spaces and dashes for fuzzy parcel ID matching."""
    return re.sub(r"[\s\-]+", "", str(s).upper())


def load_gis(path: Path) -> pd.DataFrame:
    cols = ["pin", "parcel_code", "owner_address",
            "total_value", "land_value", "improvement_value",
            "acreage", "property_class", "zone", "district",
            "taxmap", "section", "lot", "sublot", "mmagcd"]
    df = pq.read_table(path, columns=cols).to_pandas()
    df["norm_id"] = df["pin"].apply(normalize_id)
    # Drop duplicate norm_ids — keep first (lowest objectid = oldest/canonical record)
    df = df.drop_duplicates(subset="norm_id", keep="first")
    return df


def main():
    print("Loading GIS parcel data ...")
    gis = load_gis(GIS_PATH)
    print(f"  {len(gis):,} unique GIS parcels")

    print("Loading delinquent tax records ...")
    with open(DELINQ_PATH) as f:
        src = json.load(f)
    delinq = pd.DataFrame(src["records"])
    delinq["norm_id"] = delinq["parcel_id"].apply(normalize_id)
    print(f"  {len(delinq):,} delinquent records")

    print("Joining ...")
    gis_cols = ["norm_id", "owner_address", "total_value", "land_value",
                "improvement_value", "acreage", "property_class",
                "zone", "district", "taxmap", "section", "lot", "sublot"]
    merged = delinq.merge(gis[gis_cols], on="norm_id", how="left")

    matched = merged["district"].notna().sum()
    print(f"  {matched:,}/{len(merged):,} records matched ({matched/len(merged)*100:.1f}%)")

    # Coerce NaN → None for JSON serialization
    merged = merged.where(pd.notna(merged), None)

    records = merged.drop(columns=["norm_id"]).to_dict(orient="records")

    out = {
        "metadata": {
            **src["metadata"],
            "description": "Delinquent Real Estate Tax Accounts - Frederick County (with GIS parcel attributes)",
            "gis_source": "Frederick County GIS county_parcels",
            "gis_match_pct": round(matched / len(merged) * 100, 1),
            "joined_date": datetime.now().isoformat(),
        },
        "records": records,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"  Written → {OUT_PATH}  ({OUT_PATH.stat().st_size / 1024:.0f} KB)")

    # Quick district summary
    print("\nDistrict breakdown:")
    by_dist = (merged.groupby("district")["amount_delinquent"]
               .agg(accounts="count", total="sum")
               .sort_values("total", ascending=False))
    for dist, row in by_dist.iterrows():
        print(f"  {dist:20s}  {int(row.accounts):5d} accounts  ${row.total:>12,.2f}")


if __name__ == "__main__":
    main()
