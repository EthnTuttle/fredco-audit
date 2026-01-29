# CLAUDE.md - AI Agent Instructions for FCPS Audit

## Project Overview

This project audits Frederick County Public Schools (FCPS) in Virginia for over-administration, spending trends, and fiscal efficiency. The goal is to mirror public data locally, parse it into structured JSON format, and enable LLM-based inquiry.

**Target District**: Frederick County Public Schools (Division Code: 069)
**Peer Districts**: Clarke (043), Fauquier (061), Shenandoah (171), Warren (187), Loudoun (107)
**Scope**: FY2020-FY2025 (5 fiscal years)

---

## Directory Structure

```
fredco-schools/
├── ROADMAP.md              # Project roadmap and methodology
├── CLAUDE.md               # This file - AI agent instructions
├── requirements.txt        # Python dependencies
├── data/
│   ├── raw/                # Original downloaded files
│   │   ├── fcps/           # FCPS budget documents
│   │   ├── vdoe/           # VDOE tables
│   │   ├── apa/            # Auditor reports
│   │   └── vpap/           # VPAP data
│   ├── processed/          # Normalized JSON/CSV
│   └── analysis/           # Results and dashboards
├── scripts/                # Processing scripts
└── schemas/                # JSON schema definitions
```

---

## Data Sources & Collection

### 1. FCPS Budget Documents

**Source**: https://www.frederickcountyschoolsva.net/about/budget

**Files to Download**:
- Annual Approved Budget (FY2020-FY2026)
- Annual Comprehensive Financial Report (ACFR) for each year
- Monthly/Year-End Financial Reports

**Download Command**:
```bash
python scripts/download_data.py --source fcps
```

**Storage**: `data/raw/fcps/budgets/` and `data/raw/fcps/acfr/`

**Key Data Points**:
- Total operating expenditures
- Expenditures by function (instruction, administration, operations, transportation)
- Revenue sources (state, local, federal)
- Staffing counts by category

---

### 2. VDOE Superintendent's Annual Report

**Source**: https://www.doe.virginia.gov/data-policy-funding/data-reports/statistics-reports/superintendent-s-annual-report

**Tables to Download**:

| Table | Content | Format |
|-------|---------|--------|
| Table 3 | Enrollment (ADM) by division | XLSM |
| Table 13 | Instructional staff counts and salaries | XLSM |
| Table 15 | Per pupil expenditures by source | XLSM |

**Years**: 2019-20, 2020-21, 2021-22, 2022-23, 2023-24

**Download Command**:
```bash
python scripts/download_data.py --source vdoe
```

**Storage**: `data/raw/vdoe/table-{3,13,15}/`

**Division Codes for Filtering**:
- Frederick County: 069
- Clarke County: 043
- Fauquier County: 061
- Shenandoah County: 171
- Warren County: 187
- Loudoun County: 107

---

### 3. Virginia APA Comparative Report

**Source**: https://www.apa.virginia.gov

**Direct URL**: https://dlasprodpublic.blob.core.windows.net/apa/549A9D64-9A00-45D1-A88F-5FE9C1BFAD8E.xlsx

**Target**: Exhibit C-6 (Education expenditures by category)

**Download Command**:
```bash
python scripts/download_data.py --source apa
```

**Storage**: `data/raw/apa/comparative/`

---

### 4. VPAP Instructional Spending

**Source**: https://www.vpap.org/visuals/visual/back-to-school-spending-on-teaching-fy2024

**Purpose**: Supplementary benchmark data and visualizations

**Storage**: `data/raw/vpap/visuals/`

---

## Data Processing Pipeline

### Step 1: Download Raw Data

```bash
# Download all sources
python scripts/download_data.py --all

# Or download specific source
python scripts/download_data.py --source fcps
python scripts/download_data.py --source vdoe
python scripts/download_data.py --source apa
```

### Step 2: Parse PDF Documents

```bash
# Extract tables from FCPS budget PDFs
python scripts/parse_pdf.py --input data/raw/fcps/budgets/ --output data/processed/

# Extract from ACFR documents
python scripts/parse_pdf.py --input data/raw/fcps/acfr/ --output data/processed/
```

### Step 3: Parse Excel Files

```bash
# Process VDOE tables
python scripts/parse_excel.py --source vdoe --output data/processed/

# Process APA comparative report
python scripts/parse_excel.py --source apa --output data/processed/
```

### Step 4: Calculate Metrics

```bash
# Generate all ratios and per-pupil metrics
python scripts/calculate_metrics.py --output data/processed/ratios.json
```

### Step 5: Generate Dashboards

```bash
# Create Plotly interactive visualizations
python scripts/generate_dashboards.py --output data/analysis/dashboards/
```

---

## JSON Schema Definitions

### Enrollment Schema (`schemas/enrollment.json`)

```json
{
  "fiscal_year": "FY2024",
  "division_code": "069",
  "division_name": "Frederick County",
  "enrollment": {
    "adm": 14000,
    "adm_elementary": 6000,
    "adm_middle": 3500,
    "adm_high": 4500
  },
  "source": "VDOE Table 3",
  "source_url": "https://...",
  "downloaded_date": "2025-01-28"
}
```

### Expenditures Schema (`schemas/expenditures.json`)

```json
{
  "fiscal_year": "FY2024",
  "division_code": "069",
  "division_name": "Frederick County",
  "expenditures": {
    "total": 260000000,
    "instruction": 180000000,
    "administration": 15000000,
    "attendance_health": 5000000,
    "pupil_transportation": 20000000,
    "operations_maintenance": 25000000,
    "facilities": 5000000,
    "debt_service": 10000000,
    "technology": 8000000
  },
  "revenues": {
    "total": 260000000,
    "state": 122000000,
    "local": 122000000,
    "federal": 16000000
  },
  "source": "FCPS ACFR",
  "source_url": "https://...",
  "downloaded_date": "2025-01-28"
}
```

### Staffing Schema (`schemas/staffing.json`)

```json
{
  "fiscal_year": "FY2024",
  "division_code": "069",
  "division_name": "Frederick County",
  "staffing": {
    "teachers": 950,
    "administrators": 45,
    "instructional_aides": 200,
    "guidance_counselors": 35,
    "librarians": 15,
    "support_staff": 400,
    "total_fte": 1645
  },
  "salaries": {
    "avg_teacher_salary": 55000,
    "avg_admin_salary": 95000
  },
  "source": "VDOE Table 13",
  "source_url": "https://...",
  "downloaded_date": "2025-01-28"
}
```

### Ratios Schema (`schemas/ratios.json`)

```json
{
  "fiscal_year": "FY2024",
  "division_code": "069",
  "division_name": "Frederick County",
  "per_pupil": {
    "total": 18571,
    "instruction": 12857,
    "administration": 1071,
    "transportation": 1429,
    "operations": 1786
  },
  "ratios": {
    "admin_pct": 5.77,
    "instruction_pct": 69.23,
    "admin_to_student": 311,
    "admin_to_teacher": 21.1,
    "teacher_to_student": 14.7
  },
  "benchmarks": {
    "state_avg_admin_pct": 5.2,
    "state_avg_instruction_pct": 68.0,
    "peer_avg_admin_pct": 5.5
  },
  "flags": {
    "admin_above_state_avg": true,
    "instruction_below_target": false
  }
}
```

---

## Key Calculations

### Per-Pupil Metrics

```python
# Total per pupil
per_pupil_total = total_expenditures / adm

# By category
per_pupil_instruction = instruction_exp / adm
per_pupil_admin = admin_exp / adm
per_pupil_ops = operations_exp / adm
per_pupil_transport = transportation_exp / adm
```

### Efficiency Ratios

```python
# Spending ratios
admin_ratio = admin_exp / total_exp * 100
instruction_ratio = instruction_exp / total_exp * 100

# Staff ratios
admin_to_student = adm / admin_staff_count
admin_to_teacher = teacher_count / admin_staff_count
teacher_to_student = adm / teacher_count
```

### Trend Calculations

```python
# Year-over-year change
yoy_change = (current_year - prior_year) / prior_year * 100

# Compound annual growth rate (CAGR)
cagr = ((end_value / start_value) ** (1 / years)) - 1

# Enrollment-adjusted growth
adjusted_growth = budget_growth - enrollment_growth
```

---

## Validation Rules

1. **Cross-Reference**: Compare FCPS-reported numbers with VDOE tables
2. **Threshold**: Flag discrepancies >5% for investigation
3. **Completeness**: Ensure all 5 years have data for each metric
4. **Consistency**: Verify category definitions match across sources
5. **Footnotes**: Document any adjustments or restatements

---

## Red Flags to Identify

| Indicator | Threshold | Action |
|-----------|-----------|--------|
| Admin ratio | >10% | Flag for review |
| Admin growth > enrollment | >2x enrollment growth | Flag for review |
| Instruction ratio | <60% | Flag for review |
| Admin:student ratio | <1:150 | Flag for review |
| Per-pupil admin | >$1,200 | Compare to peers |

---

## LLM Query Examples

When the data is processed, use these natural language queries:

1. "What is Frederick County's administrative spending per student compared to the state average?"

2. "How has the admin-to-student ratio changed from FY2020 to FY2024?"

3. "Which peer district has the lowest administrative overhead?"

4. "Is Frederick County's instruction ratio above or below 65%?"

5. "Show the 5-year trend of total per-pupil spending for all comparison districts."

6. "What percentage of Frederick County's budget goes to central administration vs. school-level administration?"

7. "How does Frederick County's budget growth compare to its enrollment growth over 5 years?"

---

## Output Files

After processing, the following files should be generated:

| File | Description |
|------|-------------|
| `data/processed/enrollment.json` | ADM for all districts, all years |
| `data/processed/expenditures.json` | Spending by category, all districts |
| `data/processed/staffing.json` | Staff counts and salaries |
| `data/processed/ratios.json` | Calculated metrics |
| `data/analysis/trends.json` | Year-over-year analysis |
| `data/analysis/benchmarks.json` | Peer comparisons |
| `data/analysis/findings.json` | Audit conclusions |
| `data/analysis/dashboards/*.html` | Plotly visualizations |

---

## Troubleshooting

### PDF Extraction Issues
- Try `pdfplumber` first, fall back to `tabula-py`
- For scanned PDFs, use OCR preprocessing
- Manual entry may be needed for complex tables

### Excel Parsing Issues
- VDOE files are XLSM (macro-enabled) - use `openpyxl`
- Some files have multiple sheets - process each relevant sheet
- Watch for merged cells and hidden rows

### Data Gaps
- If a year is missing, note in findings
- Use FOIA request template for detailed breakdowns
- Check School Quality Profiles for supplementary data

---

## Next Steps After Data Collection

1. Run all download scripts to mirror data locally
2. Parse PDFs and Excel files into JSON
3. Calculate all metrics for 6 districts x 5 years
4. Generate comparison dashboards
5. Identify red flags and anomalies
6. Draft findings report
7. Prepare LLM query interface
