//! DataEngine - DuckDB-WASM integration for SQL queries
//!
//! This crate provides a WASM-compatible interface to DuckDB for executing
//! SQL queries against Parquet data files.

use wasm_bindgen::prelude::*;

// Re-export types
pub use playground_types::data::*;

/// Initialize the data engine
#[wasm_bindgen(start)]
pub fn init() {
    // Set up panic hook for better error messages
    console_error_panic_hook::set_once();

    // Initialize logging
    console_log::init_with_level(log::Level::Debug).ok();

    log::info!("DataEngine initialized");
}

// TODO: Implement DuckDB-WASM integration
// - Load Parquet files
// - Execute SQL queries
// - Return typed results
