/**
 * Notebook UI — DOM rendering for multi-cell notebook interface.
 *
 * Renders NotebookEngine cells into a container element.
 * SQL cells use Monaco; Markdown cells use a textarea with rendered preview.
 */

import { marked } from 'marked';
import * as monaco from 'monaco-editor';
import type { NotebookCell, NotebookEngine, CellType } from '../engines/editor';

// ============================================================================
// Styles
// ============================================================================

export function injectNotebookStyles(): void {
  if (document.getElementById('notebook-styles')) return;

  const style = document.createElement('style');
  style.id = 'notebook-styles';
  style.textContent = `
    .notebook-container {
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow-y: auto;
      padding: 0.75rem 1rem;
      gap: 0;
      background: var(--bg-primary);
    }

    /* Toolbar row above all cells */
    .notebook-toolbar {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.4rem 0;
      margin-bottom: 0.5rem;
      border-bottom: 1px solid var(--border);
    }
    .notebook-toolbar-title {
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-right: auto;
    }
    .notebook-save-btn {
      font-size: 0.75rem;
      padding: 0.25rem 0.6rem;
      background: var(--bg-secondary);
      color: var(--text-secondary);
      border: 1px solid var(--border);
      border-radius: 4px;
      cursor: pointer;
    }
    .notebook-save-btn:hover {
      color: var(--text-primary);
      background: var(--bg-tertiary);
    }
    .notebook-save-btn.saved {
      color: var(--success);
      border-color: var(--success);
    }

    /* Cell wrapper */
    .nb-cell {
      display: flex;
      gap: 0;
      margin-bottom: 8px;
      border: 1px solid var(--border);
      border-radius: 6px;
      overflow: hidden;
      background: var(--bg-secondary);
      transition: border-color 0.15s;
    }
    .nb-cell:hover {
      border-color: #555;
    }
    .nb-cell.running {
      border-color: #ffd700;
    }
    .nb-cell.success {
      border-color: rgba(0, 217, 255, 0.4);
    }
    .nb-cell.error {
      border-color: rgba(233, 69, 96, 0.5);
    }

    /* Gutter: execution count + state indicator */
    .nb-gutter {
      width: 40px;
      min-width: 40px;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 0.5rem 0.25rem;
      background: var(--bg-secondary);
      border-right: 1px solid var(--border);
      gap: 0.3rem;
      font-size: 0.65rem;
      color: var(--text-secondary);
      font-family: monospace;
    }
    .nb-exec-count {
      color: var(--text-secondary);
      font-size: 0.65rem;
      font-family: monospace;
    }
    .nb-state-icon {
      font-size: 0.7rem;
    }
    .nb-state-icon.running {
      display: inline-block;
      width: 10px;
      height: 10px;
      border: 2px solid var(--border);
      border-top-color: #ffd700;
      border-radius: 50%;
      animation: nb-spin 0.7s linear infinite;
    }
    @keyframes nb-spin {
      to { transform: rotate(360deg); }
    }
    .nb-state-icon.success { color: var(--success); }
    .nb-state-icon.error { color: var(--accent); }

    /* Cell body */
    .nb-body {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-width: 0;
    }

    /* Cell header bar */
    .nb-header {
      display: flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.3rem 0.5rem;
      background: var(--bg-secondary);
      border-bottom: 1px solid var(--border);
    }
    .nb-type-badge {
      font-size: 0.6rem;
      font-weight: 700;
      text-transform: uppercase;
      padding: 0.1rem 0.35rem;
      border-radius: 3px;
      letter-spacing: 0.04em;
    }
    .nb-type-badge.sql {
      background: rgba(86, 156, 214, 0.2);
      color: #569CD6;
    }
    .nb-type-badge.markdown {
      background: rgba(78, 201, 176, 0.2);
      color: #4EC9B0;
    }
    .nb-cell-actions {
      display: flex;
      gap: 2px;
      margin-left: auto;
    }
    .nb-btn {
      background: none;
      border: none;
      color: var(--text-secondary);
      cursor: pointer;
      padding: 0.15rem 0.35rem;
      border-radius: 3px;
      font-size: 0.7rem;
      line-height: 1;
      transition: color 0.1s, background 0.1s;
    }
    .nb-btn:hover {
      color: var(--text-primary);
      background: var(--bg-tertiary);
    }
    .nb-btn.run-btn {
      color: var(--success);
      font-size: 0.75rem;
    }
    .nb-btn.run-btn:hover {
      background: rgba(0, 217, 255, 0.1);
    }
    .nb-btn.delete-btn:hover {
      color: var(--accent);
      background: rgba(233, 69, 96, 0.1);
    }

    /* Editor area for SQL cells */
    .nb-editor-area {
      min-height: 80px;
    }
    .nb-monaco-host {
      /* height set dynamically */
    }

    /* Markdown edit / render */
    .nb-md-edit {
      width: 100%;
      min-height: 80px;
      background: var(--bg-primary);
      color: var(--text-primary);
      border: none;
      outline: none;
      resize: vertical;
      padding: 0.5rem 0.75rem;
      font-size: 0.85rem;
      font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
      line-height: 1.5;
      box-sizing: border-box;
    }
    .nb-md-preview {
      display: none;
      padding: 0.5rem 0.75rem;
      font-size: 0.875rem;
      line-height: 1.6;
      color: var(--text-primary);
    }
    .nb-md-preview.visible {
      display: block;
    }
    .nb-md-edit.hidden {
      display: none;
    }
    .nb-md-preview h1, .nb-md-preview h2, .nb-md-preview h3 {
      margin-top: 0.75rem;
      margin-bottom: 0.25rem;
      color: var(--text-primary);
    }
    .nb-md-preview p { margin: 0.4rem 0; }
    .nb-md-preview code {
      background: var(--bg-tertiary);
      padding: 0.1em 0.3em;
      border-radius: 3px;
      font-family: monospace;
      font-size: 0.85em;
    }
    .nb-md-preview pre code {
      display: block;
      padding: 0.5rem;
      overflow-x: auto;
    }
    .nb-md-preview table {
      border-collapse: collapse;
      width: 100%;
      font-size: 0.85rem;
      margin: 0.5rem 0;
    }
    .nb-md-preview th, .nb-md-preview td {
      padding: 0.3rem 0.5rem;
      border: 1px solid var(--border);
      text-align: left;
    }
    .nb-md-preview th {
      background: var(--bg-tertiary);
    }

    /* Output area */
    .nb-output {
      border-top: 1px solid var(--border);
      background: var(--bg-primary);
    }
    .nb-output.hidden {
      display: none;
    }
    .nb-output-meta {
      font-size: 0.7rem;
      color: var(--text-secondary);
      padding: 0.3rem 0.75rem;
      border-bottom: 1px solid var(--border);
    }
    .nb-output-table-wrap {
      overflow: auto;
      max-height: 300px;
      padding: 0 0.5rem 0.5rem;
    }
    .nb-output-table {
      min-width: 100%;
      width: max-content;
      border-collapse: collapse;
      font-size: 0.78rem;
    }
    .nb-output-table th {
      padding: 0.35rem 0.5rem;
      text-align: left;
      border-bottom: 2px solid var(--border);
      background: var(--bg-secondary);
      position: sticky;
      top: 0;
      font-weight: 600;
      white-space: nowrap;
    }
    .nb-output-table td {
      padding: 0.3rem 0.5rem;
      border-bottom: 1px solid var(--border);
      white-space: nowrap;
    }
    .nb-error-output {
      padding: 0.5rem 0.75rem;
      color: var(--accent);
      font-family: monospace;
      font-size: 0.8rem;
      white-space: pre-wrap;
    }

    /* Between-cell add buttons */
    .nb-add-row {
      display: flex;
      justify-content: center;
      gap: 0.5rem;
      padding: 0.2rem 0;
      opacity: 0;
      transition: opacity 0.15s;
      height: 24px;
    }
    .nb-add-row:hover {
      opacity: 1;
    }
    .nb-add-btn {
      font-size: 0.65rem;
      padding: 0.15rem 0.5rem;
      background: var(--bg-secondary);
      color: var(--text-secondary);
      border: 1px dashed var(--border);
      border-radius: 3px;
      cursor: pointer;
    }
    .nb-add-btn:hover {
      color: var(--text-primary);
      border-style: solid;
      border-color: #555;
    }

    /* Bottom add row always visible */
    .nb-add-row.bottom {
      opacity: 1;
      height: auto;
      padding: 0.5rem 0;
    }
  `;
  document.head.appendChild(style);
}

// ============================================================================
// Helpers
// ============================================================================

function escapeHtml(v: unknown): string {
  const s = v === null || v === undefined ? '' : String(v);
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function formatCellValue(v: unknown): string {
  if (v === null || v === undefined) return '';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

// ============================================================================
// Cell rendering helpers
// ============================================================================

function renderTableOutput(cell: NotebookCell): string {
  if (!cell.output || cell.output.type !== 'table') return '';
  const { columns, rows, rowCount, executionTimeMs } = cell.output;

  const headerHtml = columns
    .map(col => `<th>${escapeHtml(col)}</th>`)
    .join('');
  const rowsHtml = rows.slice(0, 500)
    .map(row => `<tr>${row.map(v => `<td>${escapeHtml(formatCellValue(v))}</td>`).join('')}</tr>`)
    .join('');

  return `
    <div class="nb-output-meta">
      ${rowCount.toLocaleString()} row${rowCount !== 1 ? 's' : ''}
      <span style="opacity:0.7;"> | ${executionTimeMs.toFixed(1)}ms</span>
      ${rows.length > 500 ? ' | Showing first 500' : ''}
    </div>
    <div class="nb-output-table-wrap">
      <table class="nb-output-table">
        <thead><tr>${headerHtml}</tr></thead>
        <tbody>${rowsHtml}</tbody>
      </table>
    </div>
  `;
}

// ============================================================================
// Core rendering
// ============================================================================

/**
 * Render a single cell into a DOM element and wire up Monaco if needed.
 * Returns the outer .nb-cell element.
 */
function renderCell(
  cell: NotebookCell,
  engine: NotebookEngine,
  onRerender: () => void,
): HTMLElement {
  const wrapper = document.createElement('div');
  wrapper.className = `nb-cell ${cell.state}`;
  wrapper.dataset.cellId = cell.id;

  // ---- Gutter ----
  const gutter = document.createElement('div');
  gutter.className = 'nb-gutter';

  const execCount = document.createElement('div');
  execCount.className = 'nb-exec-count';
  execCount.textContent = cell.executionCount !== null ? `[${cell.executionCount}]` : '[ ]';

  const stateIcon = document.createElement('div');
  stateIcon.className = `nb-state-icon ${cell.state}`;
  if (cell.state === 'success') stateIcon.textContent = '✓';
  else if (cell.state === 'error') stateIcon.textContent = '✗';
  else if (cell.state === 'running') {
    // spinner via CSS
  }

  gutter.appendChild(execCount);
  gutter.appendChild(stateIcon);

  // ---- Body ----
  const body = document.createElement('div');
  body.className = 'nb-body';

  // Header
  const header = document.createElement('div');
  header.className = 'nb-header';

  const badge = document.createElement('span');
  badge.className = `nb-type-badge ${cell.type}`;
  badge.textContent = cell.type.toUpperCase();

  const actions = document.createElement('div');
  actions.className = 'nb-cell-actions';

  // Run/Render button
  const runBtn = document.createElement('button');
  runBtn.className = 'nb-btn run-btn';
  runBtn.title = cell.type === 'sql' ? 'Run (Ctrl+Enter)' : 'Render Markdown';
  runBtn.textContent = cell.type === 'sql' ? '▶ Run' : '⬛ Render';

  // Move up
  const upBtn = document.createElement('button');
  upBtn.className = 'nb-btn';
  upBtn.title = 'Move up';
  upBtn.textContent = '↑';

  // Move down
  const downBtn = document.createElement('button');
  downBtn.className = 'nb-btn';
  downBtn.title = 'Move down';
  downBtn.textContent = '↓';

  // Delete
  const delBtn = document.createElement('button');
  delBtn.className = 'nb-btn delete-btn';
  delBtn.title = 'Delete cell';
  delBtn.textContent = '✕';

  actions.appendChild(runBtn);
  actions.appendChild(upBtn);
  actions.appendChild(downBtn);
  actions.appendChild(delBtn);

  header.appendChild(badge);
  header.appendChild(actions);

  // Editor area
  const editorArea = document.createElement('div');
  editorArea.className = 'nb-editor-area';

  if (cell.type === 'sql') {
    const monacoHost = document.createElement('div');
    monacoHost.className = 'nb-monaco-host';
    monacoHost.style.height = '120px';
    editorArea.appendChild(monacoHost);

    // Create Monaco after DOM insertion (requires element to be in document)
    requestAnimationFrame(() => {
      const ed = monaco.editor.create(monacoHost, {
        value: cell.content,
        language: 'sql',
        theme: 'audit-dark',
        fontSize: 13,
        fontFamily: "'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code', monospace",
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        wordWrap: 'on',
        automaticLayout: true,
        lineNumbers: 'on',
        lineNumbersMinChars: 3,
        glyphMargin: false,
        folding: false,
        padding: { top: 6, bottom: 6 },
        scrollbar: { vertical: 'auto', horizontal: 'auto', verticalScrollbarSize: 8 },
      });

      cell.monacoEditor = ed;

      // Auto-resize editor height to content
      const updateHeight = () => {
        const lineCount = ed.getModel()?.getLineCount() ?? 1;
        const newH = Math.max(80, Math.min(400, lineCount * 20 + 20));
        monacoHost.style.height = `${newH}px`;
        ed.layout();
      };
      ed.onDidChangeModelContent(updateHeight);
      updateHeight();

      // Ctrl+Enter to run
      ed.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => {
        void runAndUpdate(cell, engine, wrapper, onRerender);
      });
    });
  } else {
    // Markdown cell: textarea + preview
    const textarea = document.createElement('textarea');
    textarea.className = 'nb-md-edit';
    textarea.value = cell.content;
    textarea.placeholder = 'Write Markdown here...';
    textarea.addEventListener('input', () => {
      cell.content = textarea.value;
    });

    const preview = document.createElement('div');
    preview.className = 'nb-md-preview';

    editorArea.appendChild(textarea);
    editorArea.appendChild(preview);
  }

  // Output area
  const outputArea = document.createElement('div');
  outputArea.className = 'nb-output hidden';

  if (cell.output) {
    if (cell.output.type === 'table') {
      outputArea.innerHTML = renderTableOutput(cell);
      outputArea.classList.remove('hidden');
    } else if (cell.output.type === 'markdown') {
      outputArea.innerHTML = cell.output.html;
      outputArea.classList.remove('hidden');
    } else if (cell.output.type === 'error') {
      outputArea.innerHTML = `<div class="nb-error-output">${escapeHtml(cell.output.message)}</div>`;
      outputArea.classList.remove('hidden');
    }
  }

  body.appendChild(header);
  body.appendChild(editorArea);
  body.appendChild(outputArea);

  wrapper.appendChild(gutter);
  wrapper.appendChild(body);

  // ---- Event handlers ----

  runBtn.addEventListener('click', () => {
    void runAndUpdate(cell, engine, wrapper, onRerender);
  });

  upBtn.addEventListener('click', () => {
    engine.moveCell(cell.id, 'up');
    onRerender();
  });

  downBtn.addEventListener('click', () => {
    engine.moveCell(cell.id, 'down');
    onRerender();
  });

  delBtn.addEventListener('click', () => {
    engine.deleteCell(cell.id);
    onRerender();
  });

  return wrapper;
}

/**
 * Execute a cell and update its DOM in-place (without full re-render).
 */
async function runAndUpdate(
  cell: NotebookCell,
  engine: NotebookEngine,
  wrapper: HTMLElement,
  onRerender: () => void,
): Promise<void> {
  // Sync content from Monaco if SQL
  if (cell.type === 'sql' && cell.monacoEditor) {
    cell.content = cell.monacoEditor.getValue();
  }

  // Markdown: render and show
  if (cell.type === 'markdown') {
    const html = await marked.parse(cell.content);
    cell.output = { type: 'markdown', html };
    cell.state = 'success';

    // Update preview
    const editArea = wrapper.querySelector('.nb-md-edit') as HTMLTextAreaElement | null;
    const preview = wrapper.querySelector('.nb-md-preview') as HTMLElement | null;

    if (editArea) editArea.classList.add('hidden');
    if (preview) {
      preview.innerHTML = html;
      preview.classList.add('visible');
    }

    updateCellStateDOM(wrapper, cell);
    onRerender(); // save state
    return;
  }

  // SQL: execute
  updateCellStateDOM(wrapper, cell, 'running');

  await engine.executeCell(cell.id);

  updateCellStateDOM(wrapper, cell);

  // Update output area in-place
  const outputArea = wrapper.querySelector('.nb-output') as HTMLElement | null;
  if (!outputArea) return;

  if (!cell.output) {
    outputArea.classList.add('hidden');
    return;
  }

  if (cell.output.type === 'table') {
    outputArea.innerHTML = renderTableOutput(cell);
  } else if (cell.output.type === 'error') {
    outputArea.innerHTML = `<div class="nb-error-output">${escapeHtml(cell.output.message)}</div>`;
  }
  outputArea.classList.remove('hidden');

  onRerender();
}

function updateCellStateDOM(wrapper: HTMLElement, cell: NotebookCell, override?: string): void {
  const state = override ?? cell.state;
  wrapper.className = `nb-cell ${state}`;

  const gutter = wrapper.querySelector('.nb-gutter');
  if (!gutter) return;

  const execCount = gutter.querySelector('.nb-exec-count');
  if (execCount) {
    execCount.textContent = cell.executionCount !== null ? `[${cell.executionCount}]` : '[ ]';
  }

  const stateIcon = gutter.querySelector('.nb-state-icon');
  if (stateIcon) {
    stateIcon.className = `nb-state-icon ${state}`;
    if (state === 'success') stateIcon.textContent = '✓';
    else if (state === 'error') stateIcon.textContent = '✗';
    else stateIcon.textContent = '';
  }
}

// ============================================================================
// Public API
// ============================================================================

/**
 * Render the full notebook into `container`.
 * Returns an `onSave` callback you can wire to a save button.
 */
export function renderNotebook(
  container: HTMLElement,
  engine: NotebookEngine,
  onSave: () => void,
): void {
  injectNotebookStyles();

  const rebuild = () => renderNotebook(container, engine, onSave);

  container.innerHTML = '';

  const inner = document.createElement('div');
  inner.className = 'notebook-container';

  // Toolbar
  const toolbar = document.createElement('div');
  toolbar.className = 'notebook-toolbar';
  const title = document.createElement('span');
  title.className = 'notebook-toolbar-title';
  title.textContent = 'Notebook';
  const saveBtn = document.createElement('button');
  saveBtn.className = 'notebook-save-btn';
  saveBtn.textContent = '💾 Save';
  saveBtn.addEventListener('click', () => {
    onSave();
    saveBtn.classList.add('saved');
    saveBtn.textContent = '✓ Saved';
    setTimeout(() => {
      saveBtn.classList.remove('saved');
      saveBtn.textContent = '💾 Save';
    }, 2000);
  });
  toolbar.appendChild(title);
  toolbar.appendChild(saveBtn);
  inner.appendChild(toolbar);

  // Cells
  const cells = engine.getCells();

  if (cells.length === 0) {
    // Show add buttons when empty
    const emptyMsg = document.createElement('div');
    emptyMsg.style.cssText = 'text-align: center; padding: 2rem; color: var(--text-secondary); font-size: 0.85rem;';
    emptyMsg.textContent = 'No cells yet. Add one below.';
    inner.appendChild(emptyMsg);
  }

  cells.forEach((cell, idx) => {
    // Add-between row (shown on hover)
    if (idx === 0) {
      inner.appendChild(makeAddRow(cell.id, engine, rebuild, 'before'));
    }

    const cellEl = renderCell(cell, engine, rebuild);
    inner.appendChild(cellEl);

    // Add row after each cell
    inner.appendChild(makeAddRow(cell.id, engine, rebuild, 'after'));
  });

  // Bottom add row (always visible)
  const bottomRow = makeAddRow(null, engine, rebuild, 'bottom');
  bottomRow.classList.add('bottom');
  inner.appendChild(bottomRow);

  container.appendChild(inner);
}

function makeAddRow(
  afterCellId: string | null,
  engine: NotebookEngine,
  onRerender: () => void,
  _position: 'before' | 'after' | 'bottom',
): HTMLElement {
  const row = document.createElement('div');
  row.className = 'nb-add-row';

  const addSql = document.createElement('button');
  addSql.className = 'nb-add-btn';
  addSql.textContent = '+ SQL';
  addSql.addEventListener('click', () => {
    engine.addCell('sql', '', afterCellId ?? undefined);
    onRerender();
  });

  const addMd = document.createElement('button');
  addMd.className = 'nb-add-btn';
  addMd.textContent = '+ Markdown';
  addMd.addEventListener('click', () => {
    engine.addCell('markdown', '', afterCellId ?? undefined);
    onRerender();
  });

  row.appendChild(addSql);
  row.appendChild(addMd);
  return row;
}

/**
 * Add a new cell type to the engine from outside the notebook UI.
 */
export function addNotebookCell(engine: NotebookEngine, type: CellType, content?: string): void {
  engine.addCell(type, content);
}
