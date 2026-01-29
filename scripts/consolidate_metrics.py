#!/usr/bin/env python3
"""
Consolidate all processed data into unified metrics for dashboard generation.

This script reads from the various processed JSON files and creates a unified
ratios.json file optimized for dashboard generation.
"""

import json
from datetime import datetime
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
ANALYSIS_DIR = BASE_DIR / "data" / "analysis"

# Division info
DIVISION_CODES = {
    "069": "Frederick County",
    "043": "Clarke County",
    "061": "Fauquier County",
    "171": "Shenandoah County",
    "187": "Warren County",
    "107": "Loudoun County",
}

# Benchmarks
BENCHMARKS = {
    "admin_ratio_target": 5.0,
    "admin_ratio_warning": 10.0,
    "instruction_ratio_target": 65.0,
    "instruction_ratio_warning": 60.0,
    "admin_to_student_target": 250,
    "admin_to_student_warning": 150,
    "per_pupil_admin_warning": 1200,
}


def load_json(filepath: Path) -> dict:
    """Load JSON file if it exists."""
    if filepath.exists():
        with open(filepath) as f:
            return json.load(f)
    return {}


def main():
    print("Consolidating audit metrics...")
    
    # Load all processed data
    expenditures = load_json(PROCESSED_DIR / "expenditures.json")
    enrollment = load_json(PROCESSED_DIR / "enrollment.json")
    staffing = load_json(PROCESSED_DIR / "staffing.json")
    apa_data = load_json(PROCESSED_DIR / "apa_education_expenditures.json")
    
    # Build consolidated output
    output = {
        "processed_date": datetime.now().isoformat(),
        "benchmarks": BENCHMARKS,
        "data_sources": {
            "nces": "NCES Common Core of Data (FY2022)",
            "vpap": "Virginia Public Access Project (FY2024)",
            "apa": "Virginia Auditor of Public Accounts (FY2024)",
        },
        "divisions": [],
        "comparison_matrix": {
            "latest_year": "FY2024",
            "divisions": list(DIVISION_CODES.values()),
            "comparisons": [],
        },
    }
    
    # Process each division
    for div_code, div_name in DIVISION_CODES.items():
        division_data = {
            "division_code": div_code,
            "division_name": div_name,
            "fiscal_years": [],
            "metrics_by_year": [],
        }
        
        # Get expenditure records for this division
        if "records" in expenditures:
            for record in expenditures["records"]:
                if record.get("division_code") == div_code:
                    fy = record.get("fiscal_year", "Unknown")
                    
                    year_metrics = {
                        "fiscal_year": fy,
                        "source": record.get("source", "Unknown"),
                        "enrollment": 0,
                        "expenditures": record.get("data", {}),
                        "per_pupil": record.get("per_pupil", {}),
                        "ratios": record.get("calculated_ratios", {}),
                        "red_flags": [],
                    }
                    
                    # Get enrollment from enrollment.json
                    if "records" in enrollment:
                        for enroll_rec in enrollment["records"]:
                            if enroll_rec.get("division_code") == div_code and enroll_rec.get("fiscal_year") == fy:
                                year_metrics["enrollment"] = enroll_rec.get("data", {}).get("adm", 0)
                                break
                    
                    # Get staffing from staffing.json
                    if "records" in staffing:
                        for staff_rec in staffing["records"]:
                            if staff_rec.get("division_code") == div_code:
                                year_metrics["staffing"] = staff_rec.get("data", {})
                                break
                    
                    # Identify red flags
                    admin_pct = year_metrics["ratios"].get("administration_pct", 0)
                    if admin_pct and admin_pct > BENCHMARKS["admin_ratio_warning"]:
                        year_metrics["red_flags"].append({
                            "indicator": "admin_ratio",
                            "value": admin_pct,
                            "threshold": BENCHMARKS["admin_ratio_warning"],
                            "severity": "high",
                            "message": f"Admin spending ({admin_pct}%) exceeds {BENCHMARKS['admin_ratio_warning']}% threshold",
                        })
                    elif admin_pct and admin_pct > BENCHMARKS["admin_ratio_target"]:
                        year_metrics["red_flags"].append({
                            "indicator": "admin_ratio",
                            "value": admin_pct,
                            "threshold": BENCHMARKS["admin_ratio_target"],
                            "severity": "medium",
                            "message": f"Admin spending ({admin_pct}%) above {BENCHMARKS['admin_ratio_target']}% target",
                        })
                    
                    instruction_pct = year_metrics["ratios"].get("instruction_pct", 0)
                    if instruction_pct and instruction_pct < BENCHMARKS["instruction_ratio_warning"]:
                        year_metrics["red_flags"].append({
                            "indicator": "instruction_ratio",
                            "value": instruction_pct,
                            "threshold": BENCHMARKS["instruction_ratio_warning"],
                            "severity": "high",
                            "message": f"Instruction spending ({instruction_pct}%) below {BENCHMARKS['instruction_ratio_warning']}% minimum",
                        })
                    
                    per_pupil_admin = year_metrics["per_pupil"].get("administration_pp", 0)
                    if per_pupil_admin and per_pupil_admin > BENCHMARKS["per_pupil_admin_warning"]:
                        year_metrics["red_flags"].append({
                            "indicator": "per_pupil_admin",
                            "value": per_pupil_admin,
                            "threshold": BENCHMARKS["per_pupil_admin_warning"],
                            "severity": "medium",
                            "message": f"Per-pupil admin (${per_pupil_admin}) exceeds ${BENCHMARKS['per_pupil_admin_warning']}",
                        })
                    
                    if fy not in division_data["fiscal_years"]:
                        division_data["fiscal_years"].append(fy)
                    
                    division_data["metrics_by_year"].append(year_metrics)
        
        # Calculate trends if multiple years
        if len(division_data["fiscal_years"]) >= 2:
            sorted_metrics = sorted(
                division_data["metrics_by_year"],
                key=lambda x: x.get("fiscal_year", "")
            )
            division_data["trends"] = {
                "years": [m["fiscal_year"] for m in sorted_metrics],
                "instruction_pct_trend": [
                    m["ratios"].get("instruction_pct", 0) for m in sorted_metrics
                ],
                "admin_pct_trend": [
                    m["ratios"].get("administration_pct", 0) for m in sorted_metrics
                ],
            }
        
        output["divisions"].append(division_data)
        
        # Add to comparison matrix (latest year)
        latest_metrics = None
        for ym in division_data["metrics_by_year"]:
            if ym["fiscal_year"] == "FY2024" or (not latest_metrics and ym["fiscal_year"]):
                latest_metrics = ym
        
        if latest_metrics:
            comparison = {
                "division_code": div_code,
                "division_name": div_name,
                "fiscal_year": latest_metrics["fiscal_year"],
                "enrollment": latest_metrics.get("enrollment", 0),
                "per_pupil_total": latest_metrics.get("per_pupil", {}).get("total_pp", 0) or latest_metrics.get("per_pupil", {}).get("total_expenditures_pp", 0),
                "per_pupil_instruction": latest_metrics.get("per_pupil", {}).get("instructional_pp", 0),
                "per_pupil_admin": latest_metrics.get("per_pupil", {}).get("administration_pp", 0),
                "instruction_ratio": latest_metrics.get("ratios", {}).get("instruction_pct", 0),
                "admin_ratio": latest_metrics.get("ratios", {}).get("administration_pct", 0),
            }
            output["comparison_matrix"]["comparisons"].append(comparison)
    
    # Calculate peer averages
    comparisons = output["comparison_matrix"]["comparisons"]
    if comparisons:
        numeric_fields = ["enrollment", "per_pupil_total", "per_pupil_instruction", 
                        "per_pupil_admin", "instruction_ratio", "admin_ratio"]
        peer_avg = {"division_name": "Peer Average"}
        
        for field in numeric_fields:
            values = [c.get(field, 0) or 0 for c in comparisons if (c.get(field, 0) or 0) > 0]
            if values:
                peer_avg[field] = round(sum(values) / len(values), 2)
        
        output["comparison_matrix"]["peer_average"] = peer_avg
    
    # Add red flags summary from expenditures.json
    if "red_flags" in expenditures:
        output["red_flags_summary"] = expenditures["red_flags"]
    
    # Add data gaps
    if "data_gaps" in expenditures:
        output["data_gaps"] = expenditures["data_gaps"]
    
    # Write output
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    
    ratios_file = PROCESSED_DIR / "ratios.json"
    with open(ratios_file, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Created: {ratios_file}")
    
    # Also create trends.json
    trends_file = ANALYSIS_DIR / "trends.json"
    trends_output = {
        "processed_date": datetime.now().isoformat(),
        "divisions": [
            {
                "division_code": d["division_code"],
                "division_name": d["division_name"],
                "trends": d.get("trends", {}),
            }
            for d in output["divisions"]
        ],
    }
    with open(trends_file, "w") as f:
        json.dump(trends_output, f, indent=2)
    print(f"Created: {trends_file}")
    
    # Create benchmarks.json
    benchmarks_file = ANALYSIS_DIR / "benchmarks.json"
    with open(benchmarks_file, "w") as f:
        json.dump({
            "processed_date": datetime.now().isoformat(),
            "benchmarks": BENCHMARKS,
            "comparison_matrix": output["comparison_matrix"],
            "red_flags": output.get("red_flags_summary", []),
        }, f, indent=2)
    print(f"Created: {benchmarks_file}")
    
    # Print summary
    print("\n" + "=" * 50)
    print("METRICS CONSOLIDATION COMPLETE")
    print("=" * 50)
    print(f"\nDivisions processed: {len(output['divisions'])}")
    
    total_flags = sum(
        len(ym.get("red_flags", []))
        for d in output["divisions"]
        for ym in d.get("metrics_by_year", [])
    )
    print(f"Red flags identified: {total_flags}")
    
    print("\nFrederick County Summary:")
    for d in output["divisions"]:
        if d["division_code"] == "069":
            for ym in d["metrics_by_year"]:
                print(f"  {ym['fiscal_year']} ({ym['source']}):")
                print(f"    - Instruction: {ym['ratios'].get('instruction_pct', 'N/A')}%")
                print(f"    - Admin: {ym['ratios'].get('administration_pct', 'N/A')}%")
                for flag in ym.get("red_flags", []):
                    print(f"    - FLAG: {flag['message']}")


if __name__ == "__main__":
    main()
