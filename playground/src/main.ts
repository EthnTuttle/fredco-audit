/**
 * FCPS Data Playground v2
 * 
 * Entry point for the data playground application.
 * Integrates DuckDB-WASM, Chart.js, Monaco editor, and Nostr.
 */

import { initDataEngine, executeQuery, getLoadedTables, getTableSchema, type QueryResult } from './engines/data';
import { getChartEngine, type ChartType, type ChartOptions } from './engines/chart';
import { editorEngine } from './engines/editor';
import { getNotesEngine, isNostrAvailable } from './engines/notes';

// Application state
interface AppState {
  status: 'loading' | 'ready' | 'error';
  error?: string;
  viewMode: 'table' | 'chart';
  chartType: ChartType;
  lastResult: QueryResult | null;
  lastQuery: string;
  nostrConnected: boolean;
}

const state: AppState = {
  status: 'loading',
  viewMode: 'table',
  chartType: 'bar',
  lastResult: null,
  lastQuery: '',
  nostrConnected: false,
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

    // Initialize Monaco editor engine with schema provider
    console.log('[Playground] Initializing editor engine...');
    await editorEngine.init(getSchemaForAutocomplete);
    console.log('[Playground] Editor engine ready');

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
 * Get schema information for autocomplete
 */
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
      const nostrAvailable = isNostrAvailable();
      container.innerHTML = `
        <header style="padding: 1rem; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
          <h1 style="margin: 0; font-size: 1.2rem;">FCPS Data Playground v2</h1>
          <div style="display: flex; gap: 1rem; align-items: center;">
            <span id="nostr-status" style="font-size: 0.75rem; color: ${nostrAvailable ? 'var(--text-secondary)' : 'var(--text-secondary)'};">
              ${nostrAvailable ? 'Nostr: Ready' : 'Nostr: No extension'}
            </span>
            <span style="font-size: 0.8rem; color: var(--success);">DuckDB Ready</span>
          </div>
        </header>
        <main style="flex: 1; display: flex; min-height: 0;">
          <aside id="sidebar" style="width: 250px; border-right: 1px solid var(--border); padding: 1rem; overflow-y: auto;">
            <h3 style="margin-top: 0;">Data Files</h3>
            <div id="data-list" style="font-size: 0.85rem;">Loading...</div>
            ${nostrAvailable ? `
            <div style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid var(--border);">
              <h4 style="margin: 0 0 0.5rem 0; font-size: 0.9rem;">Nostr</h4>
              <button id="nostr-connect-btn" style="width: 100%; padding: 0.4rem; background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border); cursor: pointer; border-radius: 4px; font-size: 0.8rem;">
                Connect
              </button>
              <div id="nostr-pubkey" style="margin-top: 0.5rem; font-size: 0.7rem; word-break: break-all; color: var(--text-secondary);"></div>
            </div>
            ` : ''}
          </aside>
          <section id="editor" style="flex: 1; display: flex; flex-direction: column; min-width: 0;">
            <div id="query-panel" style="padding: 1rem; border-bottom: 1px solid var(--border);">
              <div id="monaco-container" style="height: 120px; border: 1px solid var(--border); border-radius: 4px;"></div>
              <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem; flex-wrap: wrap; align-items: center;">
                <button id="run-btn" style="padding: 0.5rem 1rem; background: var(--accent); color: white; border: none; cursor: pointer; border-radius: 4px;">
                  Run Query (Ctrl+Enter)
                </button>
                ${nostrAvailable ? `
                <button id="publish-btn" style="padding: 0.5rem 1rem; background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border); cursor: pointer; border-radius: 4px;" disabled>
                  Publish to Nostr
                </button>
                ` : ''}
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
      setupUI();
      break;
  }
}

/**
 * Set up UI after render
 */
function setupUI(): void {
  // Create Monaco editor
  editorEngine.createEditor('monaco-container', '-- Enter SQL query here\nSELECT division_name, total_per_pupil \nFROM vdoe_table15_expenditures \nWHERE fiscal_year = \'2023-24\' \nORDER BY total_per_pupil DESC');
  
  // Register Ctrl+Enter handler
  editorEngine.onExecute(runQuery);

  setupEventListeners();
  loadDataFileList();
}

/**
 * Set up event listeners
 */
function setupEventListeners(): void {
  const runBtn = document.getElementById('run-btn');
  const viewTableBtn = document.getElementById('view-table-btn');
  const viewChartBtn = document.getElementById('view-chart-btn');
  const chartTypeSelect = document.getElementById('chart-type-select') as HTMLSelectElement;
  const downloadChartBtn = document.getElementById('download-chart-btn');
  const nostrConnectBtn = document.getElementById('nostr-connect-btn');
  const publishBtn = document.getElementById('publish-btn');

  // Run query
  runBtn?.addEventListener('click', () => runQuery(editorEngine.getValue()));

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

  // Nostr connect
  nostrConnectBtn?.addEventListener('click', async () => {
    try {
      nostrConnectBtn.textContent = 'Connecting...';
      const notesEngine = getNotesEngine();
      await notesEngine.connect();
      await notesEngine.getPublicKey();
      state.nostrConnected = true;
      
      nostrConnectBtn.textContent = 'Connected';
      (nostrConnectBtn as HTMLButtonElement).disabled = true;
      
      const pubkeyDiv = document.getElementById('nostr-pubkey');
      if (pubkeyDiv) {
        const npub = await notesEngine.getPublicKeyBech32();
        pubkeyDiv.textContent = npub.slice(0, 20) + '...' + npub.slice(-8);
      }
      
      const statusSpan = document.getElementById('nostr-status');
      if (statusSpan) {
        statusSpan.textContent = 'Nostr: Connected';
        statusSpan.style.color = 'var(--success)';
      }

      if (publishBtn) {
        publishBtn.removeAttribute('disabled');
      }
    } catch (error) {
      nostrConnectBtn.textContent = 'Connect';
      alert('Failed to connect: ' + (error instanceof Error ? error.message : String(error)));
    }
  });

  // Publish to Nostr
  publishBtn?.addEventListener('click', async () => {
    if (!state.nostrConnected || !state.lastResult) {
      alert('Connect to Nostr and run a query first');
      return;
    }

    const comment = prompt('Add a comment (optional):') || '';
    
    try {
      publishBtn.textContent = 'Publishing...';
      const summary = `${state.lastResult.rowCount} rows in ${state.lastResult.executionTimeMs.toFixed(1)}ms`;
      const result = await getNotesEngine().publishQueryNote(state.lastQuery, summary, comment);
      publishBtn.textContent = 'Published!';
      setTimeout(() => {
        publishBtn.textContent = 'Publish to Nostr';
      }, 2000);
      console.log('Published note:', result.eventId);
    } catch (error) {
      publishBtn.textContent = 'Publish to Nostr';
      alert('Failed to publish: ' + (error instanceof Error ? error.message : String(error)));
    }
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
async function runQuery(sql: string): Promise<void> {
  const query = sql.trim();
  if (!query) return;

  state.lastQuery = query;
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
             data-table="${t}">
          <span style="color: var(--accent);">&#9632;</span> ${t}
        </div>
      `).join('');

      // Add click handlers for table names
      dataList.querySelectorAll('[data-table]').forEach(el => {
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
