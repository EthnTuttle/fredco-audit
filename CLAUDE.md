# CLAUDE.md - AI Agent Instructions for FCPS Audit

## Project Overview

This project audits Frederick County Public Schools (FCPS) in Virginia for over-administration, spending trends, and fiscal efficiency. Public data has been mirrored locally, parsed into structured JSON format, and is ready for LLM-based inquiry and analysis.

**Target District**: Frederick County Public Schools (Division Code: 069)
**Peer Districts**: Clarke (043), Fauquier (061), Shenandoah (171), Warren (187), Loudoun (107)
**Scope**: FY2020-FY2025 (6 fiscal years)

---

## Current Data Status

### Data Collection: COMPLETE

| Source | Status | Files | Years |
|--------|--------|-------|-------|
| VDOE Tables 8, 15, 17, 18, 19 | Complete | 30+ Excel files | 2019-20 to 2024-25 |
| Frederick County Budgets | Complete | 21 PDFs | FY2020-FY2026 |
| FCPS School Budgets | Partial | FY23-FY26 complete | FY20-FY22 need FOIA |
| FCPS CIP Documents | Complete | 6 PDFs | 2020-2029 |
| APA Comparative Report | Complete | 1 Excel | FY2024 |
| NCES Data | Complete | 7 JSON files | FY2022 |
| VPAP Data | Complete | 2 JSON files | FY2024 |

### Data Processing: COMPLETE

All raw data has been parsed into structured JSON with full source references.

---

## Directory Structure

```
fredco-audit/
├── CLAUDE.md                    # This file - AI agent instructions
├── ROADMAP.md                   # Project roadmap and methodology
├── requirements.txt             # Python dependencies
├── scripts/
│   └── download_data.py         # Data download script (supports --source vdoe/fcps/apa)
├── data/
│   ├── raw/                     # Original downloaded files (90+ files)
│   │   ├── fcps/
│   │   │   ├── budgets/         # FCPS budget PDFs (FY23-FY26)
│   │   │   ├── acfr/            # Year-end financial reports
│   │   │   └── cip/             # Capital Improvement Plans
│   │   ├── fcva/
│   │   │   └── budgets/         # County budget PDFs (FY2020-FY2026)
│   │   ├── vdoe/
│   │   │   ├── table-8/         # Enrollment (ADM) data
│   │   │   ├── table-15/        # Per-pupil expenditures
│   │   │   ├── table-17/        # Pupil-teacher ratios
│   │   │   ├── table-18/        # Admin personnel positions
│   │   │   └── table-19/        # Instructional positions/salaries
│   │   ├── apa/                 # VA Auditor of Public Accounts
│   │   ├── nces/                # National Center for Education Statistics
│   │   └── vpap/                # Virginia Public Access Project
│   ├── processed/               # Structured JSON files
│   │   ├── vdoe/                # Parsed VDOE tables
│   │   │   ├── table8_enrollment.json
│   │   │   ├── table15_expenditures.json
│   │   │   ├── table17_ratios.json
│   │   │   ├── table18_admin_personnel.json
│   │   │   └── table19_instructional.json
│   │   ├── county_budget_schools.json  # County appropriations to schools
│   │   ├── ratios.json          # Calculated audit metrics
│   │   └── *.json               # Other processed data
│   ├── parquet/                 # Parquet files for Data Playground
│   │   ├── real_estate_tax.parquet    # 22 MB (from 212 MB JSON)
│   │   └── *.parquet            # Other converted files
│   └── analysis/                # Analysis results (to be generated)
├── specs/                       # Data Playground v2 specifications
│   ├── 00-architecture.md       # Overall system design
│   ├── 01-ui-shell.md           # UI orchestration layer
│   ├── 02-data-engine.md        # DuckDB-WASM integration
│   ├── 03-chart-engine.md       # Chart types and config
│   ├── 04-editor-engine.md      # Monaco editor setup
│   ├── 05-notes-engine.md       # Nostr integration
│   ├── 06-storage-engine.md     # IndexedDB caching
│   └── 07-integration.md        # Build pipeline
├── playground/                  # Data Playground v2 (DuckDB-WASM)
│   ├── Cargo.toml               # Rust workspace
│   ├── package.json             # NPM dependencies
│   ├── vite.config.ts           # Vite build configuration
│   ├── tsconfig.json            # TypeScript configuration
│   ├── index.html               # Entry point
│   ├── types/                   # Rust shared types crate
│   │   └── src/
│   │       ├── lib.rs           # Module exports
│   │       ├── messages.rs      # Request/Response types
│   │       ├── data.rs          # DataEngine types
│   │       ├── chart.rs         # ChartEngine types
│   │       ├── editor.rs        # EditorEngine types
│   │       ├── notes.rs         # NotesEngine types
│   │       └── storage.rs       # StorageEngine types
│   ├── data-engine/             # DuckDB integration crate
│   │   └── src/lib.rs
│   └── src/                     # TypeScript source
│       ├── main.ts              # Application entry
│       ├── engines/
│       │   └── data.ts          # DuckDB-WASM wrapper
│       ├── ui/                  # UI components (pending)
│       └── wasm/                # WASM output directory
└── schemas/                     # JSON schema definitions
```

---

## Key Processed Data Files

### 1. VDOE Table 8: Enrollment (`data/processed/vdoe/table8_enrollment.json`)

**Contains**: Average Daily Membership (ADM), Average Daily Attendance (ADA), attendance rates
**Years**: 2019-20 to 2024-25
**Divisions**: Frederick, Clarke, Fauquier, Shenandoah, Warren, Loudoun, State Total

```json
{
  "division_code": "069",
  "division_name": "Frederick County",
  "fiscal_year": "2023-24",
  "source_file": "table8_2023-24.xlsx",
  "metrics": {
    "adm_elementary": 8234,
    "adm_secondary": 5887,
    "adm_total": 14121,
    "ada_total": 13456,
    "attendance_pct_elementary": 94.8,
    "attendance_pct_secondary": 93.2
  }
}
```

### 2. VDOE Table 15: Expenditures (`data/processed/vdoe/table15_expenditures.json`)

**Contains**: Per-pupil spending by funding source (local, state, federal, sales tax)
**Years**: 2019-20 to 2023-24

```json
{
  "division_code": "069",
  "division_name": "Frederick County",
  "fiscal_year": "2023-24",
  "source_file": "table15_2023-24.xlsm",
  "metrics": {
    "adm": 14269,
    "local_amount": 105342642,
    "local_per_pupil": 7383,
    "state_amount": 85236783,
    "state_per_pupil": 5973,
    "federal_amount": 13693034,
    "federal_per_pupil": 960,
    "total_expenditures": 224518221,
    "total_per_pupil": 15734
  }
}
```

### 3. VDOE Table 17: Pupil-Teacher Ratios (`data/processed/vdoe/table17_ratios.json`)

**Contains**: Student-to-teacher ratios for K-7 and 8-12
**Years**: 2019-20 to 2023-24

### 4. VDOE Table 18: Admin Personnel (`data/processed/vdoe/table18_admin_personnel.json`)

**Contains**: Administrative, service, and support staff positions by function
**Categories**: Instruction, Admin/Health, Technology, Transportation, Operations, Facilities

```json
{
  "metrics": {
    "instruction": { "administrative": 15, "technical_clerical": 45, "support": 120 },
    "admin_health": { "administrative": 25, "technical_clerical": 18 },
    "technology": { "administrative": 3, "technical_clerical": 12 },
    "transportation": { "administrative": 2, "trades_service": 85 },
    "operations": { "administrative": 3, "trades_service": 95 },
    "summary": { "administrative": 48, "total": 450 }
  }
}
```

### 5. VDOE Table 19: Instructional Staff (`data/processed/vdoe/table19_instructional.json`)

**Contains**: Teacher/principal counts and average salaries
**Includes**: Elementary/secondary principals, assistant principals, teachers, aides

### 6. County Budget Schools (`data/processed/county_budget_schools.json`)

**Contains**: Frederick County budget appropriations to schools
**Years**: FY2020-FY2025

```json
{
  "fiscal_year": "FY2025",
  "source_file": "FY2025_adopted.pdf",
  "total_county_budget_all_funds_net": 492899936,
  "county_transfers": {
    "to_school_operating": 109034028,
    "to_school_debt": 20460000,
    "to_school_capital": 4000000,
    "total_county_to_schools": 133494028,
    "pct_of_general_fund": 51.2
  },
  "school_funds": {
    "total_school_funds": 281068060,
    "pct_of_total_budget": 57.02
  }
}
```

---

## Division Codes Reference

| Division | Code | Type |
|----------|------|------|
| Frederick County | 069 | Target |
| Clarke County | 043 | Peer |
| Fauquier County | 061 | Peer |
| Shenandoah County | 171 | Peer |
| Warren County | 187 | Peer |
| Loudoun County | 107 | Peer (larger) |
| Virginia State Total | STATE | Benchmark |

---

## Key Metrics for Analysis

### Frederick County Summary (FY2023-24)

| Metric | Value | State Avg | Status |
|--------|-------|-----------|--------|
| Enrollment (ADM) | 14,121 | - | - |
| Per-Pupil Spending | $15,734 | $17,636 | 10.8% below |
| K-7 Pupil-Teacher Ratio | 13.8:1 | 12.3:1 | Higher (more students/teacher) |
| 8-12 Pupil-Teacher Ratio | 12.3:1 | 12.3:1 | At state average |

### County Budget Trends (FY2020-FY2025)

| Metric | FY2020 | FY2025 | Change |
|--------|--------|--------|--------|
| Total County Budget | $343.4M | $492.9M | +43.5% |
| Total to Schools | $208.8M | $281.1M | +34.6% |
| School % of Budget | 60.8% | 57.0% | -3.8 pts |
| County Transfer to Schools | $106.7M | $133.5M | +25.1% |

---

## How to Query This Data

### Load Processed Data

```python
import json

# Load enrollment data
with open('data/processed/vdoe/table8_enrollment.json') as f:
    enrollment = json.load(f)

# Filter for Frederick County
fc_enrollment = [r for r in enrollment['data'] if r['division_code'] == '069']

# Get specific year
fy24 = next(r for r in fc_enrollment if r['fiscal_year'] == '2023-24')
print(f"Frederick County ADM (2023-24): {fy24['metrics']['adm_total']}")
```

### Common Analysis Queries

1. **Compare per-pupil spending across peer districts**
```python
with open('data/processed/vdoe/table15_expenditures.json') as f:
    data = json.load(f)
fy24 = [r for r in data['data'] if r['fiscal_year'] == '2023-24']
for r in sorted(fy24, key=lambda x: x['metrics']['total_per_pupil']):
    print(f"{r['division_name']}: ${r['metrics']['total_per_pupil']:,}")
```

2. **Track Frederick County spending growth**
```python
fc_data = [r for r in data['data'] if r['division_code'] == '069']
for r in sorted(fc_data, key=lambda x: x['fiscal_year']):
    print(f"{r['fiscal_year']}: ${r['metrics']['total_per_pupil']:,}")
```

3. **Calculate admin staff ratios**
```python
with open('data/processed/vdoe/table18_admin_personnel.json') as f:
    admin = json.load(f)
with open('data/processed/vdoe/table8_enrollment.json') as f:
    enrollment = json.load(f)
# Join on division_code and fiscal_year to calculate admin-to-student ratios
```

---

## Source References

Every data point includes source references for auditability:

- `source_file`: Original filename (e.g., "table15_2023-24.xlsm")
- `source_url`: Official data source URL
- `source_page` or `source_row`: Exact location in source document
- `fiscal_year`: Fiscal year of the data

**Primary Source URLs**:
- VDOE: https://www.doe.virginia.gov/data-policy-funding/data-reports/statistics-reports/superintendent-s-annual-report
- Frederick County Budget: https://fcva.us/departments/finance/budget/budget-archives
- FCPS Budget: https://www.frederickcountyschoolsva.net/about/budget

---

## Red Flags to Investigate

| Indicator | Threshold | Current Status |
|-----------|-----------|----------------|
| Admin ratio | >10% | Check Table 18 data |
| Admin growth > enrollment | >2x | Calculate from trends |
| Instruction ratio | <60% | Check Table 15 data |
| Per-pupil below state avg | >15% below | Currently 10.8% below |
| School % of county budget declining | Year-over-year decline | Declined 3.8 pts since FY2020 |

---

## Data Gaps & Limitations

### Gap 1: FCPS Detailed Budget Documents (FY2020-FY2022)

**Issue**: Full FCPS annual budget documents for FY2020, FY2021, and FY2022 are not available on the current FCPS website or BoardDocs. These older documents predate when FCPS began uploading comprehensive budget PDFs to BoardDocs.

**What We Have**:
- FY2022: Year-End Financial Report only
- FY2023-FY2026: Full approved budget documents with line-item detail

**How We Covered It**:
1. **VDOE Data (Primary)**: The VDOE Superintendent's Annual Report Tables 15, 18, and 19 contain the official audited expenditure and staffing data for all years (2019-20 through 2023-24). This is actually MORE reliable than school-produced budget documents because it's standardized state reporting.
2. **County Budget Data**: Frederick County budget documents (all years FY2020-FY2026) show the transfers TO schools, providing the funding side of the equation.
3. **Year-End Financial Reports**: Downloaded where available, which show actual expenditures vs. budgeted.

**To Remedy (if line-item detail needed)**:
- Submit FOIA request to FCPS Finance Department for adopted budget documents FY2020-FY2022
- Contact: https://www.frederickcountyschoolsva.net/about/contact-us
- Request template: "Pursuant to the Virginia Freedom of Information Act, I request copies of the Adopted Annual Budget documents for Frederick County Public Schools for fiscal years 2020, 2021, and 2022."

---

### Gap 2: VDOE 2024-25 Expenditure Data

**Issue**: VDOE releases expenditure data (Tables 15, 17, 18, 19) approximately 6-12 months after the fiscal year ends. FY2024-25 expenditure data is not yet available.

**What We Have**:
- Table 8 (Enrollment): Available through 2024-25
- Tables 15, 17, 18, 19: Available through 2023-24

**How We Covered It**:
- The audit scope (FY2020-FY2025) can use FY2024-25 enrollment data with FY2023-24 expenditure data for the most recent year
- 5 full years of expenditure data (2019-20 through 2023-24) is sufficient for trend analysis

**To Remedy**:
- Check VDOE website quarterly: https://www.doe.virginia.gov/data-policy-funding/data-reports/statistics-reports/superintendent-s-annual-report
- FY2024-25 expenditure tables typically released by December 2025

---

### Gap 3: State Average/Total Data Inconsistency

**Issue**: Some VDOE tables include state totals, others only include division-level data. State averages must be calculated differently depending on the table.

**What We Have**:
- Table 8: State totals included
- Table 15: State totals included
- Table 17: State averages included
- Tables 18, 19: State totals included (but labeled differently)

**How We Covered It**:
- Parsed state totals where available and included in JSON with `division_code: "STATE"` or `division_name: "State Total"`
- For tables without explicit state averages, they can be calculated from division data

---

### Gap 4: Table 15 File Format Issues (Older Years)

**Issue**: Some VDOE Table 15 files for FY2020-FY2022 were distributed as ZIP archives or had Excel format issues preventing direct parsing.

**What We Have**:
- `table15_2019-20.xlsm` and `table15_2019-20_new.xlsm` (re-downloaded)
- `table15_2020-21.xlsm` and `table15_2020-21_new.xlsm` (re-downloaded)
- `table15_2021-22.zip` (contains XLSM)
- `table15_2022-23.zip` (contains XLSM)
- `final-fy20-table-15.xlsm` through `final-fy23-table-15.xlsm` (final versions)

**How We Covered It**:
- Downloaded both original and "final" versions where available
- ZIP files extracted to access XLSM contents
- Parsing uses the `final-fy*` versions which are the corrected/final releases
- All 5 years successfully parsed into `table15_expenditures.json`

---

### Gap 5: FCPS School-Level Budget Breakdown

**Issue**: We have division-level (district-wide) data but not individual school budgets. This limits analysis of resource allocation across schools.

**What We Have**:
- Division-level totals for all metrics
- No per-school breakdowns

**How We Covered It**:
- Division-level data is sufficient for the administrative overhead audit
- School-level data is available in FCPS budget documents (FY23-FY26) if deeper analysis needed

**To Remedy**:
- FCPS approved budgets contain school-by-school allocations
- VDOE School Quality Profiles have some school-level data: https://schoolquality.virginia.gov/

---

### Gap 6: Function-Level Expenditure Detail

**Issue**: VDOE Table 15 provides expenditures by FUNDING SOURCE (local, state, federal) but not by FUNCTION (instruction, administration, operations). Function-level data requires different sources.

**What We Have**:
- Table 15: Funding source breakdown (local/state/federal per pupil)
- Table 18: Administrative STAFFING counts (not dollars)
- Table 19: Instructional STAFFING counts and salaries

**How We Covered It**:
1. **APA Comparative Report**: Contains expenditures by function category for all VA school divisions
2. **NCES Data**: Contains expenditure breakdowns by function
3. **FCPS Budget Documents**: FY23-FY26 budgets have detailed function breakdowns

**Processed Files with Function Data**:
- `data/processed/apa_data.json` - Function-level expenditures
- `data/processed/ratios.json` - Calculated instruction/admin ratios

---

### Data Coverage Summary

| Data Type | FY2020 | FY2021 | FY2022 | FY2023 | FY2024 | FY2025 |
|-----------|:------:|:------:|:------:|:------:|:------:|:------:|
| VDOE Enrollment (T8) | Y | Y | Y | Y | Y | Y |
| VDOE Expenditures (T15) | Y | Y | Y | Y | Y | - |
| VDOE Ratios (T17) | Y | Y | Y | Y | Y | - |
| VDOE Admin Staff (T18) | Y | Y | Y | Y | Y | - |
| VDOE Instructional (T19) | Y | Y | Y | Y | Y | - |
| County Budget | Y | Y | Y | Y | Y | Y |
| FCPS Full Budget | - | - | - | Y | Y | Y |
| FCPS Year-End Report | - | - | Y | Y | Y | - |

**Legend**: Y = Available, - = Not Available/Not Yet Released

---

## Scripts

### Download Data
```bash
# Download VDOE tables (uses wget with proper headers)
python scripts/download_data.py --source vdoe

# Download all sources
python scripts/download_data.py --all
```

### Re-process Data
If you need to re-parse the raw data, the parsing logic used:
- `openpyxl` for XLSX/XLSM files
- `pdfplumber` for PDF extraction
- Division filtering for the 6 target districts + state totals

---

## Next Steps for Analysis

1. **Calculate Audit Ratios**: Generate admin-to-student, admin-to-teacher, instruction % ratios
2. **Peer Comparison Dashboard**: Create visualizations comparing Frederick to peers
3. **Trend Analysis**: 5-year CAGR for spending categories vs. enrollment
4. **Red Flag Report**: Identify metrics that exceed warning thresholds
5. **Findings Document**: Summarize audit conclusions with source citations

---

## File Counts

| Location | Files | Size |
|----------|-------|------|
| data/raw/vdoe/ | 35 | ~5 MB |
| data/raw/fcva/budgets/ | 21 | ~117 MB |
| data/raw/fcps/ | 25 | ~250 MB |
| data/processed/vdoe/ | 5 | ~165 KB |
| data/processed/*.json | 15 | ~200 KB |
| data/parquet/ | 16 | ~27 MB |
| playground/ | 20+ | ~5 KB (source) |
| specs/ | 8 | ~50 KB |
| **Total** | ~120 | ~400 MB |

---

## Data Playground v2

### Overview

The Data Playground v2 is an interactive browser-based tool for exploring audit data using SQL queries. It uses DuckDB-WASM for fast analytical queries against Parquet data files.

### Key Features

**Working Now:**
- **DuckDB-WASM**: In-browser SQL engine for analytical queries
- **Parquet Data**: 16 files, 27 MB total (8x smaller than JSON)
- **SQL Query Execution**: Run queries with Ctrl+Enter
- **Results Tables**: Paginated table display (up to 1000 rows)
- **Table Browser**: Click tables to generate SELECT queries

**Planned:**
- **Notebook Interface**: SQL + Markdown cells like Jupyter
- **Charts**: Bar, line, pie, scatter, choropleth maps (Chart.js)
- **Monaco Editor**: SQL syntax highlighting and autocomplete
- **Nostr Notes**: Publish findings to decentralized network
- **Offline Support**: IndexedDB caching for offline use

### Architecture

```
┌─────────────────────────────────────────────────┐
│               Browser (WASM)                    │
├─────────────────────────────────────────────────┤
│  DuckDB-WASM ──► SQL Queries ──► Results        │
│       │                              │          │
│       ▼                              ▼          │
│  Parquet Files              Chart.js / Tables   │
│  (from /data/parquet/)                          │
└─────────────────────────────────────────────────┘
```

### Running the Playground

```bash
# From playground/ directory
cd playground

# Install dependencies (first time)
npm install

# Start development server
npm run dev
# Opens at http://localhost:3001

# Build for production
npm run build
```

### Available Data Tables

When loaded, the playground creates views for Parquet files:

| Table Name | Description | Size |
|------------|-------------|------|
| `real_estate_tax` | Property tax records (45K+ records) | 22 MB |
| `county_department_detail` | County budget line items by department | 4 MB |
| `districts` | District geographic boundaries | 306 KB |
| `ownership_analysis` | Property ownership statistics | 112 KB |
| `county_budget_schools` | County transfers to schools FY2020-2025 | 37 KB |
| `county_government_analysis` | Government spending analysis | 37 KB |
| `vdoe_table18_admin` | Admin personnel by division/year | 30 KB |
| `vdoe_table19_instructional` | Instructional staff by division/year | 30 KB |
| `tax_summary` | Tax summary statistics | 31 KB |
| `expenditures` | FCPS expenditure data | 16 KB |
| `apa_data` | APA comparative data all localities | 14 KB |
| `vdoe_table15_expenditures` | Per-pupil expenditures by division | 13 KB |
| `vdoe_table8_enrollment` | Enrollment (ADM) by division/year | 12 KB |
| `apa_education_expenditures` | Education spending by locality | 10 KB |
| `vdoe_table17_ratios` | Pupil-teacher ratios | 9 KB |
| `enrollment` | Enrollment summary | 6 KB |

**Total: 16 tables, 27 MB Parquet data**

### Example Queries

```sql
-- Count records
SELECT COUNT(*) FROM real_estate_tax;

-- Get unique values
SELECT DISTINCT owner_type FROM real_estate_tax;

-- Aggregate by category
SELECT 
  entity_type,
  COUNT(*) as count,
  SUM(assessed_value) as total_value
FROM real_estate_tax
GROUP BY entity_type
ORDER BY total_value DESC;
```

### Rust Types

The playground uses Rust types compiled to WASM for type safety. Types are defined in `playground/types/src/`:

| Module | Purpose |
|--------|---------|
| `messages.rs` | Request/Response envelope types |
| `data.rs` | DataEngine query types |
| `chart.rs` | Chart configuration types |
| `editor.rs` | Notebook cell types |
| `notes.rs` | Nostr integration types |
| `storage.rs` | IndexedDB persistence types |

### Build Commands

```bash
# Build Rust types (from playground/)
cargo build

# Build WASM modules
npm run build:wasm

# TypeScript type check
npm run typecheck

# Full production build
npm run build
```

### Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Rust Types | **Complete** | All type definitions in `playground/types/` |
| DuckDB Engine | **Complete** | Query execution working |
| Basic UI | **Complete** | SQL input, results table, table browser |
| Parquet Data | **Complete** | 16 files generated in `data/parquet/` |
| Vite Build | **Complete** | Dev server on port 3001 |
| Chart Engine | Pending | Chart.js integration |
| Editor Engine | Pending | Monaco integration |
| Notes Engine | Pending | Nostr integration |
| Storage Engine | Pending | IndexedDB caching |

### Specifications

Detailed specifications are in `specs/`:

- `00-architecture.md` - System architecture
- `01-ui-shell.md` - UI component design
- `02-data-engine.md` - DuckDB-WASM setup
- `03-chart-engine.md` - Chart types (including choropleth)
- `04-editor-engine.md` - Monaco editor config
- `05-notes-engine.md` - Nostr NIP-07/NIP-46 support
- `06-storage-engine.md` - IndexedDB schema
- `07-integration.md` - Build and deploy pipeline

---

## Git Worktrees for Parallel Development

The project uses git worktrees for parallel feature development:

```
/home/ethan/code/
├── fredco-audit/              # master - Main development, analysis work
├── fredco-audit-chart/        # feature/chart-engine - Chart.js integration
├── fredco-audit-editor/       # feature/editor-engine - Monaco SQL editor
└── fredco-audit-notes/        # feature/notes-engine - Nostr publishing
```

### Worktree Commands

```bash
# List all worktrees
git worktree list

# Switch to a worktree
cd ../fredco-audit-chart

# After completing work, rebase onto master before merging
git fetch origin master
git rebase origin/master
git checkout master
git merge feature/chart-engine

# Remove a worktree when done
git worktree remove ../fredco-audit-chart
git branch -d feature/chart-engine
```

### Work Assignment

| Worktree | Branch | Focus | Key Files |
|----------|--------|-------|-----------|
| `fredco-audit` | master | Analysis, coordination | `data/analysis/` |
| `fredco-audit-chart` | feature/chart-engine | Chart.js visualizations | `playground/src/engines/chart.ts` |
| `fredco-audit-editor` | feature/editor-engine | Monaco SQL editor | `playground/src/engines/editor.ts` |
| `fredco-audit-notes` | feature/notes-engine | Nostr publishing | `playground/src/engines/notes.ts` |

### Development Workflow

1. Work in the appropriate worktree for your feature
2. Each worktree needs its own `npm install` in `playground/`
3. Run `npm run dev` to test changes
4. Commit frequently to feature branch
5. Before merging: `git rebase master` to incorporate latest changes
6. Merge to master with regular merge (not squash) to preserve history
