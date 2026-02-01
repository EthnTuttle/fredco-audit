/**
 * FCPS Data Playground v2
 * 
 * Entry point for the data playground application.
 * Initializes DuckDB-WASM and sets up the notebook interface.
 */

import { initDataEngine } from './engines/data';

// Application state
interface AppState {
  status: 'loading' | 'ready' | 'error';
  error?: string;
}

const state: AppState = { status: 'loading' };

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
        <main style="flex: 1; display: flex;">
          <aside id="sidebar" style="width: 250px; border-right: 1px solid var(--border); padding: 1rem;">
            <h3 style="margin-top: 0;">Data Files</h3>
            <div id="data-list" style="font-size: 0.85rem;">Loading...</div>
          </aside>
          <section id="editor" style="flex: 1; display: flex; flex-direction: column;">
            <div id="notebook" style="flex: 1; padding: 1rem; overflow: auto;">
              <div class="cell">
                <textarea id="sql-input" placeholder="Enter SQL query..." style="width: 100%; min-height: 100px; background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border); padding: 0.5rem; font-family: inherit; resize: vertical;"></textarea>
                <button id="run-btn" style="margin-top: 0.5rem; padding: 0.5rem 1rem; background: var(--accent); color: white; border: none; cursor: pointer;">Run Query</button>
              </div>
              <div id="results" style="margin-top: 1rem; padding: 1rem; background: var(--bg-secondary); border-radius: 4px; overflow: auto;">
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

  runBtn?.addEventListener('click', async () => {
    const query = sqlInput?.value.trim();
    if (!query) return;

    const results = document.getElementById('results');
    if (results) {
      results.innerHTML = '<em style="color: var(--text-secondary);">Running query...</em>';
    }

    try {
      const { executeQuery } = await import('./engines/data');
      const result = await executeQuery(query);
      
      if (results) {
        if (result.rows.length === 0) {
          results.innerHTML = '<em style="color: var(--text-secondary);">Query returned no results</em>';
        } else {
          results.innerHTML = renderTable(result.columns, result.rows);
        }
      }
    } catch (error) {
      if (results) {
        results.innerHTML = `<div style="color: var(--accent);">Error: ${error instanceof Error ? error.message : String(error)}</div>`;
      }
    }
  });

  // Ctrl+Enter to run
  sqlInput?.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      runBtn?.click();
    }
  });
}

/**
 * Render a table from query results
 */
function renderTable(columns: string[], rows: unknown[][]): string {
  if (columns.length === 0) return '<em>No columns</em>';

  const headerHtml = columns.map(col => `<th style="padding: 0.5rem; text-align: left; border-bottom: 1px solid var(--border);">${escapeHtml(col)}</th>`).join('');
  
  const rowsHtml = rows.slice(0, 1000).map(row => {
    const cells = row.map(cell => `<td style="padding: 0.5rem; border-bottom: 1px solid var(--border);">${escapeHtml(String(cell ?? 'NULL'))}</td>`).join('');
    return `<tr>${cells}</tr>`;
  }).join('');

  const truncated = rows.length > 1000 ? `<div style="margin-top: 0.5rem; color: var(--text-secondary);">Showing 1000 of ${rows.length} rows</div>` : '';

  return `
    <div style="margin-bottom: 0.5rem; color: var(--text-secondary);">${rows.length} row(s)</div>
    <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
      <thead><tr>${headerHtml}</tr></thead>
      <tbody>${rowsHtml}</tbody>
    </table>
    ${truncated}
  `;
}

/**
 * Load and display available data files
 */
async function loadDataFileList(): Promise<void> {
  const dataList = document.getElementById('data-list');
  if (!dataList) return;

  try {
    const { getLoadedTables } = await import('./engines/data');
    const tables = await getLoadedTables();
    
    if (tables.length === 0) {
      dataList.innerHTML = '<em style="color: var(--text-secondary);">No data loaded</em>';
    } else {
      dataList.innerHTML = tables.map(t => `
        <div style="padding: 0.25rem 0; cursor: pointer;" onclick="document.getElementById('sql-input').value = 'SELECT * FROM ${t} LIMIT 100'">
          ${t}
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
