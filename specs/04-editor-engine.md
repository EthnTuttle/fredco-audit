# EditorEngine Component Specification

**Version:** 1.0.0  
**Status:** Draft  
**Last Updated:** 2026-01-31

---

## 1. Purpose and Responsibilities

The EditorEngine manages the notebook-style editing experience, providing a multi-cell interface for combining SQL queries with Markdown documentation. It serves as the primary user interface for writing, organizing, and executing analytical queries against the audit data.

### Core Responsibilities

| Responsibility | Description |
|----------------|-------------|
| Monaco Integration | Embed and configure Monaco editor for SQL cells with syntax highlighting |
| Markdown Support | Render Markdown cells for documentation and narrative |
| Cell Management | Create, delete, reorder, and navigate between cells |
| Query Execution | Trigger SQL execution via DataEngine integration |
| Autocomplete | Provide intelligent suggestions for tables, columns, and SQL keywords |
| State Persistence | Track cell content, execution state, and output |

### Non-Responsibilities

- Query execution (delegated to DataEngine)
- Result visualization (delegated to ChartEngine)
- File I/O (delegated to Tauri backend)

---

## 2. Rust Type Definitions

### Cell Types

```rust
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Supported cell types in the notebook
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum CellType {
    /// Executable SQL query cell
    Sql,
    /// Rendered Markdown documentation cell
    Markdown,
}

/// Execution state of a cell
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Default)]
#[serde(rename_all = "snake_case")]
pub enum CellExecutionState {
    #[default]
    Idle,
    Running,
    Success,
    Error,
}

/// Output produced by cell execution
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum CellOutput {
    /// Tabular query results
    Table {
        columns: Vec<ColumnInfo>,
        rows: Vec<Vec<serde_json::Value>>,
        row_count: usize,
        truncated: bool,
    },
    /// Rendered Markdown HTML
    Markdown { html: String },
    /// Error message
    Error { message: String, details: Option<String> },
    /// Empty output
    Empty,
}

/// Column metadata for table output
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ColumnInfo {
    pub name: String,
    pub data_type: String,
}

/// A single cell in the notebook
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Cell {
    /// Unique identifier for the cell
    pub id: Uuid,
    /// Type of cell (SQL or Markdown)
    pub cell_type: CellType,
    /// Raw content/source of the cell
    pub content: String,
    /// Current execution state
    pub execution_state: CellExecutionState,
    /// Output from last execution (if any)
    pub output: Option<CellOutput>,
    /// Execution order number (for SQL cells)
    pub execution_count: Option<u32>,
    /// Timestamp of last execution
    pub last_executed: Option<i64>,
    /// Whether cell is currently focused
    #[serde(skip)]
    pub focused: bool,
    /// Whether cell is in edit mode
    #[serde(skip)]
    pub editing: bool,
}

impl Cell {
    /// Create a new SQL cell
    pub fn new_sql() -> Self {
        Self {
            id: Uuid::new_v4(),
            cell_type: CellType::Sql,
            content: String::new(),
            execution_state: CellExecutionState::Idle,
            output: None,
            execution_count: None,
            last_executed: None,
            focused: false,
            editing: true,
        }
    }

    /// Create a new Markdown cell
    pub fn new_markdown() -> Self {
        Self {
            id: Uuid::new_v4(),
            cell_type: CellType::Markdown,
            content: String::new(),
            execution_state: CellExecutionState::Idle,
            output: None,
            execution_count: None,
            last_executed: None,
            focused: false,
            editing: true,
        }
    }

    /// Create a cell with initial content
    pub fn with_content(mut self, content: impl Into<String>) -> Self {
        self.content = content.into();
        self
    }
}

/// Complete notebook state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Notebook {
    /// Notebook file path (if saved)
    pub path: Option<String>,
    /// Ordered list of cells
    pub cells: Vec<Cell>,
    /// Global execution counter
    pub execution_counter: u32,
    /// Whether notebook has unsaved changes
    #[serde(skip)]
    pub dirty: bool,
    /// Notebook metadata
    pub metadata: NotebookMetadata,
}

/// Notebook metadata
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct NotebookMetadata {
    pub title: Option<String>,
    pub description: Option<String>,
    pub created_at: Option<i64>,
    pub modified_at: Option<i64>,
    pub data_sources: Vec<String>,
}

impl Default for Notebook {
    fn default() -> Self {
        Self {
            path: None,
            cells: vec![Cell::new_sql()],
            execution_counter: 0,
            dirty: false,
            metadata: NotebookMetadata::default(),
        }
    }
}
```

### Autocomplete Types

```rust
/// Autocomplete suggestion
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompletionItem {
    /// Display label
    pub label: String,
    /// Type of completion
    pub kind: CompletionKind,
    /// Detailed description
    pub detail: Option<String>,
    /// Documentation string
    pub documentation: Option<String>,
    /// Text to insert
    pub insert_text: String,
}

/// Types of autocomplete suggestions
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum CompletionKind {
    Table,
    Column,
    Keyword,
    Function,
    Snippet,
}

/// Schema information for autocomplete
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SchemaInfo {
    pub tables: Vec<TableSchema>,
}

/// Table schema for autocomplete
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TableSchema {
    pub name: String,
    pub columns: Vec<ColumnSchema>,
}

/// Column schema for autocomplete
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ColumnSchema {
    pub name: String,
    pub data_type: String,
    pub nullable: bool,
}
```

---

## 3. Message Protocol

### Frontend to Backend Messages

```rust
/// Messages sent from EditorEngine to backend
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "payload")]
pub enum EditorCommand {
    /// Execute a SQL cell
    ExecuteCell {
        cell_id: Uuid,
        sql: String,
    },
    /// Cancel running execution
    CancelExecution {
        cell_id: Uuid,
    },
    /// Request schema for autocomplete
    GetSchema,
    /// Save notebook to file
    SaveNotebook {
        path: String,
        notebook: Notebook,
    },
    /// Load notebook from file
    LoadNotebook {
        path: String,
    },
    /// Render Markdown to HTML
    RenderMarkdown {
        cell_id: Uuid,
        content: String,
    },
}
```

### Backend to Frontend Messages

```rust
/// Messages sent from backend to EditorEngine
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "payload")]
pub enum EditorEvent {
    /// Cell execution started
    ExecutionStarted {
        cell_id: Uuid,
    },
    /// Cell execution completed successfully
    ExecutionComplete {
        cell_id: Uuid,
        output: CellOutput,
        execution_count: u32,
        duration_ms: u64,
    },
    /// Cell execution failed
    ExecutionError {
        cell_id: Uuid,
        error: String,
        details: Option<String>,
    },
    /// Schema information for autocomplete
    SchemaLoaded {
        schema: SchemaInfo,
    },
    /// Notebook saved successfully
    NotebookSaved {
        path: String,
    },
    /// Notebook loaded successfully
    NotebookLoaded {
        notebook: Notebook,
    },
    /// Markdown rendered to HTML
    MarkdownRendered {
        cell_id: Uuid,
        html: String,
    },
}
```

### Tauri Command Definitions

```rust
#[tauri::command]
async fn execute_cell(
    cell_id: String,
    sql: String,
    state: State<'_, AppState>,
) -> Result<CellOutput, String>;

#[tauri::command]
async fn cancel_execution(cell_id: String) -> Result<(), String>;

#[tauri::command]
async fn get_schema(state: State<'_, AppState>) -> Result<SchemaInfo, String>;

#[tauri::command]
async fn save_notebook(path: String, notebook: Notebook) -> Result<(), String>;

#[tauri::command]
async fn load_notebook(path: String) -> Result<Notebook, String>;

#[tauri::command]
fn render_markdown(content: String) -> Result<String, String>;
```

---

## 4. Monaco Configuration

### Editor Setup

```typescript
import * as monaco from 'monaco-editor';

interface MonacoConfig {
  // Base SQL configuration
  language: 'sql';
  theme: 'audit-dark' | 'audit-light';
  
  // Editor options
  options: monaco.editor.IStandaloneEditorConstructionOptions;
}

const defaultMonacoOptions: monaco.editor.IStandaloneEditorConstructionOptions = {
  // Display
  fontSize: 14,
  fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
  fontLigatures: true,
  lineHeight: 22,
  
  // Behavior
  minimap: { enabled: false },
  scrollBeyondLastLine: false,
  wordWrap: 'on',
  automaticLayout: true,
  
  // Line numbers
  lineNumbers: 'on',
  lineNumbersMinChars: 3,
  
  // Suggestions
  suggestOnTriggerCharacters: true,
  quickSuggestions: {
    other: true,
    comments: false,
    strings: true,
  },
  acceptSuggestionOnEnter: 'smart',
  tabCompletion: 'on',
  
  // Formatting
  formatOnPaste: true,
  formatOnType: true,
  
  // Scrollbar
  scrollbar: {
    vertical: 'auto',
    horizontal: 'auto',
    verticalScrollbarSize: 10,
    horizontalScrollbarSize: 10,
  },
  
  // Rendering
  renderWhitespace: 'selection',
  renderLineHighlight: 'line',
  cursorBlinking: 'smooth',
  cursorSmoothCaretAnimation: 'on',
};
```

### Custom Theme Definition

```typescript
monaco.editor.defineTheme('audit-dark', {
  base: 'vs-dark',
  inherit: true,
  rules: [
    { token: 'keyword', foreground: '#569CD6', fontStyle: 'bold' },
    { token: 'string', foreground: '#CE9178' },
    { token: 'number', foreground: '#B5CEA8' },
    { token: 'comment', foreground: '#6A9955', fontStyle: 'italic' },
    { token: 'operator', foreground: '#D4D4D4' },
    { token: 'identifier', foreground: '#9CDCFE' },
    { token: 'type', foreground: '#4EC9B0' },
  ],
  colors: {
    'editor.background': '#1E1E1E',
    'editor.foreground': '#D4D4D4',
    'editor.lineHighlightBackground': '#2D2D2D',
    'editor.selectionBackground': '#264F78',
    'editorCursor.foreground': '#FFFFFF',
    'editorLineNumber.foreground': '#858585',
    'editorLineNumber.activeForeground': '#C6C6C6',
  },
});
```

### Autocomplete Provider

```typescript
const sqlCompletionProvider: monaco.languages.CompletionItemProvider = {
  triggerCharacters: ['.', ' '],
  
  provideCompletionItems: async (
    model: monaco.editor.ITextModel,
    position: monaco.Position,
    context: monaco.languages.CompletionContext,
  ): Promise<monaco.languages.CompletionList> => {
    const word = model.getWordUntilPosition(position);
    const range: monaco.IRange = {
      startLineNumber: position.lineNumber,
      endLineNumber: position.lineNumber,
      startColumn: word.startColumn,
      endColumn: word.endColumn,
    };

    // Get schema from backend
    const schema = await invoke<SchemaInfo>('get_schema');
    
    const suggestions: monaco.languages.CompletionItem[] = [];
    
    // Add table suggestions
    for (const table of schema.tables) {
      suggestions.push({
        label: table.name,
        kind: monaco.languages.CompletionItemKind.Class,
        insertText: table.name,
        detail: `Table (${table.columns.length} columns)`,
        range,
      });
    }
    
    // Check if we're after a table reference (for column suggestions)
    const lineContent = model.getLineContent(position.lineNumber);
    const beforeCursor = lineContent.substring(0, position.column - 1);
    const tableMatch = beforeCursor.match(/(\w+)\.\s*$/);
    
    if (tableMatch) {
      const tableName = tableMatch[1];
      const table = schema.tables.find(t => 
        t.name.toLowerCase() === tableName.toLowerCase()
      );
      
      if (table) {
        for (const column of table.columns) {
          suggestions.push({
            label: column.name,
            kind: monaco.languages.CompletionItemKind.Field,
            insertText: column.name,
            detail: `${column.data_type}${column.nullable ? ' (nullable)' : ''}`,
            range,
          });
        }
      }
    }
    
    // Add SQL keywords
    const keywords = [
      'SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER',
      'ON', 'AND', 'OR', 'NOT', 'IN', 'LIKE', 'BETWEEN', 'IS', 'NULL',
      'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT', 'OFFSET', 'AS', 'DISTINCT',
      'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
      'UNION', 'EXCEPT', 'INTERSECT', 'WITH', 'INSERT', 'UPDATE', 'DELETE',
    ];
    
    for (const keyword of keywords) {
      suggestions.push({
        label: keyword,
        kind: monaco.languages.CompletionItemKind.Keyword,
        insertText: keyword,
        range,
      });
    }
    
    return { suggestions };
  },
};

// Register the provider
monaco.languages.registerCompletionItemProvider('sql', sqlCompletionProvider);
```

---

## 5. Markdown Rendering

### Rendering Approach

Markdown cells use a dual-mode interface:
1. **Edit Mode:** Plain text editor (Monaco with markdown language)
2. **View Mode:** Rendered HTML output

### Backend Rendering (Rust)

```rust
use pulldown_cmark::{html, Options, Parser};

/// Render Markdown to HTML with security sanitization
pub fn render_markdown(content: &str) -> String {
    let options = Options::ENABLE_TABLES
        | Options::ENABLE_FOOTNOTES
        | Options::ENABLE_STRIKETHROUGH
        | Options::ENABLE_TASKLISTS;
    
    let parser = Parser::new_ext(content, options);
    
    let mut html_output = String::new();
    html::push_html(&mut html_output, parser);
    
    // Sanitize HTML to prevent XSS
    ammonia::clean(&html_output)
}
```

### Markdown CSS Styling

```css
.markdown-cell-rendered {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
  padding: 12px 16px;
}

.markdown-cell-rendered h1 {
  font-size: 1.75em;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0.3em;
  margin-top: 1em;
  margin-bottom: 0.5em;
}

.markdown-cell-rendered h2 {
  font-size: 1.5em;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0.25em;
}

.markdown-cell-rendered code {
  background: var(--code-bg);
  padding: 0.2em 0.4em;
  border-radius: 3px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.9em;
}

.markdown-cell-rendered pre {
  background: var(--code-bg);
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
}

.markdown-cell-rendered pre code {
  background: transparent;
  padding: 0;
}

.markdown-cell-rendered table {
  border-collapse: collapse;
  width: 100%;
  margin: 1em 0;
}

.markdown-cell-rendered th,
.markdown-cell-rendered td {
  border: 1px solid var(--border-color);
  padding: 8px 12px;
  text-align: left;
}

.markdown-cell-rendered th {
  background: var(--header-bg);
  font-weight: 600;
}

.markdown-cell-rendered blockquote {
  border-left: 4px solid var(--accent-color);
  margin: 1em 0;
  padding-left: 1em;
  color: var(--text-secondary);
}

.markdown-cell-rendered ul,
.markdown-cell-rendered ol {
  padding-left: 2em;
}

.markdown-cell-rendered li {
  margin: 0.25em 0;
}
```

---

## 6. Keyboard Shortcuts

### Global Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| `Ctrl+Enter` | Execute current cell | SQL cell focused |
| `Shift+Enter` | Execute and move to next cell | Any cell |
| `Ctrl+Shift+Enter` | Execute all cells | Any |
| `Escape` | Exit edit mode / Cancel | Editing |
| `Enter` | Enter edit mode | Cell selected, not editing |

### Cell Management

| Shortcut | Action | Context |
|----------|--------|---------|
| `Ctrl+Shift+A` | Add SQL cell above | Any |
| `Ctrl+Shift+B` | Add SQL cell below | Any |
| `Ctrl+Shift+M` | Add Markdown cell below | Any |
| `Ctrl+Shift+D` | Delete current cell | Cell selected |
| `Ctrl+Shift+Up` | Move cell up | Cell selected |
| `Ctrl+Shift+Down` | Move cell down | Cell selected |

### Navigation

| Shortcut | Action | Context |
|----------|--------|---------|
| `Up` / `K` | Select previous cell | Not editing |
| `Down` / `J` | Select next cell | Not editing |
| `Ctrl+Home` | Go to first cell | Any |
| `Ctrl+End` | Go to last cell | Any |

### Editor Shortcuts (Monaco)

| Shortcut | Action | Context |
|----------|--------|---------|
| `Ctrl+Space` | Trigger autocomplete | Editing SQL |
| `Ctrl+/` | Toggle line comment | Editing |
| `Ctrl+D` | Select next occurrence | Editing |
| `Ctrl+Shift+K` | Delete line | Editing |
| `Alt+Up` | Move line up | Editing |
| `Alt+Down` | Move line down | Editing |
| `Ctrl+Shift+F` | Format document | Editing SQL |

### Implementation

```typescript
import { createShortcut } from '@solid-primitives/keyboard';

function setupEditorShortcuts(
  notebook: NotebookStore,
  executeCell: (id: string) => Promise<void>,
) {
  // Execute current cell
  createShortcut(['Control', 'Enter'], () => {
    const focused = notebook.getFocusedCell();
    if (focused?.cell_type === 'sql') {
      executeCell(focused.id);
    }
  });

  // Execute and advance
  createShortcut(['Shift', 'Enter'], async () => {
    const focused = notebook.getFocusedCell();
    if (focused) {
      if (focused.cell_type === 'sql') {
        await executeCell(focused.id);
      }
      notebook.focusNextCell();
    }
  });

  // Add cell below
  createShortcut(['Control', 'Shift', 'B'], () => {
    notebook.addCellBelow('sql');
  });

  // Add markdown cell
  createShortcut(['Control', 'Shift', 'M'], () => {
    notebook.addCellBelow('markdown');
  });

  // Delete cell
  createShortcut(['Control', 'Shift', 'D'], () => {
    const focused = notebook.getFocusedCell();
    if (focused && notebook.cells.length > 1) {
      notebook.deleteCell(focused.id);
    }
  });

  // Navigation (when not editing)
  createShortcut(['ArrowUp'], () => {
    if (!notebook.isEditing()) {
      notebook.focusPreviousCell();
    }
  });

  createShortcut(['ArrowDown'], () => {
    if (!notebook.isEditing()) {
      notebook.focusNextCell();
    }
  });
}
```

---

## 7. Example Usage

### Creating a New Notebook

```typescript
import { createNotebookStore } from './stores/notebook';
import { invoke } from '@tauri-apps/api/core';

// Initialize store
const notebook = createNotebookStore();

// Add a markdown header cell
notebook.addCell({
  cell_type: 'markdown',
  content: `# FCPS Administrative Overhead Analysis

This notebook analyzes administrative spending trends for Frederick County Public Schools
compared to peer districts.

**Data Sources:**
- VDOE Table 15: Per-pupil expenditures
- VDOE Table 18: Administrative personnel
`,
});

// Add a SQL query cell
notebook.addCell({
  cell_type: 'sql',
  content: `-- Compare admin ratios across peer districts
SELECT 
    division_name,
    fiscal_year,
    admin_staff_count,
    total_enrollment,
    ROUND(admin_staff_count * 1.0 / total_enrollment * 1000, 2) as admin_per_1000_students
FROM admin_summary
WHERE division_code IN ('069', '043', '061', '171', '187')
ORDER BY fiscal_year, admin_per_1000_students DESC;`,
});
```

### Executing a Cell

```typescript
async function executeCell(cellId: string) {
  const cell = notebook.getCell(cellId);
  if (!cell || cell.cell_type !== 'sql') return;

  // Update state to running
  notebook.updateCell(cellId, {
    execution_state: 'running',
  });

  try {
    const result = await invoke<CellOutput>('execute_cell', {
      cellId,
      sql: cell.content,
    });

    // Increment execution counter
    const executionCount = notebook.incrementExecutionCounter();

    // Update with results
    notebook.updateCell(cellId, {
      execution_state: 'success',
      output: result,
      execution_count: executionCount,
      last_executed: Date.now(),
    });
  } catch (error) {
    notebook.updateCell(cellId, {
      execution_state: 'error',
      output: {
        type: 'Error',
        data: {
          message: error instanceof Error ? error.message : String(error),
        },
      },
    });
  }
}
```

### Complete Cell Component

```tsx
import { Component, Show, createSignal } from 'solid-js';
import { Cell } from '../types';
import { MonacoEditor } from './MonacoEditor';
import { MarkdownRenderer } from './MarkdownRenderer';
import { CellToolbar } from './CellToolbar';
import { CellOutput } from './CellOutput';

interface CellComponentProps {
  cell: Cell;
  onExecute: () => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onContentChange: (content: string) => void;
  onFocus: () => void;
}

export const CellComponent: Component<CellComponentProps> = (props) => {
  const [isEditing, setIsEditing] = createSignal(props.cell.editing);

  const handleDoubleClick = () => {
    if (props.cell.cell_type === 'markdown') {
      setIsEditing(true);
    }
  };

  const handleBlur = () => {
    if (props.cell.cell_type === 'markdown') {
      setIsEditing(false);
    }
  };

  return (
    <div
      class={`cell ${props.cell.focused ? 'focused' : ''}`}
      data-cell-type={props.cell.cell_type}
      data-execution-state={props.cell.execution_state}
      onClick={props.onFocus}
    >
      <div class="cell-gutter">
        <Show when={props.cell.cell_type === 'sql'}>
          <span class="execution-count">
            [{props.cell.execution_count ?? ' '}]
          </span>
        </Show>
        <Show when={props.cell.cell_type === 'markdown'}>
          <span class="cell-type-indicator">MD</span>
        </Show>
      </div>

      <div class="cell-content">
        <CellToolbar
          cellType={props.cell.cell_type}
          executionState={props.cell.execution_state}
          onExecute={props.onExecute}
          onDelete={props.onDelete}
          onMoveUp={props.onMoveUp}
          onMoveDown={props.onMoveDown}
        />

        <Show
          when={props.cell.cell_type === 'sql' || isEditing()}
          fallback={
            <div
              class="markdown-cell-rendered"
              onDblClick={handleDoubleClick}
              innerHTML={props.cell.output?.type === 'Markdown' 
                ? props.cell.output.data.html 
                : ''}
            />
          }
        >
          <MonacoEditor
            value={props.cell.content}
            language={props.cell.cell_type === 'sql' ? 'sql' : 'markdown'}
            onChange={props.onContentChange}
            onBlur={handleBlur}
            onExecute={props.onExecute}
          />
        </Show>

        <Show when={props.cell.output && props.cell.cell_type === 'sql'}>
          <CellOutput output={props.cell.output!} />
        </Show>
      </div>
    </div>
  );
};
```

---

## 8. Integration with DataEngine

### Query Execution Flow

```
┌──────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│   EditorEngine   │     │   Tauri IPC     │     │   DataEngine     │
│   (Frontend)     │     │   (Bridge)      │     │   (Backend)      │
└────────┬─────────┘     └────────┬────────┘     └────────┬─────────┘
         │                        │                       │
         │  invoke('execute_cell')│                       │
         │───────────────────────>│                       │
         │                        │  execute_query(sql)   │
         │                        │──────────────────────>│
         │                        │                       │
         │                        │      ┌────────────────┴───────────┐
         │                        │      │ 1. Parse SQL               │
         │                        │      │ 2. Execute on DuckDB       │
         │                        │      │ 3. Format results          │
         │                        │      │ 4. Handle errors           │
         │                        │      └────────────────┬───────────┘
         │                        │                       │
         │                        │   Result<CellOutput>  │
         │                        │<──────────────────────│
         │   CellOutput           │                       │
         │<───────────────────────│                       │
         │                        │                       │
         │  ┌──────────────────┐  │                       │
         │  │ Update cell state│  │                       │
         │  │ Render output    │  │                       │
         │  └──────────────────┘  │                       │
         │                        │                       │
```

### Backend Execution Handler

```rust
use crate::data_engine::DataEngine;

#[tauri::command]
pub async fn execute_cell(
    cell_id: String,
    sql: String,
    state: State<'_, AppState>,
) -> Result<CellOutput, String> {
    let start = std::time::Instant::now();
    
    // Get DataEngine from app state
    let engine = state.data_engine.lock().await;
    
    // Execute query
    match engine.execute_query(&sql).await {
        Ok(result) => {
            let duration = start.elapsed().as_millis() as u64;
            
            // Convert to CellOutput
            Ok(CellOutput::Table {
                columns: result.columns.iter().map(|c| ColumnInfo {
                    name: c.name.clone(),
                    data_type: c.data_type.clone(),
                }).collect(),
                rows: result.rows,
                row_count: result.total_rows,
                truncated: result.truncated,
            })
        }
        Err(e) => {
            Ok(CellOutput::Error {
                message: e.to_string(),
                details: e.source().map(|s| s.to_string()),
            })
        }
    }
}
```

---

## 9. State Management

### SolidJS Store Structure

```typescript
import { createStore, produce } from 'solid-js/store';

interface NotebookState {
  path: string | null;
  cells: Cell[];
  executionCounter: number;
  focusedCellId: string | null;
  dirty: boolean;
  schema: SchemaInfo | null;
}

export function createNotebookStore() {
  const [state, setState] = createStore<NotebookState>({
    path: null,
    cells: [createNewCell('sql')],
    executionCounter: 0,
    focusedCellId: null,
    dirty: false,
    schema: null,
  });

  return {
    // Getters
    get cells() { return state.cells; },
    get focusedCell() {
      return state.cells.find(c => c.id === state.focusedCellId);
    },
    get isDirty() { return state.dirty; },

    // Cell operations
    addCell(type: CellType, index?: number) {
      const cell = createNewCell(type);
      setState(produce(s => {
        const idx = index ?? s.cells.length;
        s.cells.splice(idx, 0, cell);
        s.focusedCellId = cell.id;
        s.dirty = true;
      }));
      return cell.id;
    },

    addCellBelow(type: CellType) {
      const currentIdx = state.cells.findIndex(
        c => c.id === state.focusedCellId
      );
      return this.addCell(type, currentIdx + 1);
    },

    deleteCell(id: string) {
      setState(produce(s => {
        const idx = s.cells.findIndex(c => c.id === id);
        if (idx !== -1 && s.cells.length > 1) {
          s.cells.splice(idx, 1);
          // Focus adjacent cell
          s.focusedCellId = s.cells[Math.min(idx, s.cells.length - 1)]?.id;
          s.dirty = true;
        }
      }));
    },

    updateCell(id: string, updates: Partial<Cell>) {
      setState(produce(s => {
        const cell = s.cells.find(c => c.id === id);
        if (cell) {
          Object.assign(cell, updates);
          if ('content' in updates) {
            s.dirty = true;
          }
        }
      }));
    },

    moveCell(id: string, direction: 'up' | 'down') {
      setState(produce(s => {
        const idx = s.cells.findIndex(c => c.id === id);
        const newIdx = direction === 'up' ? idx - 1 : idx + 1;
        if (newIdx >= 0 && newIdx < s.cells.length) {
          [s.cells[idx], s.cells[newIdx]] = [s.cells[newIdx], s.cells[idx]];
          s.dirty = true;
        }
      }));
    },

    // Focus management
    focusCell(id: string) {
      setState('focusedCellId', id);
    },

    focusNextCell() {
      const idx = state.cells.findIndex(c => c.id === state.focusedCellId);
      if (idx < state.cells.length - 1) {
        setState('focusedCellId', state.cells[idx + 1].id);
      }
    },

    focusPreviousCell() {
      const idx = state.cells.findIndex(c => c.id === state.focusedCellId);
      if (idx > 0) {
        setState('focusedCellId', state.cells[idx - 1].id);
      }
    },

    // Execution
    incrementExecutionCounter(): number {
      setState('executionCounter', c => c + 1);
      return state.executionCounter;
    },

    // Schema
    setSchema(schema: SchemaInfo) {
      setState('schema', schema);
    },

    // Persistence
    markSaved(path: string) {
      setState({ path, dirty: false });
    },

    loadNotebook(notebook: Notebook) {
      setState({
        path: notebook.path,
        cells: notebook.cells,
        executionCounter: notebook.execution_counter,
        focusedCellId: notebook.cells[0]?.id ?? null,
        dirty: false,
      });
    },
  };
}
```

---

## 10. Acceptance Criteria

### Cell Management

- [ ] **AC-1.1:** Users can create new SQL cells via toolbar button or `Ctrl+Shift+B`
- [ ] **AC-1.2:** Users can create new Markdown cells via toolbar or `Ctrl+Shift+M`
- [ ] **AC-1.3:** Users can delete cells with confirmation if cell has content
- [ ] **AC-1.4:** Users can reorder cells via drag-and-drop or keyboard shortcuts
- [ ] **AC-1.5:** Cell deletion is prevented when only one cell remains

### SQL Editing

- [ ] **AC-2.1:** Monaco editor displays SQL with proper syntax highlighting
- [ ] **AC-2.2:** `Ctrl+Enter` executes the current SQL cell
- [ ] **AC-2.3:** Autocomplete suggests table names after `FROM` or `JOIN`
- [ ] **AC-2.4:** Autocomplete suggests column names after `tablename.`
- [ ] **AC-2.5:** SQL keywords are suggested with proper case
- [ ] **AC-2.6:** Execution count displays in cell gutter (e.g., `[1]`, `[2]`)

### Markdown Support

- [ ] **AC-3.1:** Markdown cells render to formatted HTML in view mode
- [ ] **AC-3.2:** Double-click on rendered Markdown enters edit mode
- [ ] **AC-3.3:** Clicking outside Markdown cell exits edit mode and re-renders
- [ ] **AC-3.4:** Tables, code blocks, and lists render correctly
- [ ] **AC-3.5:** HTML in Markdown is sanitized to prevent XSS

### Execution

- [ ] **AC-4.1:** Running cells display a spinner/loading indicator
- [ ] **AC-4.2:** Successful execution displays results in tabular format
- [ ] **AC-4.3:** Failed execution displays error message with details
- [ ] **AC-4.4:** `Shift+Enter` executes current cell and advances to next
- [ ] **AC-4.5:** `Ctrl+Shift+Enter` executes all cells in order

### Keyboard Navigation

- [ ] **AC-5.1:** Arrow keys navigate between cells when not editing
- [ ] **AC-5.2:** `Enter` enters edit mode on selected cell
- [ ] **AC-5.3:** `Escape` exits edit mode and selects cell
- [ ] **AC-5.4:** All documented shortcuts function as specified

### Performance

- [ ] **AC-6.1:** Editor loads in under 500ms
- [ ] **AC-6.2:** Autocomplete suggestions appear within 100ms
- [ ] **AC-6.3:** Cell operations (add/delete/move) complete in under 50ms
- [ ] **AC-6.4:** Notebook with 50+ cells remains responsive

### Persistence

- [ ] **AC-7.1:** Notebooks save to `.audit` JSON file format
- [ ] **AC-7.2:** Notebooks load with all cells and outputs restored
- [ ] **AC-7.3:** Unsaved changes trigger confirmation on close
- [ ] **AC-7.4:** Dirty indicator shows when notebook has unsaved changes

---

## 11. File Format

### Notebook File Structure (`.audit`)

```json
{
  "version": "1.0",
  "metadata": {
    "title": "FCPS Admin Analysis",
    "description": "Administrative overhead analysis for Frederick County",
    "created_at": 1706745600000,
    "modified_at": 1706832000000,
    "data_sources": [
      "data/processed/vdoe/table15_expenditures.json",
      "data/processed/vdoe/table18_admin_personnel.json"
    ]
  },
  "cells": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "cell_type": "markdown",
      "content": "# Analysis Title\n\nDescription here.",
      "execution_state": "idle",
      "output": {
        "type": "Markdown",
        "data": { "html": "<h1>Analysis Title</h1><p>Description here.</p>" }
      }
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "cell_type": "sql",
      "content": "SELECT * FROM expenditures LIMIT 10;",
      "execution_state": "success",
      "execution_count": 1,
      "last_executed": 1706832000000,
      "output": {
        "type": "Table",
        "data": {
          "columns": [{"name": "division", "data_type": "VARCHAR"}],
          "rows": [["Frederick County"]],
          "row_count": 1,
          "truncated": false
        }
      }
    }
  ],
  "execution_counter": 1
}
```

---

## 12. Dependencies

### Frontend (TypeScript)

```json
{
  "dependencies": {
    "monaco-editor": "^0.45.0",
    "solid-js": "^1.8.0",
    "@tauri-apps/api": "^2.0.0",
    "@solid-primitives/keyboard": "^1.2.0"
  }
}
```

### Backend (Rust)

```toml
[dependencies]
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
uuid = { version = "1.0", features = ["v4", "serde"] }
pulldown-cmark = "0.9"
ammonia = "3.3"
tauri = { version = "2.0", features = ["api-all"] }
```

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-31 | - | Initial specification |
