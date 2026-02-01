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

## Phase 6: Data Playground v2

### 6.1 Overview

Interactive browser-based data exploration tool using DuckDB-WASM for SQL queries against Parquet data files. Replaces the original Pyodide/AlaSQL playground with a more performant architecture.

### 6.2 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Data Playground v2                       │
├─────────────────────────────────────────────────────────────┤
│  UI Shell (TypeScript)                                       │
│  ├── Notebook Interface (SQL + Markdown cells)              │
│  ├── Chart Visualizations (Chart.js)                        │
│  └── Nostr Notes Integration                                │
├─────────────────────────────────────────────────────────────┤
│  Engines                                                     │
│  ├── DataEngine (DuckDB-WASM + Parquet)                     │
│  ├── ChartEngine (Bar, Line, Pie, Choropleth maps)          │
│  ├── EditorEngine (Monaco + SQL autocomplete)               │
│  ├── NotesEngine (Nostr NIP-07/NIP-46)                      │
│  └── StorageEngine (IndexedDB caching)                      │
├─────────────────────────────────────────────────────────────┤
│  Rust Types (WASM)                                           │
│  └── Shared type definitions → TypeScript via tsify         │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| SQL Engine | DuckDB-WASM | Fast analytical queries |
| Data Format | Parquet | Compressed columnar storage |
| UI Framework | Vanilla TypeScript | Lightweight, no React |
| Build Tool | Vite | Fast bundling with WASM support |
| Type Safety | Rust + tsify | Rust types → TypeScript |
| Charts | Chart.js | Visualization |
| Editor | Monaco | SQL editing with autocomplete |
| Notes | Nostr | Decentralized public notes |
| Caching | IndexedDB | Offline data persistence |

### 6.4 Data Files

JSON data converted to Parquet format for efficient browser loading:

| File | Size | Description |
|------|------|-------------|
| real_estate_tax.parquet | 22 MB | Property tax records |
| county_department_detail.parquet | 4 MB | County budget line items |
| districts.parquet | 306 KB | District boundaries |
| ownership_analysis.parquet | 112 KB | Property ownership stats |
| county_budget_schools.parquet | 37 KB | County transfers to schools |
| county_government_analysis.parquet | 37 KB | Government spending analysis |
| vdoe_table18_admin.parquet | 30 KB | Admin personnel data |
| vdoe_table19_instructional.parquet | 30 KB | Instructional staff data |
| tax_summary.parquet | 31 KB | Tax summary statistics |
| expenditures.parquet | 16 KB | FCPS expenditure data |
| apa_data.parquet | 14 KB | APA comparative data |
| vdoe_table15_expenditures.parquet | 13 KB | Per-pupil expenditures |
| vdoe_table8_enrollment.parquet | 12 KB | Enrollment (ADM) data |
| apa_education_expenditures.parquet | 10 KB | Education spending by locality |
| vdoe_table17_ratios.parquet | 9 KB | Pupil-teacher ratios |
| enrollment.parquet | 6 KB | Enrollment summary |
| **Total** | **27 MB** | 16 Parquet files |

**Compression:** ~8x smaller than original JSON files

### 6.5 Implementation Status

| Component | Status | Location |
|-----------|--------|----------|
| Rust Types Workspace | **Complete** | `playground/types/` |
| Storage Types | **Complete** | `playground/types/src/storage.rs` |
| TypeScript Project | **Complete** | `playground/src/` |
| Vite Configuration | **Complete** | `playground/vite.config.ts` |
| DuckDB Engine | **Complete** | `playground/src/engines/data.ts` |
| Basic UI Shell | **Complete** | `playground/src/main.ts` |
| Parquet Data Files | **Complete** | `data/parquet/` (16 files, 27 MB) |
| Chart Engine | Pending | - |
| Editor Engine | Pending | - |
| Notes Engine | Pending | - |
| Storage Engine | Pending | - |

**Core Functionality Working:**
- DuckDB-WASM initializes and loads Parquet files
- SQL query execution with results table rendering
- Table list sidebar with click-to-query
- Error handling and loading states

### 6.6 Development Commands

```bash
# From playground/ directory
npm install              # Install dependencies
npm run dev              # Start dev server (port 3001)
npm run build            # Build for production
npm run build:wasm       # Build Rust WASM modules
```

### 6.7 Specifications

Detailed specifications in `specs/`:

- `00-architecture.md` - Overall system design
- `01-ui-shell.md` - UI orchestration layer
- `02-data-engine.md` - DuckDB-WASM integration
- `03-chart-engine.md` - Visualization types
- `04-editor-engine.md` - Monaco editor setup
- `05-notes-engine.md` - Nostr integration
- `06-storage-engine.md` - IndexedDB caching
- `07-integration.md` - Build and deploy pipeline

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

| Phase | Duration | Dependencies | Status |
|-------|----------|--------------|--------|
| Phase 1: Data Collection | 3-5 days | Internet access | **Complete** |
| Phase 2: Data Organization | 2-3 days | Phase 1 complete | **Complete** |
| Phase 3: Metrics Calculation | 2-3 days | Phase 2 complete | **Complete** |
| Phase 4: Peer Benchmarking | 2-3 days | Phase 3 complete | In Progress |
| Phase 5: Analysis & Reporting | 3-5 days | Phase 4 complete | In Progress |
| Phase 6: Data Playground v2 | 1-2 weeks | Phase 2 complete | **Core Complete** |

**Total Estimated Time**: 3-4 weeks

### Completed Work (as of Jan 2026)

**Data Collection & Processing:**
- 90+ raw files downloaded (VDOE, FCPS, County, APA, NCES, VPAP)
- All VDOE tables (8, 15, 17, 18, 19) parsed to JSON
- County budget data extracted for FY2020-FY2026
- 16 Parquet files generated for Playground (27 MB total, 8x compression)

**Data Playground v2:**
- DuckDB-WASM engine fully operational
- Basic notebook UI with SQL execution
- Query results displayed as tables
- Ctrl+Enter keyboard shortcut for running queries

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
