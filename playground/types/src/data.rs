//! DataEngine types for SQL queries and data loading

use serde::{Deserialize, Serialize};
use tsify::Tsify;

/// Request to load a data file
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct LoadRequest {
    /// Unique name for the table
    pub name: String,
    /// URL to the Parquet file
    pub url: String,
}

/// Result of loading a file
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct LoadResult {
    /// Table name
    pub name: String,
    /// Number of rows loaded
    pub row_count: u64,
    /// Schema information
    pub schema: TableSchema,
}

/// Request to execute a SQL query
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct QueryRequest {
    /// SQL query string
    pub sql: String,
    /// Maximum rows to return (default: 10000)
    #[serde(default = "default_limit")]
    pub limit: u32,
}

fn default_limit() -> u32 {
    10000
}

/// Result of a SQL query
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct QueryResult {
    /// Column metadata
    pub columns: Vec<ColumnSchema>,
    /// Row data as JSON values
    pub rows: Vec<Vec<serde_json::Value>>,
    /// Total rows in result (before limit)
    pub total_rows: u64,
    /// Whether result was truncated
    pub truncated: bool,
}

/// Request to get table schema
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct SchemaRequest {
    /// Table name
    pub table: String,
}

/// Table schema information
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct TableSchema {
    /// Table name
    pub name: String,
    /// Column definitions
    pub columns: Vec<ColumnSchema>,
    /// Estimated row count
    pub row_count: u64,
}

/// Column metadata
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ColumnSchema {
    /// Column name
    pub name: String,
    /// Data type
    pub data_type: ColumnType,
    /// Whether column can be null
    pub nullable: bool,
}

/// SQL data types
#[derive(Tsify, Serialize, Deserialize, Clone, Debug, PartialEq)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub enum ColumnType {
    /// Boolean
    Boolean,
    /// 8-bit integer
    Int8,
    /// 16-bit integer
    Int16,
    /// 32-bit integer
    Int32,
    /// 64-bit integer
    Int64,
    /// 32-bit float
    Float32,
    /// 64-bit float
    Float64,
    /// UTF-8 string
    String,
    /// Binary data
    Binary,
    /// Date (days since epoch)
    Date,
    /// Timestamp with timezone
    Timestamp,
    /// JSON object
    Json,
    /// Unknown type
    Unknown,
}

/// Request to list all loaded tables
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ListTablesRequest {}

/// List of loaded tables
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ListTablesResult {
    /// Table schemas
    pub tables: Vec<TableSchema>,
}

/// All DataEngine request types
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(tag = "type")]
pub enum DataRequest {
    #[serde(rename = "load")]
    Load(LoadRequest),
    #[serde(rename = "query")]
    Query(QueryRequest),
    #[serde(rename = "schema")]
    Schema(SchemaRequest),
    #[serde(rename = "list_tables")]
    ListTables(ListTablesRequest),
}

/// All DataEngine response types
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(tag = "type")]
pub enum DataResponse {
    #[serde(rename = "load")]
    Load(LoadResult),
    #[serde(rename = "query")]
    Query(QueryResult),
    #[serde(rename = "schema")]
    Schema(TableSchema),
    #[serde(rename = "list_tables")]
    ListTables(ListTablesResult),
}

/// Available data files
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct DataFile {
    /// Display name
    pub name: String,
    /// File path relative to data directory
    pub path: String,
    /// File size in bytes
    pub size: u64,
    /// Category for grouping
    pub category: String,
    /// Whether file is large (>10MB)
    pub large: bool,
}

/// Data file manifest
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct DataManifest {
    /// Available files
    pub files: Vec<DataFile>,
    /// Base URL for files
    pub base_url: String,
}
