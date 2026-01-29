#!/usr/bin/env python3
"""
Generate interactive Plotly dashboards from calculated metrics.

Usage:
    python scripts/generate_dashboards.py --output data/analysis/dashboards/
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
ANALYSIS_DIR = DATA_DIR / "analysis"
DASHBOARDS_DIR = ANALYSIS_DIR / "dashboards"

# Color palette for divisions
COLORS = {
    "Frederick County": "#1f77b4",  # Blue - primary focus
    "Clarke County": "#ff7f0e",
    "Fauquier County": "#2ca02c",
    "Shenandoah County": "#d62728",
    "Warren County": "#9467bd",
    "Loudoun County": "#8c564b",
    "State Average": "#7f7f7f",
    "Peer Average": "#bcbd22",
}


def load_metrics() -> dict:
    """Load calculated metrics from JSON."""
    ratios_file = PROCESSED_DIR / "ratios.json"
    
    if not ratios_file.exists():
        print(f"Error: Metrics file not found: {ratios_file}")
        print("Run calculate_metrics.py first.")
        sys.exit(1)
    
    with open(ratios_file) as f:
        return json.load(f)


def create_per_pupil_comparison(metrics: dict, output_dir: Path):
    """Create per-pupil spending comparison bar chart."""
    comparison = metrics.get("comparison_matrix", {})
    divisions = comparison.get("comparisons", [])
    
    if not divisions:
        print("  Skipping per-pupil comparison (no data)")
        return
    
    # Prepare data
    names = [d["division_name"] for d in divisions]
    total = [d.get("per_pupil_total", 0) for d in divisions]
    instruction = [d.get("per_pupil_instruction", 0) for d in divisions]
    admin = [d.get("per_pupil_admin", 0) for d in divisions]
    
    # Create figure
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name="Total Per Pupil",
        x=names,
        y=total,
        marker_color=[COLORS.get(n, "#999999") for n in names],
        text=[f"${v:,.0f}" for v in total],
        textposition="outside",
    ))
    
    fig.update_layout(
        title={
            "text": "Per-Pupil Spending Comparison",
            "font": {"size": 20},
        },
        xaxis_title="School Division",
        yaxis_title="Dollars Per Student",
        yaxis_tickprefix="$",
        yaxis_tickformat=",",
        showlegend=False,
        height=500,
        template="plotly_white",
    )
    
    # Add peer average line
    if comparison.get("peer_average", {}).get("per_pupil_total"):
        avg = comparison["peer_average"]["per_pupil_total"]
        fig.add_hline(
            y=avg,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Peer Avg: ${avg:,.0f}",
            annotation_position="right",
        )
    
    output_file = output_dir / "per_pupil_comparison.html"
    fig.write_html(str(output_file))
    print(f"  Created: {output_file.name}")


def create_admin_ratio_comparison(metrics: dict, output_dir: Path):
    """Create administrative spending ratio comparison."""
    comparison = metrics.get("comparison_matrix", {})
    divisions = comparison.get("comparisons", [])
    benchmarks = metrics.get("benchmarks", {})
    
    if not divisions:
        print("  Skipping admin ratio comparison (no data)")
        return
    
    # Prepare data
    names = [d["division_name"] for d in divisions]
    admin_ratios = [d.get("admin_ratio", 0) for d in divisions]
    
    # Create figure
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name="Admin Spending %",
        x=names,
        y=admin_ratios,
        marker_color=[COLORS.get(n, "#999999") for n in names],
        text=[f"{v:.1f}%" for v in admin_ratios],
        textposition="outside",
    ))
    
    # Add benchmark lines
    target = benchmarks.get("admin_ratio_target", 5)
    warning = benchmarks.get("admin_ratio_warning", 10)
    
    fig.add_hline(
        y=target,
        line_dash="dash",
        line_color="green",
        annotation_text=f"Target: {target}%",
        annotation_position="right",
    )
    
    fig.add_hline(
        y=warning,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Warning: {warning}%",
        annotation_position="right",
    )
    
    fig.update_layout(
        title={
            "text": "Administrative Spending as % of Total Budget",
            "font": {"size": 20},
        },
        xaxis_title="School Division",
        yaxis_title="Admin Spending (%)",
        yaxis_ticksuffix="%",
        showlegend=False,
        height=500,
        template="plotly_white",
    )
    
    output_file = output_dir / "admin_ratio_comparison.html"
    fig.write_html(str(output_file))
    print(f"  Created: {output_file.name}")


def create_instruction_vs_admin(metrics: dict, output_dir: Path):
    """Create instruction vs admin spending comparison."""
    comparison = metrics.get("comparison_matrix", {})
    divisions = comparison.get("comparisons", [])
    
    if not divisions:
        print("  Skipping instruction vs admin chart (no data)")
        return
    
    # Prepare data
    names = [d["division_name"] for d in divisions]
    instruction = [d.get("instruction_ratio", 0) for d in divisions]
    admin = [d.get("admin_ratio", 0) for d in divisions]
    
    # Create grouped bar chart
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name="Instruction %",
        x=names,
        y=instruction,
        marker_color="#2ca02c",
        text=[f"{v:.1f}%" for v in instruction],
        textposition="outside",
    ))
    
    fig.add_trace(go.Bar(
        name="Administration %",
        x=names,
        y=admin,
        marker_color="#d62728",
        text=[f"{v:.1f}%" for v in admin],
        textposition="outside",
    ))
    
    fig.update_layout(
        title={
            "text": "Instruction vs Administrative Spending",
            "font": {"size": 20},
        },
        xaxis_title="School Division",
        yaxis_title="Percentage of Budget",
        yaxis_ticksuffix="%",
        barmode="group",
        height=500,
        template="plotly_white",
        legend={"orientation": "h", "y": -0.15},
    )
    
    output_file = output_dir / "instruction_vs_admin.html"
    fig.write_html(str(output_file))
    print(f"  Created: {output_file.name}")


def create_trend_chart(metrics: dict, output_dir: Path):
    """Create multi-year trend chart for Frederick County."""
    # Find Frederick County data
    frederick_data = None
    for div in metrics.get("divisions", []):
        if div["division_code"] == "069":
            frederick_data = div
            break
    
    if not frederick_data or not frederick_data.get("trends"):
        print("  Skipping trend chart (no multi-year data)")
        return
    
    trends = frederick_data["trends"]
    years = trends.get("years", [])
    
    if len(years) < 2:
        print("  Skipping trend chart (insufficient years)")
        return
    
    # Create subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "Enrollment Trend",
            "Per-Pupil Spending",
            "Admin Spending Ratio",
            "Instruction Spending Ratio"
        ),
        vertical_spacing=0.15,
        horizontal_spacing=0.1,
    )
    
    # Enrollment trend
    enrollment = trends.get("enrollment_trend", [])
    if enrollment:
        fig.add_trace(
            go.Scatter(
                x=years, y=enrollment,
                mode="lines+markers",
                name="Enrollment",
                line={"color": COLORS["Frederick County"]},
            ),
            row=1, col=1
        )
    
    # Per-pupil trend
    per_pupil = trends.get("per_pupil_trend", [])
    if per_pupil:
        fig.add_trace(
            go.Scatter(
                x=years, y=per_pupil,
                mode="lines+markers",
                name="Per Pupil",
                line={"color": COLORS["Frederick County"]},
            ),
            row=1, col=2
        )
    
    # Admin ratio trend
    admin_ratio = trends.get("admin_ratio_trend", [])
    if admin_ratio:
        fig.add_trace(
            go.Scatter(
                x=years, y=admin_ratio,
                mode="lines+markers",
                name="Admin %",
                line={"color": "#d62728"},
            ),
            row=2, col=1
        )
    
    # Instruction ratio trend
    instruction_ratio = trends.get("instruction_ratio_trend", [])
    if instruction_ratio:
        fig.add_trace(
            go.Scatter(
                x=years, y=instruction_ratio,
                mode="lines+markers",
                name="Instruction %",
                line={"color": "#2ca02c"},
            ),
            row=2, col=2
        )
    
    fig.update_layout(
        title={
            "text": "Frederick County Public Schools - 5-Year Trends",
            "font": {"size": 20},
        },
        height=700,
        showlegend=False,
        template="plotly_white",
    )
    
    # Update y-axes
    fig.update_yaxes(title_text="Students", row=1, col=1)
    fig.update_yaxes(title_text="Dollars", tickprefix="$", row=1, col=2)
    fig.update_yaxes(title_text="Percent", ticksuffix="%", row=2, col=1)
    fig.update_yaxes(title_text="Percent", ticksuffix="%", row=2, col=2)
    
    output_file = output_dir / "frederick_trends.html"
    fig.write_html(str(output_file))
    print(f"  Created: {output_file.name}")


def create_staff_ratio_comparison(metrics: dict, output_dir: Path):
    """Create admin-to-student ratio comparison."""
    comparison = metrics.get("comparison_matrix", {})
    divisions = comparison.get("comparisons", [])
    benchmarks = metrics.get("benchmarks", {})
    
    if not divisions:
        print("  Skipping staff ratio comparison (no data)")
        return
    
    # Filter to divisions with data
    names = []
    ratios = []
    for d in divisions:
        ratio = d.get("admin_to_student", 0)
        if ratio > 0:
            names.append(d["division_name"])
            ratios.append(ratio)
    
    if not ratios:
        print("  Skipping staff ratio comparison (no ratio data)")
        return
    
    # Create figure
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name="Students per Admin",
        x=names,
        y=ratios,
        marker_color=[COLORS.get(n, "#999999") for n in names],
        text=[f"1:{v:.0f}" for v in ratios],
        textposition="outside",
    ))
    
    # Add benchmark lines
    target = benchmarks.get("admin_to_student_target", 250)
    warning = benchmarks.get("admin_to_student_warning", 150)
    
    fig.add_hline(
        y=target,
        line_dash="dash",
        line_color="green",
        annotation_text=f"Target: 1:{target}",
        annotation_position="right",
    )
    
    fig.add_hline(
        y=warning,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Warning: 1:{warning}",
        annotation_position="right",
    )
    
    fig.update_layout(
        title={
            "text": "Admin-to-Student Ratio (Higher = More Efficient)",
            "font": {"size": 20},
        },
        xaxis_title="School Division",
        yaxis_title="Students per Administrator",
        showlegend=False,
        height=500,
        template="plotly_white",
    )
    
    output_file = output_dir / "admin_student_ratio.html"
    fig.write_html(str(output_file))
    print(f"  Created: {output_file.name}")


def create_red_flags_summary(metrics: dict, output_dir: Path):
    """Create summary of red flags across all divisions."""
    all_flags = []
    
    for div in metrics.get("divisions", []):
        div_name = div["division_name"]
        for year_metrics in div.get("metrics_by_year", []):
            for flag in year_metrics.get("red_flags", []):
                all_flags.append({
                    "division": div_name,
                    "fiscal_year": year_metrics.get("fiscal_year", "Unknown"),
                    "indicator": flag["indicator"],
                    "value": flag["value"],
                    "severity": flag["severity"],
                    "message": flag["message"],
                })
    
    if not all_flags:
        print("  No red flags to display")
        return
    
    # Create table
    fig = go.Figure(data=[go.Table(
        header={
            "values": ["Division", "Year", "Indicator", "Value", "Severity", "Details"],
            "fill_color": "#1f77b4",
            "font": {"color": "white", "size": 12},
            "align": "left",
        },
        cells={
            "values": [
                [f["division"] for f in all_flags],
                [f["fiscal_year"] for f in all_flags],
                [f["indicator"] for f in all_flags],
                [f"{f['value']:.2f}" for f in all_flags],
                [f["severity"].upper() for f in all_flags],
                [f["message"] for f in all_flags],
            ],
            "fill_color": [
                ["#ffcccc" if f["severity"] == "high" else "#fff3cd" for f in all_flags]
            ] * 6,
            "align": "left",
        }
    )])
    
    fig.update_layout(
        title={
            "text": "Audit Red Flags Summary",
            "font": {"size": 20},
        },
        height=400 + len(all_flags) * 30,
    )
    
    output_file = output_dir / "red_flags_summary.html"
    fig.write_html(str(output_file))
    print(f"  Created: {output_file.name}")


def create_dashboard_index(output_dir: Path):
    """Create an index HTML page linking to all dashboards."""
    html_files = list(output_dir.glob("*.html"))
    html_files = [f for f in html_files if f.name != "index.html"]
    
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>FCPS Audit Dashboards</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 {
            color: #333;
            border-bottom: 2px solid #1f77b4;
            padding-bottom: 10px;
        }
        .dashboard-list {
            list-style: none;
            padding: 0;
        }
        .dashboard-list li {
            margin: 10px 0;
            padding: 15px;
            background: white;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .dashboard-list a {
            color: #1f77b4;
            text-decoration: none;
            font-size: 18px;
        }
        .dashboard-list a:hover {
            text-decoration: underline;
        }
        .meta {
            color: #666;
            font-size: 14px;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <h1>Frederick County Public Schools Audit Dashboards</h1>
    <p>Interactive visualizations comparing FCPS spending metrics with peer districts.</p>
    <ul class="dashboard-list">
"""
    
    dashboard_names = {
        "per_pupil_comparison.html": "Per-Pupil Spending Comparison",
        "admin_ratio_comparison.html": "Administrative Spending Ratios",
        "instruction_vs_admin.html": "Instruction vs Administration Spending",
        "frederick_trends.html": "Frederick County 5-Year Trends",
        "admin_student_ratio.html": "Admin-to-Student Ratios",
        "red_flags_summary.html": "Audit Red Flags Summary",
    }
    
    for f in sorted(html_files, key=lambda x: x.name):
        name = dashboard_names.get(f.name, f.stem.replace("_", " ").title())
        html_content += f'        <li><a href="{f.name}">{name}</a></li>\n'
    
    html_content += f"""
    </ul>
    <p class="meta">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
</body>
</html>
"""
    
    index_file = output_dir / "index.html"
    with open(index_file, "w") as f:
        f.write(html_content)
    print(f"  Created: {index_file.name}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate interactive Plotly dashboards",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--output",
        type=Path,
        default=DASHBOARDS_DIR,
        help="Output directory for dashboard HTML files"
    )
    
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    
    print("FCPS Dashboard Generator")
    print("=" * 50)
    print(f"Output directory: {args.output}")
    
    # Load metrics
    print("\nLoading calculated metrics...")
    metrics = load_metrics()
    
    # Generate dashboards
    print("\nGenerating dashboards...")
    
    create_per_pupil_comparison(metrics, args.output)
    create_admin_ratio_comparison(metrics, args.output)
    create_instruction_vs_admin(metrics, args.output)
    create_trend_chart(metrics, args.output)
    create_staff_ratio_comparison(metrics, args.output)
    create_red_flags_summary(metrics, args.output)
    create_dashboard_index(args.output)
    
    print("\n" + "=" * 50)
    print("Dashboard generation complete!")
    print(f"\nOpen {args.output / 'index.html'} in a browser to view dashboards.")


if __name__ == "__main__":
    main()
