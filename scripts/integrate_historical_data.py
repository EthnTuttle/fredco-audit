#!/usr/bin/env python3
"""
Integrate historical NCES F-33 data with existing processed data.

This creates a complete time series from FY2019-FY2024 for all target districts.
"""

import json
from datetime import datetime
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
NCES_DIR = PROCESSED_DIR / "nces"
ANALYSIS_DIR = BASE_DIR / "data" / "analysis"

DIVISION_CODES = {
    "069": "Frederick County",
    "043": "Clarke County",
    "061": "Fauquier County",
    "171": "Shenandoah County",
    "187": "Warren County",
    "107": "Loudoun County",
}

BENCHMARKS = {
    "admin_ratio_target": 5.0,
    "admin_ratio_warning": 10.0,
    "instruction_ratio_target": 65.0,
    "instruction_ratio_warning": 60.0,
    "per_pupil_admin_warning": 1200,
}


def load_json(filepath: Path) -> list | dict:
    """Load JSON file."""
    if filepath.exists():
        with open(filepath) as f:
            return json.load(f)
    return []


def main():
    print("Integrating historical data...")
    
    # Load historical NCES F-33 data (FY2019-FY2022)
    f33_data = load_json(NCES_DIR / "f33_virginia_districts.json")
    
    # Load existing VPAP FY2024 data
    existing_expenditures = load_json(PROCESSED_DIR / "expenditures.json")
    vpap_records = [r for r in existing_expenditures.get("records", []) 
                   if r.get("source") == "VPAP"]
    
    # Build unified data structure
    unified_data = {
        "metadata": {
            "description": "Complete time series data for FCPS audit (FY2019-FY2024)",
            "sources": [
                {"name": "NCES F-33 School District Finance Survey", "years": "FY2019-FY2022"},
                {"name": "VPAP Instructional Spending", "years": "FY2024"},
            ],
            "generated_date": datetime.now().isoformat(),
            "note": "FY2023 data not yet available from NCES",
        },
        "records": [],
    }
    
    # Add F-33 historical data
    for record in f33_data:
        unified_record = {
            "fiscal_year": record["fiscal_year"],
            "division_code": record["vdoe_code"],
            "division_name": record["division_name"],
            "source": "NCES F-33",
            "enrollment": record["enrollment"],
            "expenditures": {
                "total": record["total_expenditures"],
                "current": record["current_expenditures"],
                "instruction": record["instruction_expenditures"],
                "administration": record["total_administration"],
                "support_services": record["support_services"],
                "operations": record.get("operations_maintenance", 0),
                "capital_outlay": record["capital_outlay"],
            },
            "revenue": {
                "total": record["total_revenue"],
                "federal": record["federal_revenue"],
                "state": record["state_revenue"],
                "local": record["local_revenue"],
            },
            "per_pupil": {
                "total": record["per_pupil_total"],
                "instruction": record["per_pupil_instruction"],
                "administration": record["per_pupil_admin"],
            },
            "ratios": {
                "instruction_pct": record["instruction_pct"],
                "administration_pct": record["admin_pct"],
            },
        }
        unified_data["records"].append(unified_record)
    
    # Add VPAP FY2024 data
    for record in vpap_records:
        if record.get("data", {}).get("total_spending"):
            unified_record = {
                "fiscal_year": record["fiscal_year"],
                "division_code": record["division_code"],
                "division_name": record["division_name"],
                "source": "VPAP",
                "enrollment": None,  # Not in VPAP data
                "expenditures": {
                    "instruction": record["data"].get("instructional_total"),
                    "other": record["data"].get("other_total"),
                    "total": record["data"].get("total_spending"),
                },
                "per_pupil": {
                    "instruction": record["per_pupil"].get("instructional_pp"),
                    "other": record["per_pupil"].get("other_pp"),
                    "total": record["per_pupil"].get("total_pp"),
                },
                "ratios": {
                    "instruction_pct": record.get("calculated_ratios", {}).get("instruction_pct"),
                },
            }
            unified_data["records"].append(unified_record)
    
    # Sort by division and fiscal year
    unified_data["records"].sort(key=lambda x: (x["division_code"], x["fiscal_year"]))
    
    # Save unified expenditures
    unified_file = PROCESSED_DIR / "expenditures_complete.json"
    with open(unified_file, "w") as f:
        json.dump(unified_data, f, indent=2)
    print(f"Created: {unified_file}")
    
    # Build ratios.json for dashboards
    ratios_output = {
        "processed_date": datetime.now().isoformat(),
        "benchmarks": BENCHMARKS,
        "data_sources": unified_data["metadata"]["sources"],
        "divisions": [],
        "comparison_matrix": {
            "latest_year": "FY2024",
            "divisions": list(DIVISION_CODES.values()),
            "comparisons": [],
        },
    }
    
    # Group records by division
    for div_code, div_name in DIVISION_CODES.items():
        div_records = [r for r in unified_data["records"] if r["division_code"] == div_code]
        
        division_data = {
            "division_code": div_code,
            "division_name": div_name,
            "fiscal_years": sorted(set(r["fiscal_year"] for r in div_records)),
            "metrics_by_year": [],
        }
        
        for record in div_records:
            year_metrics = {
                "fiscal_year": record["fiscal_year"],
                "source": record["source"],
                "enrollment": record.get("enrollment", 0),
                "expenditures": record.get("expenditures", {}),
                "per_pupil": record.get("per_pupil", {}),
                "ratios": record.get("ratios", {}),
                "revenue": record.get("revenue", {}),
                "red_flags": [],
            }
            
            # Check for red flags
            admin_pct = year_metrics["ratios"].get("administration_pct")
            if admin_pct and admin_pct > BENCHMARKS["admin_ratio_warning"]:
                year_metrics["red_flags"].append({
                    "indicator": "admin_ratio",
                    "value": admin_pct,
                    "threshold": BENCHMARKS["admin_ratio_warning"],
                    "severity": "high",
                    "message": f"Admin spending ({admin_pct:.1f}%) exceeds {BENCHMARKS['admin_ratio_warning']}% threshold",
                })
            elif admin_pct and admin_pct > BENCHMARKS["admin_ratio_target"]:
                year_metrics["red_flags"].append({
                    "indicator": "admin_ratio",
                    "value": admin_pct,
                    "threshold": BENCHMARKS["admin_ratio_target"],
                    "severity": "medium",
                    "message": f"Admin spending ({admin_pct:.1f}%) above {BENCHMARKS['admin_ratio_target']}% target",
                })
            
            instr_pct = year_metrics["ratios"].get("instruction_pct")
            if instr_pct and instr_pct < BENCHMARKS["instruction_ratio_warning"]:
                year_metrics["red_flags"].append({
                    "indicator": "instruction_ratio",
                    "value": instr_pct,
                    "threshold": BENCHMARKS["instruction_ratio_warning"],
                    "severity": "high",
                    "message": f"Instruction ({instr_pct:.1f}%) below {BENCHMARKS['instruction_ratio_warning']}% minimum",
                })
            
            pp_admin = year_metrics["per_pupil"].get("administration")
            if pp_admin and pp_admin > BENCHMARKS["per_pupil_admin_warning"]:
                year_metrics["red_flags"].append({
                    "indicator": "per_pupil_admin",
                    "value": pp_admin,
                    "threshold": BENCHMARKS["per_pupil_admin_warning"],
                    "severity": "medium",
                    "message": f"Per-pupil admin (${pp_admin:.0f}) exceeds ${BENCHMARKS['per_pupil_admin_warning']}",
                })
            
            division_data["metrics_by_year"].append(year_metrics)
        
        # Calculate trends
        if len(division_data["fiscal_years"]) >= 2:
            sorted_metrics = sorted(
                division_data["metrics_by_year"],
                key=lambda x: x["fiscal_year"]
            )
            division_data["trends"] = {
                "years": [m["fiscal_year"] for m in sorted_metrics],
                "enrollment_trend": [m.get("enrollment") or 0 for m in sorted_metrics],
                "per_pupil_trend": [m["per_pupil"].get("total") or 0 for m in sorted_metrics],
                "admin_pct_trend": [m["ratios"].get("administration_pct") or 0 for m in sorted_metrics],
                "instruction_pct_trend": [m["ratios"].get("instruction_pct") or 0 for m in sorted_metrics],
            }
            
            # Calculate growth rates
            first_enroll = division_data["trends"]["enrollment_trend"][0]
            last_enroll = [e for e in division_data["trends"]["enrollment_trend"] if e][-1] if any(division_data["trends"]["enrollment_trend"]) else 0
            if first_enroll > 0 and last_enroll > 0:
                division_data["trends"]["enrollment_growth_pct"] = round(
                    ((last_enroll - first_enroll) / first_enroll) * 100, 2
                )
            
            first_pp = division_data["trends"]["per_pupil_trend"][0]
            last_pp = [p for p in division_data["trends"]["per_pupil_trend"] if p][-1] if any(division_data["trends"]["per_pupil_trend"]) else 0
            if first_pp > 0 and last_pp > 0:
                division_data["trends"]["per_pupil_growth_pct"] = round(
                    ((last_pp - first_pp) / first_pp) * 100, 2
                )
        
        ratios_output["divisions"].append(division_data)
        
        # Add to comparison matrix (use FY2022 for admin data, FY2024 for instruction)
        fy2022_metrics = next((m for m in division_data["metrics_by_year"] if m["fiscal_year"] == "FY2022"), None)
        fy2024_metrics = next((m for m in division_data["metrics_by_year"] if m["fiscal_year"] == "FY2024"), None)
        
        comparison = {
            "division_code": div_code,
            "division_name": div_name,
            "enrollment": fy2022_metrics["enrollment"] if fy2022_metrics else 0,
            "per_pupil_total": fy2022_metrics["per_pupil"].get("total", 0) if fy2022_metrics else 0,
            "per_pupil_instruction": fy2024_metrics["per_pupil"].get("instruction", 0) if fy2024_metrics else (fy2022_metrics["per_pupil"].get("instruction", 0) if fy2022_metrics else 0),
            "per_pupil_admin": fy2022_metrics["per_pupil"].get("administration", 0) if fy2022_metrics else 0,
            "admin_ratio": fy2022_metrics["ratios"].get("administration_pct", 0) if fy2022_metrics else 0,
            "instruction_ratio": fy2024_metrics["ratios"].get("instruction_pct", 0) if fy2024_metrics else (fy2022_metrics["ratios"].get("instruction_pct", 0) if fy2022_metrics else 0),
        }
        ratios_output["comparison_matrix"]["comparisons"].append(comparison)
    
    # Calculate peer averages
    comparisons = ratios_output["comparison_matrix"]["comparisons"]
    numeric_fields = ["enrollment", "per_pupil_total", "per_pupil_instruction",
                     "per_pupil_admin", "admin_ratio", "instruction_ratio"]
    peer_avg = {"division_name": "Peer Average"}
    
    for field in numeric_fields:
        values = [c.get(field, 0) for c in comparisons if c.get(field, 0) and c.get(field, 0) > 0]
        if values:
            peer_avg[field] = round(sum(values) / len(values), 2)
    
    ratios_output["comparison_matrix"]["peer_average"] = peer_avg
    
    # Save ratios file
    ratios_file = PROCESSED_DIR / "ratios.json"
    with open(ratios_file, "w") as f:
        json.dump(ratios_output, f, indent=2)
    print(f"Updated: {ratios_file}")
    
    # Save trends file
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    trends_file = ANALYSIS_DIR / "trends.json"
    trends_output = {
        "processed_date": datetime.now().isoformat(),
        "divisions": [
            {
                "division_code": d["division_code"],
                "division_name": d["division_name"],
                "trends": d.get("trends", {}),
            }
            for d in ratios_output["divisions"]
        ],
    }
    with open(trends_file, "w") as f:
        json.dump(trends_output, f, indent=2)
    print(f"Updated: {trends_file}")
    
    # Save benchmarks file
    benchmarks_file = ANALYSIS_DIR / "benchmarks.json"
    with open(benchmarks_file, "w") as f:
        json.dump({
            "processed_date": datetime.now().isoformat(),
            "benchmarks": BENCHMARKS,
            "comparison_matrix": ratios_output["comparison_matrix"],
        }, f, indent=2)
    print(f"Updated: {benchmarks_file}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("HISTORICAL DATA INTEGRATION COMPLETE")
    print("=" * 60)
    
    print(f"\nTotal records: {len(unified_data['records'])}")
    print(f"Divisions: {len(ratios_output['divisions'])}")
    print(f"Years covered: FY2019-FY2024 (FY2023 unavailable)")
    
    # Print Frederick County trends
    print("\n" + "-" * 60)
    print("FREDERICK COUNTY TREND ANALYSIS")
    print("-" * 60)
    
    frederick = next((d for d in ratios_output["divisions"] if d["division_code"] == "069"), None)
    if frederick:
        print(f"\nFiscal Years: {', '.join(frederick['fiscal_years'])}")
        
        if "trends" in frederick:
            trends = frederick["trends"]
            print(f"\nEnrollment: {trends['enrollment_trend'][0]:,} -> {trends['enrollment_trend'][-1] or 'N/A':,}")
            if "enrollment_growth_pct" in trends:
                print(f"  Growth: {trends['enrollment_growth_pct']:+.1f}%")
            
            print(f"\nPer-Pupil Spending: ${trends['per_pupil_trend'][0]:,.0f} -> ${trends['per_pupil_trend'][-2] or trends['per_pupil_trend'][-1]:,.0f}")
            if "per_pupil_growth_pct" in trends:
                print(f"  Growth: {trends['per_pupil_growth_pct']:+.1f}%")
            
            print(f"\nAdmin % of Current Spending:")
            for year, pct in zip(trends["years"], trends["admin_pct_trend"]):
                if pct:
                    flag = " [FLAG]" if pct > 10 else ""
                    print(f"  {year}: {pct:.1f}%{flag}")
            
            print(f"\nInstruction % of Current Spending:")
            for year, pct in zip(trends["years"], trends["instruction_pct_trend"]):
                if pct:
                    flag = " [FLAG]" if pct < 60 else ""
                    print(f"  {year}: {pct:.1f}%{flag}")
        
        # Count red flags
        total_flags = sum(len(m.get("red_flags", [])) for m in frederick["metrics_by_year"])
        print(f"\nTotal red flags: {total_flags}")
        
        for m in frederick["metrics_by_year"]:
            for flag in m.get("red_flags", []):
                print(f"  - {m['fiscal_year']}: {flag['message']}")


if __name__ == "__main__":
    main()
