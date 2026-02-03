/**
 * Open Frederick Data Playground
 * 
 * Interactive SQL playground for exploring Frederick County, Virginia public data.
 * Includes: Schools, County Budget, Property Tax, Government Spending.
 * Features: DuckDB-WASM queries, Chart.js visualizations, shareable query links.
 */

import { initDataEngine, executeQuery, getLoadedTables, getTableSchema, type QueryResult } from './engines/data';
import { getChartEngine, type ChartType, type ChartOptions } from './engines/chart';
import { editorEngine } from './engines/editor';
import { getCacheStats, getStorageQuota, clearCache } from './engines/storage';
import { COLOR_RAMPS } from './engines/map';

// ============================================================================
// Shareable Query State
// ============================================================================

interface ShareableState {
  v: number;        // version for future compatibility
  q: string;        // SQL query
  t?: string;       // view type: table|bar|line|pie|doughnut|scatter
  n?: string;       // optional title/name
}

/**
 * Encode state to URL-safe base64
 */
function encodeShareableState(state: ShareableState): string {
  const json = JSON.stringify(state);
  // Use base64url encoding (URL-safe)
  const base64 = btoa(unescape(encodeURIComponent(json)));
  return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/**
 * Decode state from URL-safe base64
 */
function decodeShareableState(encoded: string): ShareableState | null {
  try {
    // Restore standard base64
    let base64 = encoded.replace(/-/g, '+').replace(/_/g, '/');
    // Add padding if needed
    while (base64.length % 4) base64 += '=';
    const json = decodeURIComponent(escape(atob(base64)));
    const state = JSON.parse(json) as ShareableState;
    // Validate
    if (typeof state.v !== 'number' || typeof state.q !== 'string') {
      return null;
    }
    return state;
  } catch {
    return null;
  }
}

/**
 * Get shareable state from current app state
 */
function getCurrentShareableState(): ShareableState {
  return {
    v: 1,
    q: editorEngine.getValue(),
    t: state.viewMode === 'chart' ? state.chartType : 'table',
  };
}

/**
 * Generate a shareable URL for the current query
 */
function generateShareUrl(): string {
  const shareState = getCurrentShareableState();
  const encoded = encodeShareableState(shareState);
  const url = new URL(window.location.href);
  url.hash = `share=${encoded}`;
  return url.toString();
}

/**
 * Load shared state from URL hash
 */
function loadFromUrlHash(): ShareableState | null {
  const hash = window.location.hash;
  if (!hash.startsWith('#share=')) return null;
  const encoded = hash.slice(7); // Remove '#share='
  return decodeShareableState(encoded);
}

/**
 * Copy text to clipboard with fallback
 */
async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Fallback for older browsers
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand('copy');
      return true;
    } catch {
      return false;
    } finally {
      document.body.removeChild(textarea);
    }
  }
}

// ============================================================================
// Query Templates - Human-readable presets for common analyses
// ============================================================================

interface QueryTemplate {
  name: string;
  description: string;
  sql: string;
  category: 'budget' | 'schools' | 'property' | 'government' | 'gis';
}

const QUERY_TEMPLATES: QueryTemplate[] = [
  // County Budget
  {
    name: 'County Budget Overview',
    description: 'Total county budget by year',
    category: 'budget',
    sql: `-- Frederick County budget overview
SELECT 
  fiscal_year AS "Year",
  total_county_budget_all_funds_net AS "Total Budget",
  county_transfers_total_county_to_schools AS "To Schools",
  county_transfers_pct_of_general_fund AS "Schools %"
FROM county_budget_schools
ORDER BY fiscal_year`
  },
  {
    name: 'County vs Schools Funding',
    description: 'How county funding to schools has changed',
    category: 'budget',
    sql: `-- County transfers to schools over time
SELECT 
  fiscal_year AS "Year",
  county_transfers_to_school_operating AS "Operating",
  county_transfers_to_school_debt AS "Debt Service", 
  county_transfers_to_school_capital AS "Capital",
  county_transfers_total_county_to_schools AS "Total"
FROM county_budget_schools
ORDER BY fiscal_year`
  },
  {
    name: 'General Fund Breakdown',
    description: 'Where general fund money goes',
    category: 'budget',
    sql: `-- General fund expenditures by category
SELECT 
  fiscal_year AS "Year",
  general_fund_expenditures_public_safety AS "Public Safety",
  general_fund_expenditures_school_transfers AS "Schools",
  general_fund_expenditures_health_welfare AS "Health/Welfare",
  general_fund_expenditures_public_works AS "Public Works"
FROM county_budget_schools
ORDER BY fiscal_year`
  },

  // Schools
  {
    name: 'School Spending Comparison',
    description: 'Per-pupil spending across districts',
    category: 'schools',
    sql: `-- Per-pupil spending by district (2023-24)
SELECT 
  division_name AS "District",
  metrics_total_per_pupil AS "$/Student",
  metrics_local_per_pupil AS "Local",
  metrics_state_per_pupil AS "State"
FROM vdoe_table15_expenditures 
WHERE fiscal_year = '2023-24'
ORDER BY metrics_total_per_pupil DESC`
  },
  {
    name: 'Enrollment Trends',
    description: 'Frederick County student enrollment over time',
    category: 'schools',
    sql: `-- Frederick enrollment trend
SELECT 
  fiscal_year AS "Year",
  metrics_adm_total AS "Students",
  metrics_adm_elementary AS "Elementary",
  metrics_adm_secondary AS "Secondary"
FROM vdoe_table8_enrollment
WHERE division_name = 'Frederick County'
ORDER BY fiscal_year`
  },
  {
    name: 'Teacher Ratios',
    description: 'Students per teacher by district',
    category: 'schools',
    sql: `-- Pupil-teacher ratios by district
SELECT 
  division_name AS "District",
  metrics_pupil_teacher_ratio_k7 AS "K-7 Ratio",
  metrics_pupil_teacher_ratio_8_12 AS "8-12 Ratio"
FROM vdoe_table17_ratios
WHERE fiscal_year = '2023-24'
ORDER BY metrics_pupil_teacher_ratio_k7`
  },
  {
    name: 'Admin Staff Counts',
    description: 'Administrative positions by district',
    category: 'schools',
    sql: `-- Admin staff by district
SELECT 
  division_name AS "District",
  metrics_instruction_administrative AS "Instruction Admin",
  metrics_admin_health_administrative AS "Admin/Health",
  metrics_technology_administrative AS "Technology"
FROM vdoe_table18_admin
WHERE fiscal_year = '2023-24'
ORDER BY metrics_instruction_administrative DESC`
  },
  {
    name: 'Peer District Comparison',
    description: 'Frederick vs similar rural counties',
    category: 'schools',
    sql: `-- Compare Frederick to peer districts
SELECT 
  e.division_name AS "District",
  e.metrics_adm_total AS "Students",
  x.metrics_total_per_pupil AS "$/Student",
  r.metrics_pupil_teacher_ratio_k7 AS "K-7 Ratio"
FROM vdoe_table8_enrollment e
JOIN vdoe_table15_expenditures x 
  ON e.division_name = x.division_name AND e.fiscal_year = x.fiscal_year
JOIN vdoe_table17_ratios r 
  ON e.division_name = r.division_name AND e.fiscal_year = r.fiscal_year
WHERE e.fiscal_year = '2023-24'
  AND e.division_name IN ('Frederick County', 'Clarke County', 'Shenandoah County', 'Warren County', 'Fauquier County')
ORDER BY x.metrics_total_per_pupil DESC`
  },

  // Property Tax
  {
    name: 'Top Property Owners',
    description: 'Largest landowners by assessed value',
    category: 'property',
    sql: `-- Top 25 property owners (2024)
WITH owners AS (
  SELECT json(top_owners_by_value) as arr
  FROM ownership_analysis WHERE year = 2024
)
SELECT 
  json_extract_string(json_extract(arr, '$[' || i || ']'), '$.owner') AS "Owner",
  json_extract(json_extract(arr, '$[' || i || ']'), '$.total_value')::BIGINT AS "Total Value",
  json_extract(json_extract(arr, '$[' || i || ']'), '$.properties')::INTEGER AS "Properties",
  json_extract_string(json_extract(arr, '$[' || i || ']'), '$.entity_type') AS "Type"
FROM owners, generate_series(0, 24) AS t(i)
WHERE json_extract(arr, '$[' || i || ']') IS NOT NULL
ORDER BY "Total Value" DESC`
  },
  {
    name: 'Tax Summary',
    description: 'Overall property tax statistics',
    category: 'property',
    sql: `-- Property tax summary
SELECT * FROM tax_summary`
  },

  // Government
  {
    name: 'County Budget Trends',
    description: 'Frederick County budget by year (FY2020-FY2025)',
    category: 'government',
    sql: `-- County government budget trends
SELECT 
  fiscal_year AS "Year",
  total_budget_net / 1e6 AS "Total Budget (M)",
  general_fund_total / 1e6 AS "General Fund (M)",
  school_to_operating / 1e6 AS "School Operating (M)",
  tax_real_estate_per_100 AS "RE Tax Rate"
FROM county_govt_time_series
ORDER BY fiscal_year`
  },
  {
    name: 'Budget by Category',
    description: 'Spending breakdown by category and year',
    category: 'government',
    sql: `-- Budget expenditures by category
SELECT 
  fiscal_year AS "Year",
  category AS "Category",
  adopted / 1e6 AS "Adopted (M)",
  prior_actual / 1e6 AS "Prior Actual (M)"
FROM county_govt_budget_detail
WHERE category NOT IN ('total')
ORDER BY fiscal_year, adopted DESC`
  },
  {
    name: 'APA Education Comparison',
    description: 'Education spending by district (APA data)',
    category: 'government',
    sql: `-- APA education expenditures by division
SELECT 
  division_name AS "District",
  exp_instruction / 1e6 AS "Instruction (M)",
  exp_admin_attendance_health / 1e6 AS "Admin (M)",
  exp_total / 1e6 AS "Total (M)",
  pct_state_avg_instruction AS "% of State Avg"
FROM apa_education_by_division
WHERE exp_total > 0
ORDER BY exp_total DESC`
  },
  {
    name: 'Local Revenue Sources',
    description: 'Property taxes and other local revenue (APA Exhibit B)',
    category: 'government',
    sql: `-- Local revenue by locality (APA Exhibit B)
SELECT 
  locality AS "Locality",
  total_general_property_taxes / 1e6 AS "Property Tax (M)",
  total_local_revenue / 1e6 AS "Total Revenue (M)",
  population AS "Population",
  per_capita AS "Per Capita"
FROM apa_exhibit_b
WHERE population > 0
ORDER BY total_local_revenue DESC`
  },
  {
    name: 'State & Federal Aid',
    description: 'Commonwealth and federal aid by locality (APA Exhibit B1)',
    category: 'government',
    sql: `-- State and federal aid (APA Exhibit B1)
SELECT 
  locality AS "Locality",
  total_from_the_commonwealth / 1e6 AS "State Aid (M)",
  total_from_the_federal_government / 1e6 AS "Federal Aid (M)",
  categorical_state_aid / 1e6 AS "State Categorical (M)"
FROM apa_exhibit_b1
WHERE total_from_the_commonwealth > 0
ORDER BY total_from_the_commonwealth DESC`
  },

  // GIS / Map Queries - TODO: Add GIS parquet files to data engine
  // GIS data is available in data/processed/gis/ but not yet integrated
];

// ============================================================================
// Application State
// ============================================================================

interface AppState {
  status: 'loading' | 'ready' | 'error';
  error?: string;
  viewMode: 'table' | 'chart' | 'map';
  chartType: ChartType;
  lastResult: QueryResult | null;
  lastQuery: string;
  mapColorProperty: string;
  mapColorRamp: keyof typeof COLOR_RAMPS;
}

const state: AppState = {
  status: 'loading',
  viewMode: 'table',
  chartType: 'bar',
  lastResult: null,
  lastQuery: '',
  mapColorProperty: 'total_value',
  mapColorRamp: 'blues',
};

// ============================================================================
// Initialization
// ============================================================================

async function init(): Promise<void> {
  const app = document.getElementById('app');
  if (!app) throw new Error('App container not found');

  try {
    console.log('[Playground] Initializing...');
    await initDataEngine();
    await editorEngine.init(getSchemaForAutocomplete);
    
    state.status = 'ready';
    render(app);
    console.log('[Playground] Ready');
  } catch (error) {
    console.error('[Playground] Initialization failed:', error);
    state.status = 'error';
    state.error = error instanceof Error ? error.message : String(error);
    render(app);
  }
}

async function getSchemaForAutocomplete(): Promise<{ tables: { name: string; columns: { name: string; type: string }[] }[] }> {
  try {
    const tableNames = await getLoadedTables();
    const tables = await Promise.all(
      tableNames.map(async (name) => {
        try {
          const columns = await getTableSchema(name);
          return { name, columns };
        } catch {
          return { name, columns: [] };
        }
      })
    );
    return { tables };
  } catch {
    return { tables: [] };
  }
}

// ============================================================================
// Rendering
// ============================================================================

function render(container: HTMLElement): void {
  switch (state.status) {
    case 'loading':
      container.innerHTML = `
        <div class="loading">
          <div class="loading-spinner"></div>
          <div>Loading Data Playground...</div>
          <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.5rem;">
            Initializing DuckDB and loading data files...
          </div>
        </div>
      `;
      break;

    case 'error':
      container.innerHTML = `
        <div class="loading">
          <div style="color: var(--accent); font-size: 1.2rem;">Failed to Load</div>
          <div style="color: var(--text-secondary); font-size: 0.9rem; margin: 1rem 0;">${state.error}</div>
          <button onclick="location.reload()" style="padding: 0.5rem 1rem; cursor: pointer; background: var(--accent); color: white; border: none; border-radius: 4px;">
            Try Again
          </button>
        </div>
      `;
      break;

    case 'ready':
      container.innerHTML = `
        <header class="header">
          <div class="header-left">
            <h1>Open Frederick Data Playground</h1>
            <span class="header-subtitle">Explore Frederick County, VA public data with SQL</span>
          </div>
          <div class="header-right">
            <span id="cache-status" class="status-badge" title="Data cache status">Loading...</span>
            <span class="status-badge status-ready">Ready</span>
          </div>
        </header>
        
        <main class="main-content">
          <aside class="sidebar">
            <div class="sidebar-section">
              <h3>Quick Queries</h3>
              <p class="sidebar-hint">Click to load a pre-built analysis</p>
              <div id="query-templates"></div>
            </div>
            
            <div class="sidebar-section">
              <h3>Data Tables</h3>
              <p class="sidebar-hint">Click to explore table contents</p>
              <div id="data-list">Loading...</div>
            </div>
          </aside>
          
          <section class="editor-section">
            <div class="query-panel">
              <div id="monaco-container" class="editor-container"></div>
              <div class="query-controls">
                <button id="run-btn" class="btn btn-primary">
                  Run Query
                  <span class="shortcut">Ctrl+Enter</span>
                </button>
                <button id="share-btn" class="btn btn-secondary" title="Copy shareable link">
                  Share
                </button>
                <div class="view-toggle">
                  <button id="view-table-btn" class="btn btn-toggle active">Table</button>
                  <button id="view-chart-btn" class="btn btn-toggle">Chart</button>
                  <button id="view-map-btn" class="btn btn-toggle">Map</button>
                </div>
              </div>
              <div id="share-toast" class="share-toast">Link copied to clipboard!</div>
            </div>
            
            <div id="chart-controls" class="chart-controls" style="display: none;">
              <label class="chart-select-label">
                Chart Type:
                <select id="chart-type-select" class="chart-select">
                  <option value="bar">Bar Chart</option>
                  <option value="line">Line Chart</option>
                  <option value="pie">Pie Chart</option>
                  <option value="doughnut">Doughnut</option>
                  <option value="scatter">Scatter Plot</option>
                </select>
              </label>
              <button id="download-chart-btn" class="btn btn-secondary">Download PNG</button>
              <span class="chart-hint">First column = labels, other columns = data series</span>
            </div>
            
            <div id="map-controls" class="map-controls" style="display: none;">
              <label class="map-select-label">
                Color By:
                <select id="map-color-property" class="map-select">
                  <option value="">None (uniform)</option>
                  <option value="total_value">Total Value</option>
                  <option value="land_value">Land Value</option>
                  <option value="acreage">Acreage</option>
                  <option value="tax_amount">Tax Amount</option>
                </select>
              </label>
              <label class="map-select-label">
                Color Ramp:
                <select id="map-color-ramp" class="map-select">
                  <option value="blues">Blues</option>
                  <option value="greens">Greens</option>
                  <option value="reds">Reds</option>
                  <option value="purples">Purples</option>
                  <option value="value">Value (Yellow-Blue)</option>
                </select>
              </label>
              <button id="zoom-county-btn" class="btn btn-secondary">Zoom to County</button>
              <span class="map-hint">Query must include a 'geometry' column for map display</span>
            </div>
            
            <div class="results-panel">
              <div id="results" class="results-container">
                <div class="results-placeholder">
                  <p>Select a query template or write your own SQL above</p>
                  <p class="hint">Press Ctrl+Enter or click "Run Query" to execute</p>
                </div>
              </div>
            </div>
          </section>
        </main>
      `;
      addStyles();
      setupUI();
      break;
  }
}

function addStyles(): void {
  if (document.getElementById('playground-styles')) return;
  
  const style = document.createElement('style');
  style.id = 'playground-styles';
  style.textContent = `
    .header {
      padding: 0.75rem 1rem;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: var(--bg-secondary);
    }
    .header-left { display: flex; align-items: baseline; gap: 1rem; }
    .header h1 { margin: 0; font-size: 1.1rem; font-weight: 600; }
    .header-subtitle { font-size: 0.8rem; color: var(--text-secondary); }
    .header-right { display: flex; gap: 0.75rem; align-items: center; }
    
    .status-badge {
      font-size: 0.7rem;
      padding: 0.2rem 0.5rem;
      border-radius: 3px;
      background: var(--bg-tertiary);
      color: var(--text-secondary);
      cursor: default;
    }
    .status-ready { background: rgba(0, 217, 255, 0.15); color: var(--success); }
    .status-cached { background: rgba(0, 217, 255, 0.15); color: var(--success); cursor: pointer; }
    
    .main-content {
      flex: 1;
      display: flex;
      min-height: 0;
      overflow: hidden;
    }
    
    .sidebar {
      width: 280px;
      border-right: 1px solid var(--border);
      overflow-y: auto;
      background: var(--bg-secondary);
      height: 100%;
    }
    
    .editor-section {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-width: 0;
      height: 100%;
      overflow: hidden;
    }
    .sidebar-section {
      padding: 1rem;
      border-bottom: 1px solid var(--border);
    }
    .sidebar-section h3 {
      margin: 0 0 0.25rem 0;
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--text-primary);
    }
    .sidebar-hint {
      margin: 0 0 0.75rem 0;
      font-size: 0.7rem;
      color: var(--text-secondary);
    }
    
    .template-category {
      margin-bottom: 0.75rem;
    }
    .template-category-title {
      font-size: 0.7rem;
      font-weight: 600;
      text-transform: uppercase;
      color: var(--text-secondary);
      margin-bottom: 0.25rem;
      padding-left: 0.25rem;
    }
    .template-item {
      padding: 0.4rem 0.5rem;
      cursor: pointer;
      border-radius: 4px;
      margin-bottom: 2px;
      font-size: 0.8rem;
      transition: background 0.15s, border-color 0.15s;
      border-left: 3px solid transparent;
    }
    .template-item:hover {
      background: var(--bg-tertiary);
    }
    .template-item.active {
      background: rgba(0, 217, 255, 0.1);
      border-left-color: var(--accent);
    }
    .template-item .template-name {
      color: var(--text-primary);
    }
    .template-item.active .template-name {
      color: var(--accent);
    }
    .template-item .template-desc {
      font-size: 0.7rem;
      color: var(--text-secondary);
      margin-top: 2px;
    }
    
    .table-item {
      padding: 0.3rem 0.5rem;
      cursor: pointer;
      border-radius: 4px;
      font-size: 0.75rem;
      font-family: monospace;
      transition: background 0.15s;
    }
    .table-item:hover {
      background: var(--bg-tertiary);
    }
    .table-item::before {
      content: '\\25A0';
      color: var(--accent);
      margin-right: 0.4rem;
      font-size: 0.6rem;
    }
    
    .query-panel {
      padding: 0.75rem 1rem;
      border-bottom: 1px solid var(--border);
    }
    .editor-container {
      height: 140px;
      border: 1px solid var(--border);
      border-radius: 4px;
      overflow: hidden;
    }
    .query-controls {
      display: flex;
      gap: 0.5rem;
      margin-top: 0.5rem;
      align-items: center;
    }
    
    .btn {
      padding: 0.4rem 0.75rem;
      border: 1px solid var(--border);
      border-radius: 4px;
      cursor: pointer;
      font-size: 0.8rem;
      transition: all 0.15s;
    }
    .btn-primary {
      background: var(--accent);
      color: white;
      border-color: var(--accent);
    }
    .btn-primary:hover {
      filter: brightness(1.1);
    }
    .btn-secondary {
      background: var(--bg-secondary);
      color: var(--text-primary);
    }
    .btn-secondary:hover {
      background: var(--bg-tertiary);
    }
    .btn .shortcut {
      font-size: 0.65rem;
      opacity: 0.7;
      margin-left: 0.5rem;
    }
    
    .view-toggle {
      display: flex;
      margin-left: auto;
    }
    .btn-toggle {
      background: var(--bg-secondary);
      color: var(--text-secondary);
      border-radius: 0;
    }
    .btn-toggle:first-child {
      border-radius: 4px 0 0 4px;
    }
    .btn-toggle:last-child {
      border-radius: 0 4px 4px 0;
      border-left: none;
    }
    .btn-toggle.active {
      background: var(--bg-tertiary);
      color: var(--text-primary);
    }
    
    .chart-controls {
      padding: 0.5rem 1rem;
      background: var(--bg-secondary);
      border-bottom: 1px solid var(--border);
      display: flex;
      gap: 1rem;
      align-items: center;
      font-size: 0.8rem;
    }
    .chart-select-label {
      color: var(--text-secondary);
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .chart-select {
      padding: 0.25rem 0.5rem;
      background: var(--bg-primary);
      color: var(--text-primary);
      border: 1px solid var(--border);
      border-radius: 4px;
    }
    .chart-hint {
      color: var(--text-secondary);
      font-size: 0.7rem;
      font-style: italic;
      margin-left: auto;
    }
    
    .results-panel {
      flex: 1;
      padding: 1rem;
      overflow: auto;
      min-height: 0;
    }
    .results-container {
      height: 100%;
    }
    .results-placeholder {
      text-align: center;
      padding: 3rem 1rem;
      color: var(--text-secondary);
    }
    .results-placeholder p {
      margin: 0.5rem 0;
    }
    .results-placeholder .hint {
      font-size: 0.8rem;
      opacity: 0.7;
    }
    
    /* Share toast notification */
    .share-toast {
      position: fixed;
      bottom: 2rem;
      left: 50%;
      transform: translateX(-50%) translateY(100px);
      background: var(--success);
      color: #000;
      padding: 0.75rem 1.5rem;
      border-radius: 6px;
      font-size: 0.85rem;
      font-weight: 500;
      opacity: 0;
      transition: transform 0.3s ease, opacity 0.3s ease;
      z-index: 1000;
      pointer-events: none;
    }
    .share-toast.show {
      transform: translateX(-50%) translateY(0);
      opacity: 1;
    }
  `;
  document.head.appendChild(style);
}

// ============================================================================
// UI Setup
// ============================================================================

function setupUI(): void {
  // Check for shared query in URL
  const sharedState = loadFromUrlHash();
  
  // Default SQL if no shared query
  const defaultSQL = `-- Welcome to Open Frederick Data Playground!
-- Select a Quick Query from the sidebar, or write your own SQL.
-- Press Ctrl+Enter to run.

-- Example: County budget to schools over time
SELECT 
  fiscal_year,
  county_transfers_total_county_to_schools AS to_schools,
  county_transfers_pct_of_general_fund AS pct_of_budget
FROM county_budget_schools
ORDER BY fiscal_year`;

  // Initialize Monaco editor
  editorEngine.createEditor('monaco-container', sharedState?.q || defaultSQL);
  
  // Apply shared view mode if present
  if (sharedState?.t) {
    if (sharedState.t === 'table') {
      state.viewMode = 'table';
    } else {
      state.viewMode = 'chart';
      state.chartType = sharedState.t as ChartType;
    }
  }
  
  editorEngine.onExecute(runQuery);
  editorEngine.onChange(highlightMatchingTemplate);
  
  setupEventListeners();
  renderQueryTemplates();
  loadDataFileList();
  updateCacheStatus();
  
  // Update UI to reflect loaded state
  updateViewMode();
  
  // If we loaded a shared query, run it automatically
  if (sharedState?.q) {
    highlightMatchingTemplate(sharedState.q);
    // Small delay to ensure UI is ready
    setTimeout(() => {
      runQuery(sharedState.q);
    }, 100);
  }
}

/**
 * Normalize SQL for comparison (remove extra whitespace, lowercase)
 */
function normalizeSQL(sql: string): string {
  return sql.trim().replace(/\s+/g, ' ').toLowerCase();
}

/**
 * Highlight the sidebar template that matches the current editor content
 */
function highlightMatchingTemplate(sql: string): void {
  const normalizedCurrent = normalizeSQL(sql);
  const container = document.getElementById('query-templates');
  if (!container) return;

  // Remove all active states
  container.querySelectorAll('.template-item.active').forEach(el => {
    el.classList.remove('active');
  });

  // Find and highlight matching template
  container.querySelectorAll('.template-item').forEach(el => {
    const templateSQL = decodeURIComponent(el.getAttribute('data-sql') || '');
    if (normalizeSQL(templateSQL) === normalizedCurrent) {
      el.classList.add('active');
      // Scroll into view if needed
      el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  });
}

function renderQueryTemplates(): void {
  const container = document.getElementById('query-templates');
  if (!container) return;

  const categories: Record<string, string> = {
    budget: 'County Budget',
    schools: 'Schools',
    property: 'Property Tax',
    government: 'Government Data',
  };

  const byCategory = QUERY_TEMPLATES.reduce((acc, t) => {
    if (!acc[t.category]) acc[t.category] = [];
    acc[t.category].push(t);
    return acc;
  }, {} as Record<string, QueryTemplate[]>);

  container.innerHTML = Object.entries(byCategory).map(([cat, templates]) => `
    <div class="template-category">
      <div class="template-category-title">${categories[cat] || cat}</div>
      ${templates.map(t => `
        <div class="template-item" data-sql="${encodeURIComponent(t.sql)}" title="${t.description}">
          <div class="template-name">${t.name}</div>
          <div class="template-desc">${t.description}</div>
        </div>
      `).join('')}
    </div>
  `).join('');

  // Add click handlers
  container.querySelectorAll('.template-item').forEach(el => {
    el.addEventListener('click', () => {
      const sql = decodeURIComponent(el.getAttribute('data-sql') || '');
      editorEngine.setValue(sql);
      editorEngine.focus();
      highlightMatchingTemplate(sql); // Immediately highlight
      runQuery(sql);
    });
  });
}

async function loadDataFileList(): Promise<void> {
  const dataList = document.getElementById('data-list');
  if (!dataList) return;

  try {
    const tables = await getLoadedTables();
    
    if (tables.length === 0) {
      dataList.innerHTML = '<em style="color: var(--text-secondary);">No data loaded</em>';
    } else {
      dataList.innerHTML = tables.map(t => `
        <div class="table-item" data-table="${t}">${t}</div>
      `).join('');

      dataList.querySelectorAll('.table-item').forEach(el => {
        el.addEventListener('click', () => {
          const tableName = el.getAttribute('data-table');
          editorEngine.setValue(`SELECT * FROM ${tableName} LIMIT 100`);
          editorEngine.focus();
        });
      });
    }
  } catch {
    dataList.innerHTML = '<em style="color: var(--text-secondary);">Failed to load tables</em>';
  }
}

async function updateCacheStatus(): Promise<void> {
  const cacheStatus = document.getElementById('cache-status');
  if (!cacheStatus) return;

  try {
    const stats = await getCacheStats();
    const quota = await getStorageQuota();
    
    if (stats.fileCount > 0) {
      const sizeMB = (stats.totalSize / 1024 / 1024).toFixed(1);
      cacheStatus.textContent = `Cached: ${sizeMB} MB`;
      cacheStatus.className = 'status-badge status-cached';
      cacheStatus.title = `${stats.fileCount} files cached (${sizeMB} MB). Click to manage.`;
    } else {
      cacheStatus.textContent = 'Not cached';
      cacheStatus.title = 'Data will be cached after first query';
    }

    cacheStatus.onclick = async () => {
      const action = confirm(
        `Cache: ${stats.fileCount} files (${(stats.totalSize / 1024 / 1024).toFixed(1)} MB)\n` +
        `Storage: ${quota.usagePercent?.toFixed(0) ?? '?'}% used\n\n` +
        `Clear cache?`
      );
      if (action) {
        await clearCache();
        updateCacheStatus();
      }
    };
  } catch {
    cacheStatus.textContent = 'Cache unavailable';
  }
}

function setupEventListeners(): void {
  const runBtn = document.getElementById('run-btn');
  const shareBtn = document.getElementById('share-btn');
  const shareToast = document.getElementById('share-toast');
  const viewTableBtn = document.getElementById('view-table-btn');
  const viewChartBtn = document.getElementById('view-chart-btn');
  const chartTypeSelect = document.getElementById('chart-type-select') as HTMLSelectElement;
  const downloadChartBtn = document.getElementById('download-chart-btn');

  runBtn?.addEventListener('click', () => runQuery(editorEngine.getValue()));

  // Share button - copy link to clipboard
  shareBtn?.addEventListener('click', async () => {
    const url = generateShareUrl();
    const success = await copyToClipboard(url);
    
    if (success && shareToast) {
      // Show toast notification
      shareToast.classList.add('show');
      setTimeout(() => {
        shareToast.classList.remove('show');
      }, 2500);
    } else {
      // Fallback: show URL in prompt
      prompt('Copy this shareable link:', url);
    }
  });

  viewTableBtn?.addEventListener('click', () => {
    state.viewMode = 'table';
    updateViewMode();
    if (state.lastResult) displayResults(state.lastResult);
  });

  viewChartBtn?.addEventListener('click', () => {
    state.viewMode = 'chart';
    updateViewMode();
    if (state.lastResult) displayResults(state.lastResult);
  });

  chartTypeSelect?.addEventListener('change', () => {
    state.chartType = chartTypeSelect.value as ChartType;
    if (state.viewMode === 'chart' && state.lastResult) {
      displayChart(state.lastResult);
    }
  });

  downloadChartBtn?.addEventListener('click', () => {
    getChartEngine().downloadAsPng('chart-container', `fcps-chart-${Date.now()}.png`);
  });
}

function updateViewMode(): void {
  const tableBtn = document.getElementById('view-table-btn');
  const chartBtn = document.getElementById('view-chart-btn');
  const chartControls = document.getElementById('chart-controls');
  const chartTypeSelect = document.getElementById('chart-type-select') as HTMLSelectElement | null;

  tableBtn?.classList.toggle('active', state.viewMode === 'table');
  chartBtn?.classList.toggle('active', state.viewMode === 'chart');
  if (chartControls) {
    chartControls.style.display = state.viewMode === 'chart' ? 'flex' : 'none';
  }
  // Sync chart type select with state
  if (chartTypeSelect && chartTypeSelect.value !== state.chartType) {
    chartTypeSelect.value = state.chartType;
  }
}

// ============================================================================
// Query Execution & Results
// ============================================================================

async function runQuery(sql: string): Promise<void> {
  const query = sql.trim();
  if (!query) return;

  state.lastQuery = query;
  const results = document.getElementById('results');
  if (results) {
    results.innerHTML = '<div class="results-placeholder"><p>Running query...</p></div>';
  }

  try {
    const result = await executeQuery(query);
    state.lastResult = result;
    displayResults(result);
  } catch (error) {
    state.lastResult = null;
    if (results) {
      results.innerHTML = `
        <div style="color: var(--accent); padding: 1rem;">
          <strong>Query Error</strong>
          <pre style="margin-top: 0.5rem; font-size: 0.85rem; white-space: pre-wrap;">${
            error instanceof Error ? error.message : String(error)
          }</pre>
        </div>
      `;
    }
  }
}

function displayResults(result: QueryResult): void {
  if (state.viewMode === 'table') {
    displayTable(result);
  } else {
    displayChart(result);
  }
}

function displayTable(result: QueryResult): void {
  const container = document.getElementById('results');
  if (!container) return;

  getChartEngine().destroyChart('chart-container');

  if (result.rows.length === 0) {
    container.innerHTML = '<div class="results-placeholder"><p>Query returned no results</p></div>';
    return;
  }

  const headerHtml = result.columns.map(col => 
    `<th style="padding: 0.5rem; text-align: left; border-bottom: 2px solid var(--border); background: var(--bg-secondary); position: sticky; top: 0; font-weight: 600;">${escapeHtml(col)}</th>`
  ).join('');
  
  const rowsHtml = result.rows.slice(0, 1000).map(row => 
    `<tr>${row.map(cell => 
      `<td style="padding: 0.4rem 0.5rem; border-bottom: 1px solid var(--border);">${escapeHtml(formatCell(cell))}</td>`
    ).join('')}</tr>`
  ).join('');

  container.innerHTML = `
    <div style="margin-bottom: 0.5rem; color: var(--text-secondary); font-size: 0.8rem;">
      ${result.rowCount.toLocaleString()} row${result.rowCount !== 1 ? 's' : ''} 
      <span style="opacity: 0.7;">| ${result.executionTimeMs.toFixed(1)}ms</span>
      ${result.rows.length > 1000 ? ' | Showing first 1,000' : ''}
    </div>
    <div style="overflow: auto; max-height: calc(100% - 2rem);">
      <table style="width: 100%; border-collapse: collapse; font-size: 0.8rem;">
        <thead><tr>${headerHtml}</tr></thead>
        <tbody>${rowsHtml}</tbody>
      </table>
    </div>
  `;
}

function displayChart(result: QueryResult): void {
  const container = document.getElementById('results');
  if (!container) return;

  if (result.rows.length === 0) {
    container.innerHTML = '<div class="results-placeholder"><p>Query returned no results</p></div>';
    return;
  }

  container.innerHTML = `
    <div style="margin-bottom: 0.5rem; color: var(--text-secondary); font-size: 0.8rem;">
      ${result.rowCount.toLocaleString()} row${result.rowCount !== 1 ? 's' : ''}
      <span style="opacity: 0.7;">| ${result.executionTimeMs.toFixed(1)}ms</span>
    </div>
    <div id="chart-container" style="height: calc(100% - 2rem); min-height: 300px;"></div>
  `;

  const options: ChartOptions = {
    showLegend: result.columns.length > 2 || ['pie', 'doughnut'].includes(state.chartType),
    beginAtZero: true,
  };

  getChartEngine().renderChart('chart-container', state.chartType, result, options);
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return 'NULL';
  if (typeof value === 'number') {
    if (Number.isInteger(value) && Math.abs(value) >= 1000) {
      return value.toLocaleString();
    }
    if (!Number.isInteger(value)) {
      return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }
  }
  return String(value);
}

function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ============================================================================
// Start Application
// ============================================================================

init();
