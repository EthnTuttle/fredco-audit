# Auditing Frederick County Schools: A Data-Driven Deep Dive into Public School Spending

*How we collected, processed, and visualized six years of public education data to answer a simple question: Is our school district over-administered?*

---

## The Question That Started It All

Every year, Frederick County, Virginia transfers over $130 million to its public school system. That's more than half of the county's general fund. As taxpayers, residents have a right to know: Is that money being spent wisely? Are we top-heavy with administrators while classrooms are overcrowded? How do we compare to our neighbors?

This project set out to answer those questions with data, not opinions.

---

## What Data Did We Collect?

The first challenge was gathering comprehensive, authoritative data. We pulled from seven different public sources to build a complete picture spanning fiscal years 2020-2025:

### Virginia Department of Education (VDOE)
The backbone of our analysis. VDOE publishes detailed annual reports on every school division in Virginia:

- **Table 8**: Enrollment data (Average Daily Membership and Attendance)
- **Table 15**: Per-pupil expenditures broken down by funding source (local, state, federal)
- **Table 17**: Pupil-teacher ratios for elementary and secondary
- **Table 18**: Administrative and support staff positions by function
- **Table 19**: Instructional positions and average teacher salaries

### Frederick County Government Budgets
We downloaded 21 county budget PDFs covering FY2020-FY2026. These show exactly how much the county appropriates to schools each year—and how that compares to other county priorities.

### FCPS School District Budgets
The school district's own budget documents (FY2023-FY2026) provide line-item detail on how funds are allocated across schools and functions.

### Additional Sources
- **Virginia Auditor of Public Accounts (APA)**: Function-level expenditure comparisons across all VA districts
- **NCES Common Core of Data**: Federal education statistics for national context
- **VPAP (Virginia Public Access Project)**: Political spending and education funding data
- **County Real Estate Tax Records**: To understand the tax burden context

In total: **90+ source files, ~375 MB of raw data**.

---

## How Did We Analyze It?

Raw Excel files and PDFs don't answer questions—structured data does. We built a processing pipeline to transform everything into queryable JSON files with full source references for auditability.

### The Processing Pipeline

```
Raw Data (XLSX, PDF, ZIP)
    ↓
Python Scripts (openpyxl, pdfplumber, pandas)
    ↓
Structured JSON (with source citations)
    ↓
Audit Metrics (ratios, comparisons, trends)
    ↓
Interactive Dashboards (Chart.js, Leaflet)
```

### Key Scripts

- `parse_excel.py` — Extracts data from VDOE's complex multi-sheet Excel workbooks
- `parse_county_budget.py` — Uses pdfplumber to pull budget tables from county PDFs
- `calculate_audit_metrics.py` — The heart of the audit: calculates admin ratios, peer comparisons, and flags anomalies

### Peer Comparison Methodology

No number means anything in isolation. We compared Frederick County against:

| District | Why Compare? |
|----------|--------------|
| Clarke County | Small rural neighbor |
| Fauquier County | Similar size, similar demographics |
| Shenandoah County | Adjacent valley district |
| Warren County | Adjacent district |
| Loudoun County | Larger regional benchmark |
| Virginia State Average | Statewide baseline |

Every metric shows where Frederick stands in this peer group.

---

## What Does the Site Display?

We built four interactive dashboards to make the data accessible:

### 1. County Government Dashboard (`index.html`)
- Total county budget growth over time
- Department-by-department spending breakdown
- How much goes to schools vs. other county functions
- Personnel counts and growth rates

### 2. FCPS Schools Dashboard (`schools.html`)
The star of the audit. This dashboard answers the core questions:

**Admin Efficiency Metrics**
- Admin positions per 1,000 students
- Students per administrator
- Admin as percentage of total staff
- 5-year admin growth vs. enrollment growth

**Peer Comparison Charts**
- Per-pupil spending across all peer districts
- Admin ratios: Who's leanest? Who's most bloated?
- Class sizes compared to state averages

**Trend Analysis**
- Enrollment trajectory (is it growing or shrinking?)
- Spending growth vs. enrollment growth
- Teacher salary trends

### 3. Interactive District Map (`map.html`)
A Leaflet.js map showing school district boundaries with key metrics overlaid. Click any district to see its stats.

### 4. Real Estate Analysis (`real_estate.html`)
Context matters. This dashboard shows property values and tax rates so you can understand the funding picture.

---

## What Did We Find?

The results surprised us.

### The Good News: Frederick County is NOT Over-Administered

Despite concerns about bureaucratic bloat, the data tells a different story:

| Metric | Frederick County | Finding |
|--------|-----------------|---------|
| Admin per 1,000 students | 1.73 | **Lowest among all peers** |
| Students per admin | 579.7 | **Highest among peers** (most efficient) |
| Admin % of staff | 1.26% | Well below 10% warning threshold |
| Admin growth vs. enrollment | 1.7x | Below 2.0x threshold |

Frederick County Public Schools runs the leanest administration of any comparable district in the region.

### The Concerns Worth Watching

**1. Per-Pupil Spending is Below Average**
At $15,734 per student, Frederick spends 10.8% less than the Virginia state average of $17,636. Is this efficiency or underfunding?

**2. K-7 Class Sizes are Larger Than Average**
Elementary pupil-teacher ratio of 13.9:1 is 12% higher than the state average of 12.4:1. More students per teacher could impact educational quality.

**3. Schools' Share of County Budget is Declining**
In FY2020, schools received 60.8% of the county budget. By FY2025, that dropped to 57.0%. The absolute dollars increased, but schools are getting a smaller slice of a growing pie.

### Historical NCES Data Showed One Red Flag
The FY2022 federal data (NCES) showed administration spending at 10.4% of total expenditures—slightly above our 10% threshold. However, current VDOE data shows this has improved.

---

## The Technical Stack

For those interested in replicating this approach:

- **Data Processing**: Python 3, pandas, openpyxl, pdfplumber
- **Frontend**: Static HTML, vanilla JavaScript, CSS
- **Charting**: Chart.js for dashboards, Plotly for detailed analysis
- **Mapping**: Leaflet.js with GeoJSON district boundaries
- **Data Format**: JSON with source citations for every data point
- **Hosting**: Static files—no database, no server required

The entire site can be hosted on GitHub Pages, Netlify, or any static host.

---

## What Else Could We Do?

This project answered our initial questions, but it opened doors to deeper investigations. Here's what we're considering:

### 1. School-Level Analysis
We have division-level data, but what about individual schools? Are resources distributed equitably across Frederick County's elementary, middle, and high schools? Do schools in different neighborhoods get different funding?

### 2. Outcomes Correlation
We've analyzed inputs (spending, staffing), but what about outputs? How do SOL scores, graduation rates, and college readiness correlate with spending levels? Are high-spending districts getting better results?

### 3. Salary Benchmarking
Teachers in Frederick County earn an average of $66,441. How does that compare to cost-of-living-adjusted salaries in peer districts? Are we competitive enough to attract and retain talent?

### 4. Capital Spending Deep Dive
We have CIP (Capital Improvement Plan) documents but haven't fully analyzed them. How much is going to new construction vs. maintenance? Are we addressing facility needs proactively or reactively?

### 5. Special Education Analysis
Federal IDEA funding and special education costs are growing nationwide. How is Frederick County handling this mandate? What's the local contribution beyond federal requirements?

### 6. Longitudinal Staffing Analysis
We know current admin ratios are healthy, but what about turnover? Are we losing experienced teachers? What's the tenure distribution of our teaching staff?

### 7. Revenue Source Diversification
How dependent is FCPS on local property taxes vs. state funding? What happens to school funding if real estate values decline?

### 8. Predictive Modeling
With 6 years of data, can we project future enrollment, staffing needs, and budget requirements? What if we see a 10% enrollment increase from new housing developments?

### 9. Public Engagement Tools
Could we build a "what if" calculator where residents explore trade-offs? "If we increase per-pupil spending by $500, what would that cost in property taxes?"

### 10. Expand to Other Counties
The pipeline we built works for any Virginia school division. We could audit every district in the Shenandoah Valley—or the entire state.

---

## Conclusion

Public data exists for a reason: accountability. But raw data locked in PDFs and spreadsheets doesn't inform anyone. By collecting, processing, and visualizing this information, we've made it possible for any resident to understand how their schools are funded and whether that money is being spent wisely.

The answer, at least for Frederick County, is encouraging: **our schools are running lean**, perhaps even too lean given the larger-than-average class sizes. The debate shouldn't be about administrative bloat—it should be about whether we're investing enough in the classroom.

All of our data, code, and methodology is available in this repository. We invite scrutiny, corrections, and contributions.

*Because in the end, these are our schools. We should know how they're run.*

---

**Data Sources**: Virginia Department of Education, Frederick County Government, FCPS, Virginia Auditor of Public Accounts, NCES, VPAP

**Methodology**: All calculations use official state-reported data with full source citations. Peer districts selected based on geographic proximity and demographic similarity.

**Questions or Corrections?** Open an issue in this repository.
