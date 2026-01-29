#!/usr/bin/env python3
"""
FCPS Audit Metrics Calculator
Calculates administrative ratios, peer comparisons, and trend analysis.
"""

import json
from datetime import datetime
from pathlib import Path

# Configuration
DATA_DIR = Path(__file__).parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"
ANALYSIS_DIR = DATA_DIR / "analysis"

# Target and peer divisions
DIVISIONS = {
    "069": "Frederick County",
    "043": "Clarke County", 
    "061": "Fauquier County",
    "171": "Shenandoah County",
    "187": "Warren County",
    "107": "Loudoun County",
    "STATE": "Virginia State"
}

TARGET_DIVISION = "069"

# Red flag thresholds
THRESHOLDS = {
    "admin_ratio_pct": 10.0,  # Admin staff as % of total staff
    "admin_per_1000_students": 3.5,  # Admin positions per 1000 students
    "admin_to_teacher_ratio": 0.05,  # Admin per teacher
    "per_pupil_admin": 1200,  # Per-pupil admin spending
    "admin_growth_vs_enrollment": 2.0,  # Admin growth should not exceed 2x enrollment growth
}


def load_json(filename):
    """Load a JSON file from the processed directory."""
    path = PROCESSED_DIR / filename
    if not path.exists():
        # Try subdirectory
        path = PROCESSED_DIR / "vdoe" / filename
    with open(path) as f:
        return json.load(f)


def normalize_fiscal_year(fy):
    """Convert fiscal year to both formats for matching."""
    if fy.startswith("FY"):
        # FY2024 -> 2023-24
        year = int(fy[2:])
        return [fy, f"{year-1}-{str(year)[-2:]}"]
    elif "-" in fy:
        # 2023-24 -> FY2024
        parts = fy.split("-")
        year = int(parts[0][:2] + parts[1])
        return [fy, f"FY{year}"]
    return [fy]


def get_division_data(data, division_code, fiscal_year=None):
    """Extract data for a specific division and optionally fiscal year."""
    records = data.get("data", [])
    if data.get("state_totals"):
        records = records + data["state_totals"]
    
    filtered = [r for r in records if r["division_code"] == division_code]
    if fiscal_year:
        fy_variants = normalize_fiscal_year(fiscal_year)
        filtered = [r for r in filtered if r["fiscal_year"] in fy_variants]
    return filtered


def calculate_admin_ratios(table18, table19, table8, fiscal_year):
    """Calculate administrative ratios for all divisions."""
    results = {}
    
    for code, name in DIVISIONS.items():
        if code == "STATE":
            continue
            
        # Get data for this division and year
        admin_data = get_division_data(table18, code, fiscal_year)
        instr_data = get_division_data(table19, code, fiscal_year)
        enroll_data = get_division_data(table8, code, fiscal_year)
        
        if not admin_data or not instr_data or not enroll_data:
            continue
            
        admin = admin_data[0]["metrics"]
        instr = instr_data[0]["metrics"]
        enroll = enroll_data[0]["metrics"]
        
        # Extract key values
        admin_positions = admin["summary"]["administrative"]
        total_support_positions = admin["summary"]["total"]
        total_teachers = instr["teaching_positions"]["total_positions"]
        total_instructional = instr["all_instructional"]["positions"]
        adm = enroll["adm_total"]
        
        # Calculate ratios
        total_staff = total_support_positions + total_instructional
        admin_pct = (admin_positions / total_staff) * 100 if total_staff > 0 else 0
        admin_per_1000 = (admin_positions / adm) * 1000 if adm > 0 else 0
        admin_to_teacher = admin_positions / total_teachers if total_teachers > 0 else 0
        students_per_admin = adm / admin_positions if admin_positions > 0 else 0
        
        results[code] = {
            "division_name": name,
            "fiscal_year": fiscal_year,
            "enrollment_adm": adm,
            "admin_positions": admin_positions,
            "total_support_staff": total_support_positions,
            "teaching_positions": total_teachers,
            "total_instructional": total_instructional,
            "total_staff": total_staff,
            "admin_pct_of_total_staff": round(admin_pct, 2),
            "admin_per_1000_students": round(admin_per_1000, 2),
            "admin_to_teacher_ratio": round(admin_to_teacher, 4),
            "students_per_admin": round(students_per_admin, 1),
        }
    
    return results


def calculate_expenditure_analysis(table15, fiscal_year):
    """Calculate per-pupil expenditure comparisons."""
    results = {}
    
    for code, name in DIVISIONS.items():
        exp_data = get_division_data(table15, code, fiscal_year)
        if not exp_data:
            continue
            
        metrics = exp_data[0]["metrics"]
        
        results[code] = {
            "division_name": name,
            "fiscal_year": fiscal_year,
            "adm": metrics["adm"],
            "total_expenditures": metrics["total_expenditures"],
            "total_per_pupil": metrics["total_per_pupil"],
            "local_per_pupil": metrics["local_per_pupil"],
            "state_per_pupil": metrics["state_per_pupil"],
            "federal_per_pupil": metrics["federal_per_pupil"],
            "local_pct": round((metrics["local_per_pupil"] / metrics["total_per_pupil"]) * 100, 1),
            "state_pct": round((metrics["state_per_pupil"] / metrics["total_per_pupil"]) * 100, 1),
            "federal_pct": round((metrics["federal_per_pupil"] / metrics["total_per_pupil"]) * 100, 1),
        }
    
    return results


def calculate_trend_analysis(table8, table15, table18, table19):
    """Calculate 5-year trends for Frederick County."""
    years = ["2019-20", "2020-21", "2021-22", "2022-23", "2023-24"]
    fy_years = ["FY2020", "FY2021", "FY2022", "FY2023", "FY2024"]
    
    trends = {
        "division": "Frederick County (069)",
        "years": years,
        "metrics": {}
    }
    
    # Enrollment trend
    enrollment = []
    for year in years:
        data = get_division_data(table8, TARGET_DIVISION, year)
        if data:
            enrollment.append(data[0]["metrics"]["adm_total"])
        else:
            enrollment.append(None)
    trends["metrics"]["enrollment_adm"] = enrollment
    
    # Per-pupil spending trend
    per_pupil = []
    total_exp = []
    for year in years:
        data = get_division_data(table15, TARGET_DIVISION, year)
        if data:
            per_pupil.append(data[0]["metrics"]["total_per_pupil"])
            total_exp.append(data[0]["metrics"]["total_expenditures"])
        else:
            per_pupil.append(None)
            total_exp.append(None)
    trends["metrics"]["per_pupil_spending"] = per_pupil
    trends["metrics"]["total_expenditures"] = total_exp
    
    # Admin positions trend
    admin_pos = []
    total_support = []
    for fy_year in fy_years:
        data = get_division_data(table18, TARGET_DIVISION, fy_year)
        if data:
            admin_pos.append(data[0]["metrics"]["summary"]["administrative"])
            total_support.append(data[0]["metrics"]["summary"]["total"])
        else:
            admin_pos.append(None)
            total_support.append(None)
    trends["metrics"]["admin_positions"] = admin_pos
    trends["metrics"]["total_support_staff"] = total_support
    
    # Teaching positions trend
    teachers = []
    total_instr = []
    avg_teacher_salary = []
    for fy_year in fy_years:
        data = get_division_data(table19, TARGET_DIVISION, fy_year)
        if data:
            teachers.append(data[0]["metrics"]["teaching_positions"]["total_positions"])
            total_instr.append(data[0]["metrics"]["all_instructional"]["positions"])
            avg_teacher_salary.append(data[0]["metrics"]["teaching_positions"]["total_avg_salary"])
        else:
            teachers.append(None)
            total_instr.append(None)
            avg_teacher_salary.append(None)
    trends["metrics"]["teaching_positions"] = teachers
    trends["metrics"]["total_instructional"] = total_instr
    trends["metrics"]["avg_teacher_salary"] = avg_teacher_salary
    
    # Calculate growth rates (first year to last year with data)
    def calc_growth(values):
        """Calculate growth rate between first and last non-None values."""
        non_none = [(i, v) for i, v in enumerate(values) if v is not None]
        if len(non_none) >= 2:
            first_idx, first_val = non_none[0]
            last_idx, last_val = non_none[-1]
            years_diff = last_idx - first_idx
            if years_diff > 0 and first_val > 0:
                total_growth = ((last_val - first_val) / first_val) * 100
                cagr = ((last_val / first_val) ** (1 / years_diff) - 1) * 100
                return {
                    "start_value": first_val,
                    "end_value": last_val,
                    "total_growth_pct": round(total_growth, 2),
                    "cagr_pct": round(cagr, 2),
                    "years": years_diff
                }
        return None
    
    trends["growth_rates"] = {
        "enrollment": calc_growth(enrollment),
        "per_pupil_spending": calc_growth(per_pupil),
        "total_expenditures": calc_growth(total_exp),
        "admin_positions": calc_growth(admin_pos),
        "teaching_positions": calc_growth(teachers),
        "avg_teacher_salary": calc_growth(avg_teacher_salary),
    }
    
    return trends


def identify_red_flags(admin_ratios, trends, county_budget):
    """Identify metrics that exceed warning thresholds."""
    red_flags = []
    
    fc = admin_ratios.get(TARGET_DIVISION, {})
    
    # Check admin ratio
    if fc.get("admin_pct_of_total_staff", 0) > THRESHOLDS["admin_ratio_pct"]:
        red_flags.append({
            "flag": "High Admin Ratio",
            "metric": "admin_pct_of_total_staff",
            "value": fc["admin_pct_of_total_staff"],
            "threshold": THRESHOLDS["admin_ratio_pct"],
            "severity": "WARNING",
            "description": f"Admin staff ({fc['admin_pct_of_total_staff']}%) exceeds {THRESHOLDS['admin_ratio_pct']}% threshold"
        })
    
    # Check admin per 1000 students
    if fc.get("admin_per_1000_students", 0) > THRESHOLDS["admin_per_1000_students"]:
        red_flags.append({
            "flag": "High Admin Per Student",
            "metric": "admin_per_1000_students",
            "value": fc["admin_per_1000_students"],
            "threshold": THRESHOLDS["admin_per_1000_students"],
            "severity": "WARNING",
            "description": f"Admin positions per 1000 students ({fc['admin_per_1000_students']}) exceeds {THRESHOLDS['admin_per_1000_students']} threshold"
        })
    
    # Check admin to teacher ratio
    if fc.get("admin_to_teacher_ratio", 0) > THRESHOLDS["admin_to_teacher_ratio"]:
        red_flags.append({
            "flag": "High Admin-to-Teacher Ratio",
            "metric": "admin_to_teacher_ratio",
            "value": fc["admin_to_teacher_ratio"],
            "threshold": THRESHOLDS["admin_to_teacher_ratio"],
            "severity": "WARNING",
            "description": f"Admin-to-teacher ratio ({fc['admin_to_teacher_ratio']:.4f}) exceeds {THRESHOLDS['admin_to_teacher_ratio']} threshold"
        })
    
    # Check admin growth vs enrollment growth
    if trends and trends.get("growth_rates"):
        admin_growth = trends["growth_rates"].get("admin_positions", {})
        enroll_growth = trends["growth_rates"].get("enrollment", {})
        
        if admin_growth and enroll_growth:
            admin_total = admin_growth.get("total_growth_pct", 0)
            enroll_total = enroll_growth.get("total_growth_pct", 0)
            
            if enroll_total != 0:
                ratio = admin_total / enroll_total if enroll_total != 0 else float('inf')
                if ratio > THRESHOLDS["admin_growth_vs_enrollment"]:
                    red_flags.append({
                        "flag": "Admin Growing Faster Than Enrollment",
                        "metric": "admin_growth_vs_enrollment",
                        "value": round(ratio, 2),
                        "threshold": THRESHOLDS["admin_growth_vs_enrollment"],
                        "severity": "CRITICAL",
                        "description": f"Admin growth ({admin_total}%) is {ratio:.1f}x enrollment growth ({enroll_total}%)"
                    })
    
    # Check county budget school share decline
    if county_budget:
        budget_data = county_budget.get("data", [])
        if len(budget_data) >= 2:
            first = budget_data[0]
            last = budget_data[-1]
            first_pct = first["school_funds"]["pct_of_total_budget"]
            last_pct = last["school_funds"]["pct_of_total_budget"]
            
            if last_pct < first_pct:
                red_flags.append({
                    "flag": "Declining School Share of County Budget",
                    "metric": "school_pct_of_budget",
                    "value": last_pct,
                    "threshold": first_pct,
                    "severity": "INFO",
                    "description": f"School share declined from {first_pct}% ({first['fiscal_year']}) to {last_pct}% ({last['fiscal_year']})"
                })
    
    # Add positive findings (no red flags)
    if not any(f["metric"] == "admin_pct_of_total_staff" for f in red_flags):
        red_flags.append({
            "flag": "Admin Ratio Within Threshold",
            "metric": "admin_pct_of_total_staff",
            "value": fc.get("admin_pct_of_total_staff", 0),
            "threshold": THRESHOLDS["admin_ratio_pct"],
            "severity": "OK",
            "description": f"Admin staff ratio ({fc.get('admin_pct_of_total_staff', 0)}%) is within acceptable range"
        })
    
    return red_flags


def generate_peer_comparison(admin_ratios, expenditures, fiscal_year):
    """Generate a peer comparison table."""
    comparison = {
        "fiscal_year": fiscal_year,
        "divisions": [],
        "rankings": {}
    }
    
    for code in ["069", "043", "061", "171", "187", "107"]:
        if code not in admin_ratios or code not in expenditures:
            continue
            
        admin = admin_ratios[code]
        exp = expenditures[code]
        
        comparison["divisions"].append({
            "division_code": code,
            "division_name": admin["division_name"],
            "enrollment_adm": admin["enrollment_adm"],
            "per_pupil_spending": exp["total_per_pupil"],
            "admin_positions": admin["admin_positions"],
            "teaching_positions": admin["teaching_positions"],
            "admin_pct_of_staff": admin["admin_pct_of_total_staff"],
            "admin_per_1000_students": admin["admin_per_1000_students"],
            "students_per_admin": admin["students_per_admin"],
        })
    
    # Calculate rankings (1 = best for most metrics)
    divisions = comparison["divisions"]
    
    # Per-pupil spending (lower can be good if outcomes are similar)
    sorted_by_spending = sorted(divisions, key=lambda x: x["per_pupil_spending"])
    comparison["rankings"]["per_pupil_spending_rank"] = {
        d["division_code"]: i+1 for i, d in enumerate(sorted_by_spending)
    }
    
    # Admin per 1000 (lower is better)
    sorted_by_admin = sorted(divisions, key=lambda x: x["admin_per_1000_students"])
    comparison["rankings"]["admin_efficiency_rank"] = {
        d["division_code"]: i+1 for i, d in enumerate(sorted_by_admin)
    }
    
    # Students per admin (higher is more efficient)
    sorted_by_students = sorted(divisions, key=lambda x: -x["students_per_admin"])
    comparison["rankings"]["students_per_admin_rank"] = {
        d["division_code"]: i+1 for i, d in enumerate(sorted_by_students)
    }
    
    return comparison


def main():
    """Main analysis function."""
    print("FCPS Audit Metrics Calculator")
    print("=" * 50)
    
    # Load all data
    print("\nLoading processed data...")
    table8 = load_json("table8_enrollment.json")
    table15 = load_json("table15_expenditures.json")
    table18 = load_json("table18_admin_personnel.json")
    table19 = load_json("table19_instructional.json")
    
    county_budget_path = PROCESSED_DIR / "county_budget_schools.json"
    county_budget = json.load(open(county_budget_path)) if county_budget_path.exists() else None
    
    # Use most recent complete year (FY2024 / 2023-24)
    current_fy = "FY2024"
    current_year = "2023-24"
    
    # Calculate admin ratios
    print(f"\nCalculating admin ratios for {current_fy}...")
    admin_ratios = calculate_admin_ratios(table18, table19, table8, current_fy)
    
    # Calculate expenditure analysis
    print(f"Calculating expenditure analysis for {current_year}...")
    expenditures = calculate_expenditure_analysis(table15, current_year)
    
    # Calculate trend analysis
    print("Calculating 5-year trends for Frederick County...")
    trends = calculate_trend_analysis(table8, table15, table18, table19)
    
    # Generate peer comparison
    print("Generating peer comparison...")
    peer_comparison = generate_peer_comparison(admin_ratios, expenditures, current_fy)
    
    # Identify red flags
    print("Identifying red flags...")
    red_flags = identify_red_flags(admin_ratios, trends, county_budget)
    
    # Compile full audit report
    audit_report = {
        "report_title": "Frederick County Public Schools Administrative Audit",
        "target_division": {
            "code": "069",
            "name": "Frederick County",
        },
        "peer_divisions": ["043", "061", "171", "187", "107"],
        "analysis_date": datetime.now().isoformat(),
        "fiscal_year_analyzed": current_fy,
        "data_sources": [
            "VDOE Superintendent's Annual Report Tables 8, 15, 17, 18, 19",
            "Frederick County Annual Budgets FY2020-FY2025",
        ],
        "thresholds_used": THRESHOLDS,
        "sections": {
            "admin_ratios": admin_ratios,
            "expenditure_analysis": expenditures,
            "trend_analysis": trends,
            "peer_comparison": peer_comparison,
            "red_flags": red_flags,
        }
    }
    
    # Save results
    ANALYSIS_DIR.mkdir(exist_ok=True)
    
    output_path = ANALYSIS_DIR / "fcps_audit_report.json"
    with open(output_path, "w") as f:
        json.dump(audit_report, f, indent=2)
    print(f"\nFull audit report saved to: {output_path}")
    
    # Print summary
    print("\n" + "=" * 50)
    print("AUDIT SUMMARY - Frederick County Public Schools")
    print("=" * 50)
    
    fc = admin_ratios.get(TARGET_DIVISION, {})
    fc_exp = expenditures.get(TARGET_DIVISION, {})
    state_exp = expenditures.get("STATE", {})
    
    print(f"\nFiscal Year: {current_fy}")
    enrollment = fc.get('enrollment_adm', 'N/A')
    if isinstance(enrollment, (int, float)):
        print(f"Enrollment (ADM): {enrollment:,.0f}")
    else:
        print(f"Enrollment (ADM): {enrollment}")
    
    print(f"\n--- Staffing ---")
    print(f"Admin Positions: {fc.get('admin_positions', 'N/A'):.1f}")
    print(f"Teaching Positions: {fc.get('teaching_positions', 'N/A'):,.1f}")
    print(f"Total Staff: {fc.get('total_staff', 'N/A'):,.1f}")
    print(f"Admin % of Staff: {fc.get('admin_pct_of_total_staff', 'N/A')}%")
    print(f"Admin per 1000 Students: {fc.get('admin_per_1000_students', 'N/A')}")
    print(f"Students per Admin: {fc.get('students_per_admin', 'N/A')}")
    
    print(f"\n--- Expenditures ---")
    print(f"Total Per-Pupil: ${fc_exp.get('total_per_pupil', 0):,}")
    print(f"State Average: ${state_exp.get('total_per_pupil', 0):,}")
    if fc_exp.get('total_per_pupil') and state_exp.get('total_per_pupil'):
        diff_pct = ((fc_exp['total_per_pupil'] - state_exp['total_per_pupil']) / state_exp['total_per_pupil']) * 100
        print(f"vs State: {diff_pct:+.1f}%")
    
    print(f"\n--- 5-Year Trends (FY2020-FY2024) ---")
    if trends.get("growth_rates"):
        gr = trends["growth_rates"]
        if gr.get("enrollment"):
            print(f"Enrollment Growth: {gr['enrollment']['total_growth_pct']:+.1f}%")
        if gr.get("per_pupil_spending"):
            print(f"Per-Pupil Spending Growth: {gr['per_pupil_spending']['total_growth_pct']:+.1f}%")
        if gr.get("admin_positions"):
            print(f"Admin Position Growth: {gr['admin_positions']['total_growth_pct']:+.1f}%")
        if gr.get("teaching_positions"):
            print(f"Teaching Position Growth: {gr['teaching_positions']['total_growth_pct']:+.1f}%")
    
    print(f"\n--- Red Flags ---")
    critical = [f for f in red_flags if f["severity"] == "CRITICAL"]
    warnings = [f for f in red_flags if f["severity"] == "WARNING"]
    ok = [f for f in red_flags if f["severity"] == "OK"]
    
    print(f"CRITICAL: {len(critical)}")
    for f in critical:
        print(f"  - {f['description']}")
    print(f"WARNING: {len(warnings)}")
    for f in warnings:
        print(f"  - {f['description']}")
    print(f"OK: {len(ok)}")
    
    print(f"\n--- Peer Comparison Ranking (out of 6 divisions) ---")
    if peer_comparison.get("rankings"):
        rankings = peer_comparison["rankings"]
        print(f"Per-Pupil Spending: #{rankings.get('per_pupil_spending_rank', {}).get('069', 'N/A')}")
        print(f"Admin Efficiency: #{rankings.get('admin_efficiency_rank', {}).get('069', 'N/A')}")
        print(f"Students per Admin: #{rankings.get('students_per_admin_rank', {}).get('069', 'N/A')}")
    
    return audit_report


if __name__ == "__main__":
    main()
