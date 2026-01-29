# Frederick County Public Schools Audit Roadmap

## Objective

Audit Frederick County, VA public school system for over-administration, spending trends, dollars per student, and related ratios to ensure fiscal accountability and comparability with peer districts.

**Scope**: FY2020-FY2025 (5-year trend analysis)

**Peer Districts**: Clarke, Fauquier, Shenandoah, Warren, Loudoun Counties

---

## Phase 1: Data Collection

### 1.1 Primary Data Sources

#### Frederick County Public Schools (FCPS) Official Website
- **URL**: https://www.frederickcountyschoolsva.net/about/budget
- **Target Documents**:
  - Annual Budget Documents (FY2020-FY2026)
  - Monthly/Year-End Financial Reports
  - Annual Comprehensive Financial Report (ACFR) - FY2020-FY2024
- **Data Points**: Line-item revenues, expenditures, staffing allocations
- **Local Path**: `data/raw/fcps/`

#### Virginia Department of Education (VDOE) Superintendent's Annual Report
- **URL**: https://www.doe.virginia.gov/data-policy-funding/data-reports/statistics-reports/superintendent-s-annual-report
- **Target Tables**:
  - **Table 3**: Enrollment (Average Daily Membership/ADM)
  - **Table 13**: Instructional Staff Counts and Salaries
  - **Table 15**: Sources of Financial Support for Expenditures and Per Pupil Expenditures
- **Years**: 2019-2020 through 2023-2024
- **Local Path**: `data/raw/vdoe/`

#### Virginia Auditor of Public Accounts (APA) Comparative Report
- **URL**: https://www.apa.virginia.gov
- **Direct Link**: https://dlasprodpublic.blob.core.windows.net/apa/549A9D64-9A00-45D1-A88F-5FE9C1BFAD8E.xlsx
- **Target**: Exhibit C-6 (Education expenditures by category for all localities)
- **Local Path**: `data/raw/apa/`

#### Virginia Public Access Project (VPAP)
- **URL**: https://www.vpap.org/visuals/visual/back-to-school-spending-on-teaching-fy2024
- **Purpose**: Instructional spending visuals and benchmarks
- **Local Path**: `data/raw/vpap/`

#### School Quality Profiles
- **URL**: https://schoolquality.virginia.gov/divisions/frederick-county-public-schools
- **Purpose**: Division-level financial and staffing summaries

---

## Phase 2: Data Organization

### 2.1 Local Data Mirror Structure

```
data/
├── raw/
│   ├── fcps/
│   │   ├── budgets/           # Annual budget PDFs
│   │   ├── acfr/              # Comprehensive financial reports
│   │   └── monthly-reports/   # Monthly financial statements
│   ├── vdoe/
│   │   ├── table-3/           # Enrollment data (ADM)
│   │   ├── table-13/          # Staff counts/salaries
│   │   └── table-15/          # Per pupil expenditures
│   ├── apa/
│   │   └── comparative/       # Auditor reports
│   └── vpap/
│       └── visuals/           # Spending visualizations
├── processed/
│   ├── enrollment.json        # Normalized enrollment data
│   ├── expenditures.json      # Normalized spending data
│   ├── staffing.json          # Normalized staffing data
│   └── ratios.json            # Calculated metrics
└── analysis/
    ├── trends.json            # Multi-year trend analysis
    ├── benchmarks.json        # Peer comparisons
    ├── findings.json          # Audit conclusions
    └── dashboards/            # Plotly HTML outputs
```

### 2.2 Data Formats
- **Raw**: Original PDFs, XLSX, XLSM files (preserved as-is)
- **Processed**: JSON for LLM consumption, CSV for analysis
- **Metadata**: Source URL, download date, fiscal year covered

---

## Phase 3: Key Metrics Calculation

### 3.1 Per-Student Metrics

| Metric | Formula | Benchmark |
|--------|---------|-----------|
| Total Per Pupil Spending | Total Operating Expenditures / ADM | Compare to state avg (~$15-16K) |
| Instructional Per Pupil | Instructional Expenditures / ADM | Target 60-70% of total |
| Administrative Per Pupil | Admin Expenditures / ADM | Target <$800-1,000 |
| Operations Per Pupil | Operations/Maintenance / ADM | Varies by facilities |
| Transportation Per Pupil | Transportation Costs / ADM | Varies by geography |

### 3.2 Efficiency Ratios

| Ratio | Formula | Target |
|-------|---------|--------|
| Administration Ratio | Admin Expenditures / Total Expenditures | <5-10% |
| Instruction Ratio | Instructional Spending / Total Spending | >60-70% |
| Admin-to-Student | Admin Staff Count / Total Students | 1:200-300 |
| Admin-to-Teacher | Admin Staff Count / Teacher Count | 1:10-15 |
| Teacher-to-Student | Teacher Count / Total Students | 1:15-20 |

### 3.3 Trend Indicators
- Budget growth rate vs. enrollment growth rate
- Administrative spending growth vs. instructional growth
- Per-pupil spending trajectory (inflation-adjusted)
- Staffing composition changes over time

---

## Phase 4: Peer Benchmarking

### 4.1 Comparison Districts

| District | Division Code | Profile |
|----------|---------------|---------|
| Frederick County | 069 | Target district |
| Clarke County | 043 | Small rural neighbor |
| Fauquier County | 061 | Larger regional peer |
| Shenandoah County | 171 | Geographic neighbor, similar size |
| Warren County | 187 | Adjacent jurisdiction |
| Loudoun County | 107 | Larger, wealthier neighbor |

### 4.2 Comparison Framework
- Same metrics applied consistently across all districts
- Normalize for enrollment size differences
- Account for regional cost-of-living variations
- Note any structural differences (e.g., shared services)

---

## Phase 5: Analysis & Reporting

### 5.1 Red Flag Indicators
- Admin spending growth exceeding enrollment/inflation
- Admin ratio above state/peer averages
- Declining instruction ratio over time
- Staff ratio outliers compared to peers
- Budget increases without enrollment growth

### 5.2 Deliverables

1. **Interactive Dashboards** (Plotly)
   - Per-pupil spending trends
   - Admin ratio comparisons
   - Peer benchmarking matrix
   - Year-over-year changes

2. **Trend Analysis Report**
   - 5-year spending trajectory
   - Enrollment correlation
   - Inflation-adjusted figures

3. **Peer Comparison Matrix**
   - Side-by-side metrics for all 6 districts
   - State average benchmarks
   - Quartile rankings

4. **Findings Summary**
   - Key observations and anomalies
   - Potential over-administration indicators
   - Recommendations for further investigation

5. **LLM Query Interface**
   - Structured JSON data
   - Natural language question support
   - Source citations

---

## Implementation Scripts

| Script | Purpose |
|--------|---------|
| `scripts/download_data.py` | Fetch all source files from URLs |
| `scripts/parse_pdf.py` | Extract tables from budget/ACFR PDFs |
| `scripts/parse_excel.py` | Process VDOE/APA spreadsheets |
| `scripts/calculate_metrics.py` | Compute ratios and per-pupil figures |
| `scripts/generate_dashboards.py` | Create Plotly visualizations |

---

## Timeline (One-Time Analysis)

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Data Collection | 3-5 days | Internet access |
| Phase 2: Data Organization | 2-3 days | Phase 1 complete |
| Phase 3: Metrics Calculation | 2-3 days | Phase 2 complete |
| Phase 4: Peer Benchmarking | 2-3 days | Phase 3 complete |
| Phase 5: Analysis & Reporting | 3-5 days | Phase 4 complete |

**Total Estimated Time**: 2-3 weeks

---

## Tools & Technologies

### Python Dependencies
- `pandas` - Data manipulation
- `openpyxl` - Excel file processing
- `pdfplumber` - PDF table extraction
- `tabula-py` - Alternative PDF extraction
- `requests` - HTTP downloads
- `beautifulsoup4` - HTML parsing
- `plotly` - Interactive visualizations

### System Requirements
- Python 3.10+
- Java Runtime (for tabula-py)
- wget/curl (for downloads)

---

## Data Quality Notes

- All data sources are public records
- Focus on audited/official numbers only
- Document all assumptions and limitations
- Cross-reference FCPS numbers with VDOE for validation
- Flag discrepancies >5% for investigation
- FOIA requests may be needed for detailed breakdowns

---

## References

1. FCPS Budget Portal: https://www.frederickcountyschoolsva.net/about/budget
2. VDOE Superintendent's Annual Report: https://www.doe.virginia.gov/data-policy-funding/data-reports/statistics-reports/superintendent-s-annual-report
3. Virginia APA: https://www.apa.virginia.gov
4. VPAP School Spending: https://www.vpap.org/visuals/visual/back-to-school-spending-on-teaching-fy2024
5. School Quality Profiles: https://schoolquality.virginia.gov
