# VDOE Data Download Instructions

## Status: Automated Download Blocked

The VDOE website (doe.virginia.gov) uses Akamai enterprise bot protection that blocks
automated access, including:
- curl/wget requests
- Python requests library
- Playwright/Puppeteer headless browsers
- Wayback Machine (rate limited)

## Manual Download Required

Please manually download the following files from:
**https://www.doe.virginia.gov/data-policy-funding/data-reports/statistics-reports/superintendent-s-annual-report**

### Files Needed:

#### Table 3 - Enrollment (ADM)
Save to: `data/raw/vdoe/table-3/`
- Table 3: 2023-24
- Table 3: 2022-23
- Table 3: 2021-22
- Table 3: 2020-21
- Table 3: 2019-20

#### Table 13 - Instructional Staff  
Save to: `data/raw/vdoe/table-13/`
- Table 13: 2023-24
- Table 13: 2022-23
- Table 13: 2021-22
- Table 13: 2020-21
- Table 13: 2019-20

#### Table 15 - Per Pupil Expenditures
Save to: `data/raw/vdoe/table-15/`
- Table 15: 2023-24
- Table 15: 2022-23
- Table 15: 2021-22
- Table 15: 2020-21
- Table 15: 2019-20

## File Naming Convention

Rename downloaded files as:
- `table-3-2023-24.xlsm` (or .xlsx)
- `table-13-2023-24.xlsm`
- etc.

## Alternative Data Sources

If VDOE site is inaccessible, try:
1. **NCES ELSI**: https://nces.ed.gov/ccd/elsi/tableGenerator.aspx
   - Has similar enrollment and expenditure data from federal sources
   
2. **Virginia School Quality Profiles**: https://schoolquality.virginia.gov
   
3. **Contact VDOE directly**: datarequest@doe.virginia.gov

## After Manual Download

After downloading the files, run:
```bash
python scripts/parse_excel.py --source vdoe --output data/processed/
```

