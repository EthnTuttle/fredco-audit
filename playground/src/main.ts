/**
 * FCPS Data Playground v2
 * 
 * Entry point for the data playground application.
 * Initializes DuckDB-WASM and sets up the notebook interface with chart support.
 */

import { initDataEngine, executeQuery, getLoadedTables, type QueryResult } from './engines/data';
import { getChartEngine, type ChartType, type ChartOptions } from './engines/chart';

// Application state
interface AppState {
  status: 'loading' | 'ready' | 'error';
  error?: string;
  viewMode: 'table' | 'chart';
  chartType: ChartType;
  lastResult: QueryResult | null;
}

const state: AppState = {
  status: 'loading',
  viewMode: 'table',
  chartType: 'bar',
  lastResult: null,
};

/**
 * Initialize the application
 */
async function init(): Promise<void> {
  const app = document.getElementById('app');
  if (!app) throw new Error('App container not found');

  try {
    // Initialize DuckDB-WASM data engine
    console.log('[Playground] Initializing data engine...');
    await initDataEngine();
    console.log('[Playground] Data engine ready');

    state.status = 'ready';
    render(app);
  } catch (error) {
    console.error('[Playground] Initialization failed:', error);
    state.status = 'error';
    state.error = error instanceof Error ? error.message : String(error);
    render(app);
  }
}

/**
 * Render the application
 */
function render(container: HTMLElement): void {
  switch (state.status) {
    case 'loading':
      container.innerHTML = `
        <div class="loading">
          <div class="loading-spinner"></div>
          <div>Loading Data Playground...</div>
        </div>
      `;
      break;

    case 'error':
      container.innerHTML = `
        <div class="loading">
          <div style="color: var(--accent);">Initialization Error</div>
          <div style="color: var(--text-secondary); font-size: 0.9rem;">${state.error}</div>
          <button onclick="location.reload()" style="margin-top: 1rem; padding: 0.5rem 1rem; cursor: pointer;">
            Retry
          </button>
        </div>
      `;
      break;

    case 'ready':
      container.innerHTML = `
        <header style="padding: 1rem; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
          <h1 style="margin: 0; font-size: 1.2rem;">FCPS Data Playground v2</h1>
          <div style="font-size: 0.8rem; color: var(--success);">DuckDB Ready</div>
        </header>
        <main style="flex: 1; display: flex; min-height: 0;">
          <aside id="sidebar" style="width: 250px; border-right: 1px solid var(--border); padding: 1rem; overflow-y: auto;">
            <h3 style="margin-top: 0;">Data Files</h3>
            <div id="data-list" style="font-size: 0.85rem;">Loading...</div>
          </aside>
          <section id="editor" style="flex: 1; display: flex; flex-direction: column; min-width: 0;">
            <div id="query-panel" style="padding: 1rem; border-bottom: 1px solid var(--border);">
              <div class="cell">
                <textarea id="sql-input" placeholder="Enter SQL query... (e.g., SELECT division_name, total_per_pupil FROM vdoe_table15_expenditures WHERE fiscal_year = '2023-24' ORDER BY total_per_pupil DESC)" style="width: 100%; min-height: 80px; background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border); padding: 0.5rem; font-family: 'Fira Code', monospace; font-size: 0.9rem; resize: vertical; box-sizing: border-box;"></textarea>
                <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem; flex-wrap: wrap; align-items: center;">
                  <button id="run-btn" style="padding: 0.5rem 1rem; background: var(--accent); color: white; border: none; cursor: pointer; border-radius: 4px;">
                    Run Query (Ctrl+Enter)
                  </button>
                  <div style="display: flex; align-items: center; gap: 0.5rem; margin-left: auto;">
                    <span style="color: var(--text-secondary); font-size: 0.85rem;">View:</span>
                    <button id="view-table-btn" class="view-btn active" style="padding: 0.4rem 0.75rem; background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border); cursor: pointer; border-radius: 4px 0 0 4px;">
                      Table
                    </button>
                    <button id="view-chart-btn" class="view-btn" style="padding: 0.4rem 0.75rem; background: var(--bg-secondary); color: var(--text-secondary); border: 1px solid var(--border); border-left: none; cursor: pointer; border-radius: 0 4px 4px 0;">
                      Chart
                    </button>
                  </div>
                </div>
              </div>
            </div>
            <div id="chart-controls" style="display: none; padding: 0.75rem 1rem; background: var(--bg-secondary); border-bottom: 1px solid var(--border);">
              <div style="display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;">
                <label style="display: flex; align-items: center; gap: 0.5rem; color: var(--text-secondary); font-size: 0.85rem;">
                  Chart Type:
                  <select id="chart-type-select" style="padding: 0.3rem 0.5rem; background: var(--bg-primary); color: var(--text-primary); border: 1px solid var(--border); border-radius: 4px;">
                    <option value="bar">Bar</option>
                    <option value="line">Line</option>
                    <option value="pie">Pie</option>
                    <option value="scatter">Scatter</option>
                    <option value="doughnut">Doughnut</option>
                    <option value="radar">Radar</option>
                    <option value="polarArea">Polar Area</option>
                  </select>
                </label>
                <button id="download-chart-btn" style="padding: 0.4rem 0.75rem; background: var(--bg-primary); color: var(--text-primary); border: 1px solid var(--border); cursor: pointer; border-radius: 4px; font-size: 0.85rem;">
                  Download PNG
                </button>
                <span id="chart-hint" style="color: var(--text-secondary); font-size: 0.8rem; font-style: italic;">
                  Tip: First column = labels, remaining columns = data series
                </span>
              </div>
            </div>
            <div id="results-panel" style="flex: 1; padding: 1rem; overflow: auto; min-height: 0;">
              <div id="results" style="height: 100%;">
                <em style="color: var(--text-secondary);">Results will appear here</em>
              </div>
            </div>
          </section>
        </main>
      `;
      setupEventListeners();
      loadDataFileList();
      break;
  }
}

/**
 * Set up event listeners
 */
function setupEventListeners(): void {
  const runBtn = document.getElementById('run-btn');
  const sqlInput = document.getElementById('sql-input') as HTMLTextAreaElement;
  const viewTableBtn = document.getElementById('view-table-btn');
  const viewChartBtn = document.getElementById('view-chart-btn');
  const chartTypeSelect = document.getElementById('chart-type-select') as HTMLSelectElement;
  const downloadChartBtn = document.getElementById('download-chart-btn');

  // Run query
  runBtn?.addEventListener('click', runQuery);

  // Ctrl+Enter to run
  sqlInput?.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      runQuery();
    }
  });

  // View mode toggle
  viewTableBtn?.addEventListener('click', () => {
    state.viewMode = 'table';
    updateViewModeUI();
    if (state.lastResult) {
      displayResults(state.lastResult);
    }
  });

  viewChartBtn?.addEventListener('click', () => {
    state.viewMode = 'chart';
    updateViewModeUI();
    if (state.lastResult) {
      displayResults(state.lastResult);
    }
  });

  // Chart type change
  chartTypeSelect?.addEventListener('change', () => {
    state.chartType = chartTypeSelect.value as ChartType;
    if (state.viewMode === 'chart' && state.lastResult) {
      displayChart(state.lastResult);
    }
  });

  // Download chart
  downloadChartBtn?.addEventListener('click', () => {
    const engine = getChartEngine();
    engine.downloadAsPng('chart-container', `fcps-chart-${Date.now()}.png`);
  });
}

/**
 * Update view mode UI
 */
function updateViewModeUI(): void {
  const viewTableBtn = document.getElementById('view-table-btn');
  const viewChartBtn = document.getElementById('view-chart-btn');
  const chartControls = document.getElementById('chart-controls');

  if (state.viewMode === 'table') {
    viewTableBtn?.classList.add('active');
    viewTableBtn!.style.color = 'var(--text-primary)';
    viewChartBtn?.classList.remove('active');
    viewChartBtn!.style.color = 'var(--text-secondary)';
    if (chartControls) chartControls.style.display = 'none';
  } else {
    viewTableBtn?.classList.remove('active');
    viewTableBtn!.style.color = 'var(--text-secondary)';
    viewChartBtn?.classList.add('active');
    viewChartBtn!.style.color = 'var(--text-primary)';
    if (chartControls) chartControls.style.display = 'block';
  }
}

/**
 * Run the SQL query
 */
async function runQuery(): Promise<void> {
  const sqlInput = document.getElementById('sql-input') as HTMLTextAreaElement;
  const query = sqlInput?.value.trim();
  if (!query) return;

  const results = document.getElementById('results');
  if (results) {
    results.innerHTML = '<em style="color: var(--text-secondary);">Running query...</em>';
  }

  try {
    const result = await executeQuery(query);
    state.lastResult = result;
    displayResults(result);
  } catch (error) {
    state.lastResult = null;
    if (results) {
      results.innerHTML = `<div style="color: var(--accent);">Error: ${error instanceof Error ? error.message : String(error)}</div>`;
    }
  }
}

/**
 * Display results based on current view mode
 */
function displayResults(result: QueryResult): void {
  if (state.viewMode === 'table') {
    displayTable(result);
  } else {
    displayChart(result);
  }
}

/**
 * Display results as a table
 */
function displayTable(result: QueryResult): void {
  const results = document.getElementById('results');
  if (!results) return;

  // Destroy any existing chart
  getChartEngine().destroyChart('chart-container');

  if (result.rows.length === 0) {
    results.innerHTML = '<em style="color: var(--text-secondary);">Query returned no results</em>';
    return;
  }

  results.innerHTML = renderTable(result.columns, result.rows, result.executionTimeMs);
}

/**
 * Display results as a chart
 */
function displayChart(result: QueryResult): void {
  const results = document.getElementById('results');
  if (!results) return;

  if (result.rows.length === 0) {
    results.innerHTML = '<em style="color: var(--text-secondary);">Query returned no results</em>';
    return;
  }

  // Create chart container
  results.innerHTML = `
    <div style="margin-bottom: 0.5rem; color: var(--text-secondary); font-size: 0.85rem;">
      ${result.rowCount} row(s) | ${result.executionTimeMs.toFixed(1)}ms
    </div>
    <div id="chart-container" style="height: calc(100% - 2rem); min-height: 300px; position: relative;"></div>
  `;

  // Render chart
  const engine = getChartEngine();
  const options: ChartOptions = {
    showLegend: result.columns.length > 2 || state.chartType === 'pie' || state.chartType === 'doughnut',
    beginAtZero: true,
  };

  engine.renderChart('chart-container', state.chartType, result, options);
}

/**
 * Render a table from query results
 */
function renderTable(columns: string[], rows: unknown[][], executionTimeMs?: number): string {
  if (columns.length === 0) return '<em>No columns</em>';

  const headerHtml = columns.map(col => 
    `<th style="padding: 0.5rem; text-align: left; border-bottom: 2px solid var(--border); background: var(--bg-secondary); position: sticky; top: 0;">${escapeHtml(col)}</th>`
  ).join('');
  
  const rowsHtml = rows.slice(0, 1000).map(row => {
    const cells = row.map(cell => 
      `<td style="padding: 0.5rem; border-bottom: 1px solid var(--border);">${escapeHtml(formatCell(cell))}</td>`
    ).join('');
    return `<tr>${cells}</tr>`;
  }).join('');

  const truncated = rows.length > 1000 
    ? `<div style="margin-top: 0.5rem; color: var(--text-secondary);">Showing 1000 of ${rows.length} rows</div>` 
    : '';

  const timing = executionTimeMs !== undefined
    ? ` | ${executionTimeMs.toFixed(1)}ms`
    : '';

  return `
    <div style="margin-bottom: 0.5rem; color: var(--text-secondary);">${rows.length} row(s)${timing}</div>
    <div style="overflow: auto; max-height: calc(100% - 2rem);">
      <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
        <thead><tr>${headerHtml}</tr></thead>
        <tbody>${rowsHtml}</tbody>
      </table>
    </div>
    ${truncated}
  `;
}

/**
 * Format a cell value for display
 */
function formatCell(value: unknown): string {
  if (value === null || value === undefined) return 'NULL';
  if (typeof value === 'number') {
    // Format large numbers with commas
    if (Number.isInteger(value) && Math.abs(value) >= 1000) {
      return value.toLocaleString();
    }
    // Format decimals to reasonable precision
    if (!Number.isInteger(value)) {
      return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
    }
  }
  return String(value);
}

/**
 * Load and display available data files
 */
async function loadDataFileList(): Promise<void> {
  const dataList = document.getElementById('data-list');
  if (!dataList) return;

  try {
    const tables = await getLoadedTables();
    
    if (tables.length === 0) {
      dataList.innerHTML = '<em style="color: var(--text-secondary);">No data loaded</em>';
    } else {
      dataList.innerHTML = tables.map(t => `
        <div class="table-item" style="padding: 0.4rem 0.5rem; cursor: pointer; border-radius: 4px; margin-bottom: 0.25rem; transition: background 0.15s;" 
             onmouseover="this.style.background='var(--bg-secondary)'" 
             onmouseout="this.style.background='transparent'"
             onclick="document.getElementById('sql-input').value = 'SELECT * FROM ${t} LIMIT 100'; document.getElementById('sql-input').focus();">
          <span style="color: var(--accent);">&#9632;</span> ${t}
        </div>
      `).join('');
    }
  } catch {
    dataList.innerHTML = '<em style="color: var(--text-secondary);">Failed to load tables</em>';
  }
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Start the application
init();
