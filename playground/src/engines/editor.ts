/**
 * EditorEngine - Monaco editor integration for SQL editing
 * 
 * Provides syntax highlighting, dark theme, and keyboard shortcuts for SQL queries.
 */

import * as monaco from 'monaco-editor';

// Monaco editor instance
let editor: monaco.editor.IStandaloneCodeEditor | null = null;
let executeCallback: ((sql: string) => void) | null = null;
let changeCallback: ((sql: string) => void) | null = null;

// SQL keywords for autocomplete
const SQL_KEYWORDS = [
  'SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'FULL', 'CROSS',
  'ON', 'AND', 'OR', 'NOT', 'IN', 'LIKE', 'BETWEEN', 'IS', 'NULL', 'TRUE', 'FALSE',
  'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT', 'OFFSET', 'AS', 'DISTINCT', 'ALL',
  'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
  'UNION', 'EXCEPT', 'INTERSECT', 'WITH', 'INSERT', 'INTO', 'VALUES', 'UPDATE', 'SET', 'DELETE',
  'CREATE', 'TABLE', 'VIEW', 'DROP', 'ALTER', 'INDEX', 'PRIMARY', 'KEY', 'FOREIGN', 'REFERENCES',
  'ASC', 'DESC', 'NULLS', 'FIRST', 'LAST', 'OVER', 'PARTITION', 'WINDOW', 'ROWS', 'RANGE',
  'CAST', 'COALESCE', 'NULLIF', 'EXISTS', 'ANY', 'SOME', 'USING', 'NATURAL',
];

// DuckDB-specific functions
const DUCKDB_FUNCTIONS = [
  'parquet_scan', 'read_parquet', 'read_csv', 'read_json',
  'strftime', 'date_part', 'date_trunc', 'now', 'current_date', 'current_timestamp',
  'substr', 'length', 'upper', 'lower', 'trim', 'ltrim', 'rtrim', 'replace', 'concat',
  'round', 'floor', 'ceil', 'abs', 'sqrt', 'power', 'log', 'ln', 'exp',
  'row_number', 'rank', 'dense_rank', 'ntile', 'lag', 'lead', 'first_value', 'last_value',
  'array_agg', 'string_agg', 'list', 'struct', 'map',
  'typeof', 'describe',
];

/**
 * Define the custom dark theme for the editor
 */
function defineAuditDarkTheme(): void {
  monaco.editor.defineTheme('audit-dark', {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'keyword', foreground: '569CD6', fontStyle: 'bold' },
      { token: 'keyword.sql', foreground: '569CD6', fontStyle: 'bold' },
      { token: 'string', foreground: 'CE9178' },
      { token: 'string.sql', foreground: 'CE9178' },
      { token: 'number', foreground: 'B5CEA8' },
      { token: 'number.sql', foreground: 'B5CEA8' },
      { token: 'comment', foreground: '6A9955', fontStyle: 'italic' },
      { token: 'comment.sql', foreground: '6A9955', fontStyle: 'italic' },
      { token: 'operator', foreground: 'D4D4D4' },
      { token: 'operator.sql', foreground: 'D4D4D4' },
      { token: 'identifier', foreground: '9CDCFE' },
      { token: 'identifier.sql', foreground: '9CDCFE' },
      { token: 'type', foreground: '4EC9B0' },
      { token: 'predefined', foreground: '4EC9B0' },
      { token: 'predefined.sql', foreground: '4EC9B0' },
    ],
    colors: {
      'editor.background': '#1a1a2e',
      'editor.foreground': '#D4D4D4',
      'editor.lineHighlightBackground': '#2D2D4A',
      'editor.selectionBackground': '#264F78',
      'editorCursor.foreground': '#FFFFFF',
      'editorLineNumber.foreground': '#858585',
      'editorLineNumber.activeForeground': '#C6C6C6',
      'editor.inactiveSelectionBackground': '#3A3D41',
      'editorWidget.background': '#16213e',
      'editorWidget.border': '#333',
      'editorSuggestWidget.background': '#16213e',
      'editorSuggestWidget.border': '#333',
      'editorSuggestWidget.selectedBackground': '#0f3460',
      'editorSuggestWidget.highlightForeground': '#00d9ff',
    },
  });
}

/**
 * Register SQL completion provider with table/column awareness
 */
function registerCompletionProvider(getSchema: () => Promise<{ tables: { name: string; columns: { name: string; type: string }[] }[] }>): void {
  monaco.languages.registerCompletionItemProvider('sql', {
    triggerCharacters: ['.', ' '],
    
    provideCompletionItems: async (model, position) => {
      const word = model.getWordUntilPosition(position);
      const range: monaco.IRange = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: word.startColumn,
        endColumn: word.endColumn,
      };

      const suggestions: monaco.languages.CompletionItem[] = [];

      // Check if we're after a table reference (for column suggestions)
      const lineContent = model.getLineContent(position.lineNumber);
      const beforeCursor = lineContent.substring(0, position.column - 1);
      const tableMatch = beforeCursor.match(/(\w+)\.\s*$/);

      if (tableMatch) {
        // Column completion after "table."
        try {
          const schema = await getSchema();
          const tableName = tableMatch[1].toLowerCase();
          const table = schema.tables.find(t => t.name.toLowerCase() === tableName);
          
          if (table) {
            for (const column of table.columns) {
              suggestions.push({
                label: column.name,
                kind: monaco.languages.CompletionItemKind.Field,
                insertText: column.name,
                detail: column.type,
                range,
              });
            }
          }
        } catch {
          // Schema not available, skip column suggestions
        }
      } else {
        // Add SQL keywords
        for (const keyword of SQL_KEYWORDS) {
          suggestions.push({
            label: keyword,
            kind: monaco.languages.CompletionItemKind.Keyword,
            insertText: keyword,
            range,
          });
        }

        // Add DuckDB functions
        for (const func of DUCKDB_FUNCTIONS) {
          suggestions.push({
            label: func,
            kind: monaco.languages.CompletionItemKind.Function,
            insertText: func + '($0)',
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            detail: 'DuckDB function',
            range,
          });
        }

        // Add table suggestions
        try {
          const schema = await getSchema();
          for (const table of schema.tables) {
            suggestions.push({
              label: table.name,
              kind: monaco.languages.CompletionItemKind.Class,
              insertText: table.name,
              detail: `Table (${table.columns.length} columns)`,
              range,
            });
          }
        } catch {
          // Schema not available, skip table suggestions
        }
      }

      return { suggestions };
    },
  });
}

/**
 * EditorEngine class for managing Monaco editor instances
 */
export class EditorEngine {
  private schemaProvider: (() => Promise<{ tables: { name: string; columns: { name: string; type: string }[] }[] }>) | null = null;
  private initialized = false;

  /**
   * Initialize the editor engine with optional schema provider for autocomplete
   */
  async init(schemaProvider?: () => Promise<{ tables: { name: string; columns: { name: string; type: string }[] }[] }>): Promise<void> {
    if (this.initialized) return;
    
    this.schemaProvider = schemaProvider || (async () => ({ tables: [] }));
    
    // Define custom theme
    defineAuditDarkTheme();
    
    // Register completion provider
    registerCompletionProvider(this.schemaProvider);
    
    this.initialized = true;
    console.log('[EditorEngine] Initialized');
  }

  /**
   * Create a Monaco editor in the specified container
   */
  createEditor(containerId: string, initialValue = ''): void {
    const container = document.getElementById(containerId);
    if (!container) {
      throw new Error(`Container element '${containerId}' not found`);
    }

    // Dispose existing editor if any
    if (editor) {
      editor.dispose();
    }

    // Create the editor
    editor = monaco.editor.create(container, {
      value: initialValue,
      language: 'sql',
      theme: 'audit-dark',
      
      // Display options
      fontSize: 14,
      fontFamily: "'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code', monospace",
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
      glyphMargin: false,
      folding: false,
      
      // Suggestions
      suggestOnTriggerCharacters: true,
      quickSuggestions: {
        other: true,
        comments: false,
        strings: true,
      },
      acceptSuggestionOnEnter: 'smart',
      tabCompletion: 'on',
      
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
      
      // Padding
      padding: {
        top: 8,
        bottom: 8,
      },
    });

    // Register Ctrl+Enter handler
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => {
      if (executeCallback) {
        executeCallback(this.getValue());
      }
    });

    // Register content change handler (debounced)
    let changeTimeout: ReturnType<typeof setTimeout> | null = null;
    editor.onDidChangeModelContent(() => {
      if (changeCallback) {
        // Debounce to avoid excessive calls
        if (changeTimeout !== null) {
          clearTimeout(changeTimeout);
        }
        const cb = changeCallback; // Capture callback
        changeTimeout = setTimeout(() => {
          cb(this.getValue());
        }, 150);
      }
    });

    console.log('[EditorEngine] Editor created in', containerId);
  }

  /**
   * Get the current editor value
   */
  getValue(): string {
    return editor?.getValue() ?? '';
  }

  /**
   * Set the editor value
   */
  setValue(value: string): void {
    editor?.setValue(value);
  }

  /**
   * Register a callback for Ctrl+Enter execution
   */
  onExecute(callback: (sql: string) => void): void {
    executeCallback = callback;
  }

  /**
   * Register a callback for content changes (debounced)
   */
  onChange(callback: (sql: string) => void): void {
    changeCallback = callback;
  }

  /**
   * Focus the editor
   */
  focus(): void {
    editor?.focus();
  }

  /**
   * Get the editor instance (for advanced use cases)
   */
  getEditor(): monaco.editor.IStandaloneCodeEditor | null {
    return editor;
  }

  /**
   * Dispose the editor
   */
  dispose(): void {
    if (editor) {
      editor.dispose();
      editor = null;
    }
    executeCallback = null;
    changeCallback = null;
    console.log('[EditorEngine] Disposed');
  }
}

// Export singleton instance
export const editorEngine = new EditorEngine();

// Export for direct use
export { monaco };
