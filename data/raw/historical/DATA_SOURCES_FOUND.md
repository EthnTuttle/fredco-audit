# Historical Financial Data Sources Found for FCPS Audit

**Date Searched:** January 28, 2026  
**Target District:** Frederick County Public Schools (VDOE Division Code: 069)  
**Target Years:** FY2020-FY2023

---

## Summary of Data Sources Found

### 1. FCPS Direct Budget Documents (BoardDocs)
**Location:** `data/raw/fcps/budgets/`

| File | Fiscal Year | Size | Notes |
|------|-------------|------|-------|
| FY26_Approved_Budget_LineItem.pdf | FY2026 | 55.5 MB | Full line-item budget |
| FY26_Approved_Budget_with_Addendum.pdf | FY2026 | 55.5 MB | Same as above |
| FY26_Superintendent_Proposed_Budget.pdf | FY2026 | 7.4 MB | Proposed budget |
| FY26_Superintendent_Proposed_Budget_Presentation.pdf | FY2026 | 13.7 MB | Budget presentation |
| FY26-29_Capital_Asset_Plan.pdf | FY2026-29 | 3.7 MB | Capital plan |
| FY25_Approved_Budget_LineItem.pdf | FY2025 | 37.3 MB | Full line-item budget |
| FY25_Approved_Budget_with_Addendum.pdf | FY2025 | 37.3 MB | Same as above |
| FY25_Approved_Budget_Summary.pdf | FY2025 | 90 KB | Summary only |
| FY25_Capital_Asset_Plan.pdf | FY2025 | 3.3 MB | Capital plan |
| FY25_YearEnd_Financial.pdf | FY2025 | 5.0 MB | Year-end financials |
| FY24_YearEnd_Financial.pdf | FY2024 | 2.5 MB | Year-end financials |

**Coverage:** FY2024-FY2026 (current year data)
**Gap:** FY2020-FY2023 budget documents NOT found on current website

### 2. FCPS Financial Reports & Audits (ACFR)
**Location:** `data/raw/fcps/acfr/`

| File | Fiscal Year | Notes |
|------|-------------|-------|
| FY25_Year-End_Financial_Reports.pdf | FY2025 | Year-end reports |
| FY24_Year-End_Financial_Statements.pdf | FY2024 | Financial statements |
| FY25_Activity_Fund_Audit.pdf | FY2025 | Activity fund audit |
| FY24_Activity_Fund_Audit.pdf | FY2024 | Activity fund audit |
| Internal_Audit_Aug24.pdf | FY2025 | Internal audit |

**Coverage:** FY2024-FY2025
**Note:** Comprehensive ACFR is part of Frederick County government reports

---

### 3. NCES School District Finance Survey (F-33)
**Location:** `data/raw/nces/historical/`

| File | Fiscal Year | Records | Status |
|------|-------------|---------|--------|
| sdf22_1a.txt | FY2022 | 19,572 districts | Provisional (Jun 2024) |
| sdf21_1a.txt | FY2021 | ~19,500 districts | Final |
| sdf20_1a.txt | FY2020 | ~19,500 districts | Final |
| sdf19_1a.txt | FY2019 | ~19,500 districts | Final |

**Coverage:** FY2019-FY2022 (EXCELLENT - covers target period!)

**Key Variables Available:**
- TOTALREV - Total Revenue
- TFEDREV - Federal Revenue
- TSTREV - State Revenue  
- TLOCREV - Local Revenue
- TCURELSC - Total Current Expenditures
- TCURINST - Instruction Expenditures
- TCURSSVC - Student Support Services
- TCURSPND - Student/Staff Support
- TCURADM - Administration
- V33 - Fall Membership (enrollment)

**NCES ID for Frederick County:** 5101470

---

### 4. Virginia APA Comparative Report
**Location:** `data/raw/apa/APA_Comparative_Report.xlsx`

**Size:** 1.27 MB  
**Content:** State comparative data including:
- Exhibit C-6: Education expenditures by category
- Multi-year historical data
- Per-pupil expenditures
- Administrative spending ratios

---

### 5. NCES District Directory Data
**Location:** `data/raw/nces/`

Current data for target districts:
- frederick_county_public_schools.json (Division 069)
- clarke_county_public_schools.json (Division 043)
- fauquier_county_public_schools.json (Division 061)
- shenandoah_county_public_schools.json (Division 171)
- warren_county_public_schools.json (Division 187)
- loudoun_county_public_schools.json (Division 107)

---

## Data Sources NOT Accessible (Require Manual Retrieval)

### 1. VDOE Superintendent's Annual Report Tables
**URL:** https://www.doe.virginia.gov/data-policy-funding/data-reports/statistics-reports/superintendent-s-annual-report

**Status:** Website returns 403 (bot protection)

**Tables Needed:**
- Table 3: Enrollment (ADM) by division
- Table 13: Instructional staff counts and salaries
- Table 15: Per pupil expenditures by source

**Recommendation:** Access manually via browser or FOIA request

### 2. ClearGov Historical Budgets
**URL:** https://www.cleargov.com/virginia/frederick/schools

**Status:** Site requires authentication/subscription for detailed data

### 3. BoardDocs Meeting Archives (FY2020-2023)
**URL:** https://go.boarddocs.com/va/fcpsva/Board.nsf/Public

**Status:** Older meeting archives may contain budget presentations from 2020-2023
**Recommendation:** Manual search of meeting minutes and attachments

### 4. Frederick County Government ACFR
**Status:** FCPS is a component unit of Frederick County
**Recommendation:** Request county ACFR documents for FY2020-2023 which include school board financials

### 5. Virginia School Quality Profiles
**URL:** https://schoolquality.virginia.gov/divisions/frederick-county-public-schools
**Status:** SSL certificate issue
**Content:** Contains financial efficiency data

---

## Recommended Next Steps

1. **Parse NCES F-33 Data (Priority 1)**
   - Extract Frederick County (LEAID: 5101470) from sdf19-22 files
   - This provides FY2019-FY2022 expenditure data
   - Compare with peer districts

2. **Parse APA Comparative Report (Priority 2)**
   - Extract Virginia education expenditure data
   - Contains historical per-pupil spending

3. **Manual VDOE Data Retrieval (Priority 3)**
   - Access VDOE website via browser
   - Download Tables 3, 13, 15 for FY2020-FY2024

4. **FOIA Request (If Needed)**
   - Request detailed budget breakdowns from FCPS Finance Department
   - Request FY2020-FY2023 approved budgets

5. **Internet Archive Search**
   - Use Wayback Machine to find archived FCPS budget pages
   - May contain direct links to older PDF documents

---

## Data Quality Assessment

| Source | FY2020 | FY2021 | FY2022 | FY2023 | FY2024 | FY2025 |
|--------|--------|--------|--------|--------|--------|--------|
| FCPS Budgets | X | X | X | X | ✓ | ✓ |
| NCES F-33 | ✓ | ✓ | ✓ | * | X | X |
| APA Report | ✓ | ✓ | ✓ | ✓ | ? | X |
| VDOE SAR | Manual | Manual | Manual | Manual | Manual | X |

✓ = Available  
X = Not available  
* = May be available (check latest release)  
? = Check report contents

---

*Generated by FCPS Audit Data Collection Script*
