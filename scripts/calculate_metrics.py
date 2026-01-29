#!/usr/bin/env python3
"""
Calculate audit metrics and ratios from processed data.

Usage:
    python scripts/calculate_metrics.py --output data/processed/ratios.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
ANALYSIS_DIR = DATA_DIR / "analysis"

# Division codes
DIVISION_CODES = {
    "069": "Frederick County",
    "043": "Clarke County",
    "061": "Fauquier County",
    "171": "Shenandoah County",
    "187": "Warren County",
    "107": "Loudoun County",
}

# Benchmark targets
BENCHMARKS = {
    "admin_ratio_target": 5.0,  # Target: <5% admin spending
    "admin_ratio_warning": 10.0,  # Warning: >10% admin spending
    "instruction_ratio_target": 65.0,  # Target: >65% instruction spending
    "instruction_ratio_warning": 60.0,  # Warning: <60% instruction
    "admin_to_student_target": 250,  # Target: 1 admin per 250+ students
    "admin_to_student_warning": 150,  # Warning: 1 admin per <150 students
    "teacher_to_student_target": 15,  # Target: 1 teacher per 15 students
    "per_pupil_admin_warning": 1200,  # Warning: >$1,200 per pupil admin
}


def load_processed_data() -> dict[str, Any]:
    """Load all processed data from JSON files."""
    data = {
        "enrollment": [],
        "expenditures": [],
        "staffing": [],
        "vdoe": {},
        "apa": {},
    }
    
    # Load individual JSON files
    for json_file in PROCESSED_DIR.glob("*.json"):
        try:
            with open(json_file) as f:
                content = json.load(f)
                
            if "enrollment" in json_file.name.lower():
                data["enrollment"].append(content)
            elif "expenditure" in json_file.name.lower():
                data["expenditures"].append(content)
            elif "staffing" in json_file.name.lower():
                data["staffing"].append(content)
            elif "vdoe" in json_file.name.lower():
                data["vdoe"] = content
            elif "apa" in json_file.name.lower():
                data["apa"] = content
                
        except (json.JSONDecodeError, IOError) as e:
            print(f"  Warning: Could not load {json_file.name}: {e}")
    
    return data


def calculate_per_pupil_metrics(expenditures: dict, enrollment: float) -> dict[str, float]:
    """
    Calculate per-pupil spending metrics.
    
    Args:
        expenditures: Dictionary with expenditure categories
        enrollment: ADM (Average Daily Membership)
    
    Returns:
        Dictionary of per-pupil amounts
    """
    if enrollment <= 0:
        return {}
    
    per_pupil = {}
    
    # Map expenditure keys to per-pupil metrics
    key_mapping = {
        "total": "total",
        "instruction": "instruction",
        "administration": "administration",
        "pupil_transportation": "transportation",
        "operations_maintenance": "operations",
        "facilities": "facilities",
        "debt_service": "debt_service",
        "technology": "technology",
    }
    
    for exp_key, pp_key in key_mapping.items():
        if exp_key in expenditures and expenditures[exp_key] > 0:
            per_pupil[pp_key] = round(expenditures[exp_key] / enrollment, 2)
    
    return per_pupil


def calculate_spending_ratios(expenditures: dict) -> dict[str, float]:
    """
    Calculate spending ratios (percentages).
    
    Args:
        expenditures: Dictionary with expenditure categories
    
    Returns:
        Dictionary of percentage ratios
    """
    total = expenditures.get("total", 0)
    
    if total <= 0:
        return {}
    
    ratios = {}
    
    # Calculate percentage for each category
    categories = [
        "instruction", "administration", "pupil_transportation",
        "operations_maintenance", "facilities", "debt_service", "technology"
    ]
    
    for category in categories:
        if category in expenditures:
            ratios[f"{category}_pct"] = round(
                (expenditures[category] / total) * 100, 2
            )
    
    return ratios


def calculate_staff_ratios(staffing: dict, enrollment: float) -> dict[str, float]:
    """
    Calculate staff-to-student and staff-to-staff ratios.
    
    Args:
        staffing: Dictionary with staff counts
        enrollment: ADM
    
    Returns:
        Dictionary of ratios
    """
    ratios = {}
    
    teachers = staffing.get("teachers", 0)
    admins = staffing.get("administrators", 0)
    
    if enrollment > 0 and teachers > 0:
        ratios["teacher_to_student"] = round(enrollment / teachers, 1)
    
    if enrollment > 0 and admins > 0:
        ratios["admin_to_student"] = round(enrollment / admins, 1)
    
    if teachers > 0 and admins > 0:
        ratios["admin_to_teacher"] = round(teachers / admins, 1)
    
    return ratios


def identify_red_flags(metrics: dict) -> list[dict]:
    """
    Identify potential red flags based on benchmark thresholds.
    
    Args:
        metrics: Dictionary of calculated metrics
    
    Returns:
        List of red flag dictionaries
    """
    flags = []
    
    # Check admin spending ratio
    admin_pct = metrics.get("ratios", {}).get("administration_pct", 0)
    if admin_pct > BENCHMARKS["admin_ratio_warning"]:
        flags.append({
            "indicator": "admin_ratio",
            "value": admin_pct,
            "threshold": BENCHMARKS["admin_ratio_warning"],
            "severity": "high",
            "message": f"Administrative spending ratio ({admin_pct}%) exceeds {BENCHMARKS['admin_ratio_warning']}% threshold",
        })
    elif admin_pct > BENCHMARKS["admin_ratio_target"]:
        flags.append({
            "indicator": "admin_ratio",
            "value": admin_pct,
            "threshold": BENCHMARKS["admin_ratio_target"],
            "severity": "medium",
            "message": f"Administrative spending ratio ({admin_pct}%) above {BENCHMARKS['admin_ratio_target']}% target",
        })
    
    # Check instruction ratio
    instruction_pct = metrics.get("ratios", {}).get("instruction_pct", 0)
    if instruction_pct > 0 and instruction_pct < BENCHMARKS["instruction_ratio_warning"]:
        flags.append({
            "indicator": "instruction_ratio",
            "value": instruction_pct,
            "threshold": BENCHMARKS["instruction_ratio_warning"],
            "severity": "high",
            "message": f"Instruction spending ratio ({instruction_pct}%) below {BENCHMARKS['instruction_ratio_warning']}% minimum",
        })
    elif instruction_pct > 0 and instruction_pct < BENCHMARKS["instruction_ratio_target"]:
        flags.append({
            "indicator": "instruction_ratio",
            "value": instruction_pct,
            "threshold": BENCHMARKS["instruction_ratio_target"],
            "severity": "medium",
            "message": f"Instruction spending ratio ({instruction_pct}%) below {BENCHMARKS['instruction_ratio_target']}% target",
        })
    
    # Check admin-to-student ratio
    admin_to_student = metrics.get("staff_ratios", {}).get("admin_to_student", 0)
    if admin_to_student > 0 and admin_to_student < BENCHMARKS["admin_to_student_warning"]:
        flags.append({
            "indicator": "admin_to_student",
            "value": admin_to_student,
            "threshold": BENCHMARKS["admin_to_student_warning"],
            "severity": "high",
            "message": f"Admin-to-student ratio (1:{admin_to_student}) below 1:{BENCHMARKS['admin_to_student_warning']} threshold",
        })
    elif admin_to_student > 0 and admin_to_student < BENCHMARKS["admin_to_student_target"]:
        flags.append({
            "indicator": "admin_to_student",
            "value": admin_to_student,
            "threshold": BENCHMARKS["admin_to_student_target"],
            "severity": "medium",
            "message": f"Admin-to-student ratio (1:{admin_to_student}) below 1:{BENCHMARKS['admin_to_student_target']} target",
        })
    
    # Check per-pupil admin spending
    per_pupil_admin = metrics.get("per_pupil", {}).get("administration", 0)
    if per_pupil_admin > BENCHMARKS["per_pupil_admin_warning"]:
        flags.append({
            "indicator": "per_pupil_admin",
            "value": per_pupil_admin,
            "threshold": BENCHMARKS["per_pupil_admin_warning"],
            "severity": "medium",
            "message": f"Per-pupil admin spending (${per_pupil_admin}) exceeds ${BENCHMARKS['per_pupil_admin_warning']} threshold",
        })
    
    return flags


def calculate_trends(metrics_by_year: list[dict]) -> dict[str, Any]:
    """
    Calculate year-over-year trends from multi-year data.
    
    Args:
        metrics_by_year: List of metrics dictionaries with fiscal_year
    
    Returns:
        Trend analysis dictionary
    """
    if len(metrics_by_year) < 2:
        return {}
    
    # Sort by fiscal year
    sorted_metrics = sorted(metrics_by_year, key=lambda x: x.get("fiscal_year", ""))
    
    trends = {
        "years": [m.get("fiscal_year") for m in sorted_metrics],
        "enrollment_trend": [],
        "per_pupil_trend": [],
        "admin_ratio_trend": [],
        "instruction_ratio_trend": [],
    }
    
    for metrics in sorted_metrics:
        trends["enrollment_trend"].append(metrics.get("enrollment", 0))
        trends["per_pupil_trend"].append(
            metrics.get("per_pupil", {}).get("total", 0)
        )
        trends["admin_ratio_trend"].append(
            metrics.get("ratios", {}).get("administration_pct", 0)
        )
        trends["instruction_ratio_trend"].append(
            metrics.get("ratios", {}).get("instruction_pct", 0)
        )
    
    # Calculate growth rates
    if len(trends["enrollment_trend"]) >= 2:
        first = trends["enrollment_trend"][0]
        last = trends["enrollment_trend"][-1]
        if first > 0:
            trends["enrollment_growth_pct"] = round(((last - first) / first) * 100, 2)
    
    if len(trends["per_pupil_trend"]) >= 2:
        first = trends["per_pupil_trend"][0]
        last = trends["per_pupil_trend"][-1]
        if first > 0:
            trends["per_pupil_growth_pct"] = round(((last - first) / first) * 100, 2)
    
    return trends


def process_division_data(division_code: str, data: dict) -> dict[str, Any]:
    """
    Process all available data for a single division.
    
    Args:
        division_code: 3-digit division code
        data: Loaded data dictionary
    
    Returns:
        Metrics dictionary for the division
    """
    division_name = DIVISION_CODES.get(division_code, "Unknown")
    
    result = {
        "division_code": division_code,
        "division_name": division_name,
        "fiscal_years": [],
        "metrics_by_year": [],
    }
    
    # Extract data from VDOE tables
    vdoe_data = data.get("vdoe", {})
    if "tables" in vdoe_data:
        for table in vdoe_data["tables"]:
            fiscal_year = table.get("fiscal_year", "Unknown")
            
            # Find this division's data
            for record in table.get("data", []):
                if record.get("division_code") == division_code:
                    year_metrics = {
                        "fiscal_year": fiscal_year,
                        "source": table.get("table", "VDOE"),
                    }
                    
                    # Add enrollment
                    if "enrollment" in record:
                        enrollment = record["enrollment"]
                        year_metrics["enrollment"] = (
                            enrollment.get("adm_total") or
                            enrollment.get("adm") or 0
                        )
                    
                    # Add staffing
                    if "staffing" in record:
                        year_metrics["staffing"] = record["staffing"]
                    
                    # Add salaries
                    if "salaries" in record:
                        year_metrics["salaries"] = record["salaries"]
                    
                    # Add per-pupil (from Table 15)
                    if "per_pupil" in record:
                        year_metrics["per_pupil"] = record["per_pupil"]
                    
                    # Add expenditures
                    if "expenditures" in record:
                        year_metrics["expenditures"] = record["expenditures"]
                    
                    # Calculate staff ratios if we have data
                    if "staffing" in year_metrics and year_metrics.get("enrollment", 0) > 0:
                        year_metrics["staff_ratios"] = calculate_staff_ratios(
                            year_metrics["staffing"],
                            year_metrics["enrollment"]
                        )
                    
                    if fiscal_year not in result["fiscal_years"]:
                        result["fiscal_years"].append(fiscal_year)
                    
                    result["metrics_by_year"].append(year_metrics)
    
    return result


def generate_comparison_matrix(all_metrics: list[dict]) -> dict[str, Any]:
    """
    Generate a comparison matrix across all divisions.
    
    Args:
        all_metrics: List of division metrics dictionaries
    
    Returns:
        Comparison matrix dictionary
    """
    matrix = {
        "divisions": [],
        "latest_year": "",
        "comparisons": [],
    }
    
    # Find latest fiscal year with data
    all_years = set()
    for div_metrics in all_metrics:
        all_years.update(div_metrics.get("fiscal_years", []))
    
    if all_years:
        matrix["latest_year"] = sorted(all_years)[-1]
    
    # Build comparison for latest year
    for div_metrics in all_metrics:
        division = {
            "division_code": div_metrics["division_code"],
            "division_name": div_metrics["division_name"],
        }
        
        # Find latest year's metrics
        for year_metrics in div_metrics.get("metrics_by_year", []):
            if year_metrics.get("fiscal_year") == matrix["latest_year"]:
                division["enrollment"] = year_metrics.get("enrollment", 0)
                division["per_pupil_total"] = year_metrics.get("per_pupil", {}).get("total", 0)
                division["per_pupil_instruction"] = year_metrics.get("per_pupil", {}).get("instruction", 0)
                division["per_pupil_admin"] = year_metrics.get("per_pupil", {}).get("administration", 0)
                division["admin_ratio"] = year_metrics.get("ratios", {}).get("administration_pct", 0)
                division["instruction_ratio"] = year_metrics.get("ratios", {}).get("instruction_pct", 0)
                division["admin_to_student"] = year_metrics.get("staff_ratios", {}).get("admin_to_student", 0)
                break
        
        matrix["divisions"].append(division["division_name"])
        matrix["comparisons"].append(division)
    
    # Calculate averages
    if matrix["comparisons"]:
        avg = {"division_name": "Peer Average"}
        numeric_keys = [
            "enrollment", "per_pupil_total", "per_pupil_instruction",
            "per_pupil_admin", "admin_ratio", "instruction_ratio", "admin_to_student"
        ]
        
        for key in numeric_keys:
            values = [d.get(key, 0) for d in matrix["comparisons"] if d.get(key, 0) > 0]
            if values:
                avg[key] = round(sum(values) / len(values), 2)
        
        matrix["peer_average"] = avg
    
    return matrix


def main():
    parser = argparse.ArgumentParser(
        description="Calculate audit metrics and ratios",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--output",
        type=Path,
        default=PROCESSED_DIR / "ratios.json",
        help="Output file for calculated metrics"
    )
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    
    print("FCPS Metrics Calculator")
    print("=" * 50)
    
    # Load processed data
    print("\nLoading processed data...")
    data = load_processed_data()
    
    # Process each division
    print("\nCalculating metrics for each division...")
    all_metrics = []
    
    for div_code, div_name in DIVISION_CODES.items():
        print(f"  Processing: {div_name} ({div_code})")
        div_metrics = process_division_data(div_code, data)
        
        # Identify red flags for each year
        for year_metrics in div_metrics.get("metrics_by_year", []):
            year_metrics["red_flags"] = identify_red_flags(year_metrics)
        
        # Calculate trends if multi-year data
        if len(div_metrics.get("metrics_by_year", [])) >= 2:
            div_metrics["trends"] = calculate_trends(div_metrics["metrics_by_year"])
        
        all_metrics.append(div_metrics)
    
    # Generate comparison matrix
    print("\nGenerating comparison matrix...")
    comparison = generate_comparison_matrix(all_metrics)
    
    # Compile final output
    output = {
        "processed_date": datetime.now().isoformat(),
        "benchmarks": BENCHMARKS,
        "divisions": all_metrics,
        "comparison_matrix": comparison,
    }
    
    # Save main output
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved: {args.output}")
    
    # Save trends analysis
    trends_output = ANALYSIS_DIR / "trends.json"
    trends_data = {
        "processed_date": datetime.now().isoformat(),
        "divisions": [
            {
                "division_code": m["division_code"],
                "division_name": m["division_name"],
                "trends": m.get("trends", {}),
            }
            for m in all_metrics
        ],
    }
    with open(trends_output, "w") as f:
        json.dump(trends_data, f, indent=2)
    print(f"Saved: {trends_output}")
    
    # Save benchmarks comparison
    benchmarks_output = ANALYSIS_DIR / "benchmarks.json"
    with open(benchmarks_output, "w") as f:
        json.dump({
            "processed_date": datetime.now().isoformat(),
            "benchmarks": BENCHMARKS,
            "comparison_matrix": comparison,
        }, f, indent=2)
    print(f"Saved: {benchmarks_output}")
    
    # Summary
    print("\n" + "=" * 50)
    print("Metrics calculation complete!")
    print(f"\nDivisions processed: {len(all_metrics)}")
    
    # Count red flags
    total_flags = sum(
        len(ym.get("red_flags", []))
        for m in all_metrics
        for ym in m.get("metrics_by_year", [])
    )
    print(f"Red flags identified: {total_flags}")
    
    print("\nNext steps:")
    print("  1. Review ratios.json for detailed metrics")
    print("  2. Review trends.json for year-over-year analysis")
    print("  3. Run generate_dashboards.py for visualizations")


if __name__ == "__main__":
    main()
