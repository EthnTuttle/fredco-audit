//! EditorEngine types for notebook cells

use crate::messages::Timestamp;
use serde::{Deserialize, Serialize};
use tsify::Tsify;

/// Cell type
#[derive(Tsify, Serialize, Deserialize, Clone, Debug, PartialEq)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub enum CellType {
    /// SQL query cell
    Sql,
    /// Markdown documentation cell
    Markdown,
}

/// Execution state
#[derive(Tsify, Serialize, Deserialize, Clone, Debug, PartialEq)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub enum ExecutionState {
    /// Not executed
    Idle,
    /// Currently running
    Running,
    /// Completed successfully
    Success,
    /// Completed with error
    Error,
}

/// A notebook cell
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct Cell {
    /// Unique cell ID
    pub id: String,
    /// Cell type
    pub cell_type: CellType,
    /// Cell content (SQL or Markdown)
    pub content: String,
    /// Cell output (query results, rendered markdown, or error)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output: Option<CellOutput>,
    /// Execution state
    #[serde(default)]
    pub state: ExecutionState,
    /// Execution number (for ordering)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub execution_count: Option<u32>,
    /// Creation timestamp
    pub created_at: Timestamp,
    /// Last modified timestamp
    pub modified_at: Timestamp,
    /// Whether cell is collapsed
    #[serde(default)]
    pub collapsed: bool,
}

impl Default for ExecutionState {
    fn default() -> Self {
        ExecutionState::Idle
    }
}

/// Cell output
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(tag = "type")]
pub enum CellOutput {
    /// Query result
    #[serde(rename = "query")]
    Query(QueryOutput),
    /// Rendered markdown
    #[serde(rename = "markdown")]
    Markdown(MarkdownOutput),
    /// Error output
    #[serde(rename = "error")]
    Error(ErrorOutput),
}

/// Query output
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct QueryOutput {
    /// Column names
    pub columns: Vec<String>,
    /// Row data as JSON
    pub rows: Vec<Vec<serde_json::Value>>,
    /// Total row count (before limit)
    pub total_rows: u64,
    /// Execution time in ms
    pub execution_time_ms: u32,
    /// Whether result was truncated
    pub truncated: bool,
}

/// Rendered markdown output
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct MarkdownOutput {
    /// Rendered HTML
    pub html: String,
}

/// Error output
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ErrorOutput {
    /// Error message
    pub message: String,
    /// Optional stack trace or details
    #[serde(skip_serializing_if = "Option::is_none")]
    pub details: Option<String>,
}

/// Notebook document
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct Notebook {
    /// Format version
    pub version: u32,
    /// Notebook metadata
    pub metadata: NotebookMetadata,
    /// Cells in order
    pub cells: Vec<Cell>,
    /// Loaded data files
    pub loaded_data: Vec<String>,
    /// Chart configurations
    #[serde(default)]
    pub charts: Vec<crate::chart::ChartConfig>,
}

/// Notebook metadata
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct NotebookMetadata {
    /// Notebook title
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title: Option<String>,
    /// Author (npub if signed)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub author: Option<String>,
    /// Tags for categorization
    #[serde(default)]
    pub tags: Vec<String>,
    /// Creation timestamp
    pub created_at: Timestamp,
    /// Last modified timestamp
    pub modified_at: Timestamp,
    /// Description
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
}

/// Execute cell request
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ExecuteCellRequest {
    /// Cell ID
    pub cell_id: String,
}

/// Add cell request
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct AddCellRequest {
    /// Cell type
    pub cell_type: CellType,
    /// Initial content
    #[serde(default)]
    pub content: String,
    /// Position (None = end)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub after_cell_id: Option<String>,
}

/// Delete cell request
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct DeleteCellRequest {
    /// Cell ID to delete
    pub cell_id: String,
}

/// Move cell request
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct MoveCellRequest {
    /// Cell ID to move
    pub cell_id: String,
    /// Direction (-1 = up, 1 = down)
    pub direction: i32,
}

/// Update cell content request
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct UpdateCellRequest {
    /// Cell ID
    pub cell_id: String,
    /// New content
    pub content: String,
}

/// Autocomplete request
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct AutocompleteRequest {
    /// Partial SQL text
    pub text: String,
    /// Cursor position
    pub cursor_position: u32,
}

/// Autocomplete suggestion
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct AutocompleteSuggestion {
    /// Display label
    pub label: String,
    /// Text to insert
    pub insert_text: String,
    /// Suggestion kind
    pub kind: SuggestionKind,
    /// Optional documentation
    #[serde(skip_serializing_if = "Option::is_none")]
    pub documentation: Option<String>,
}

/// Suggestion kind
#[derive(Tsify, Serialize, Deserialize, Clone, Debug, PartialEq)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub enum SuggestionKind {
    Table,
    Column,
    Function,
    Keyword,
}

/// Autocomplete result
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct AutocompleteResult {
    /// Suggestions
    pub suggestions: Vec<AutocompleteSuggestion>,
}
