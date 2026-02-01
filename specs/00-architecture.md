# 00 - Architecture Specification

## Overview

The Data Playground is a browser-based analytics environment for exploring Frederick County public data. It provides SQL querying, visualization, and collaborative note-taking capabilities.

## Design Principles

1. **Type Safety**: Rust defines all shared types; TypeScript bindings are auto-generated
2. **Loose Coupling**: Components communicate only via typed messages
3. **Performance**: Heavy computation in WASM workers; UI stays responsive
4. **Data Efficiency**: Parquet for analytics; JSON for interop/download
5. **Open Collaboration**: Nostr-based public notes for community insights

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           UI Shell                                   │
│                  (TypeScript - Thin Orchestrator)                    │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │Data Tab │ │SQL Tab  │ │Chart Tab│ │Notes Tab│ │Settings │       │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘       │
└────────────────────────────┬────────────────────────────────────────┘
                             │
              ╔══════════════╧══════════════╗
              ║      Message Bus (TS)       ║
              ║   Type-safe pub/sub system  ║
              ╚══════════════╤══════════════╝
                             │
    ┌────────────┬───────────┼───────────┬────────────┬────────────┐
    ▼            ▼           ▼           ▼            ▼            ▼
┌────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ Data   │ │ Chart   │ │ Editor  │ │ Notes   │ │ Storage │ │ Export  │
│ Engine │ │ Engine  │ │ Engine  │ │ Engine  │ │ Engine  │ │ Engine  │
│ (WASM) │ │  (TS)   │ │ (Monaco)│ │ (Nostr) │ │(IndexDB)│ │  (TS)   │
│ Worker │ │         │ │         │ │         │ │         │ │         │
└────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
```

## Shared Type System

All types are defined in Rust and exported to TypeScript via `wasm-bindgen` + `tsify`.

### Core Message Protocol

```rust
// Defined in: playground/types/src/messages.rs

use serde::{Serialize, Deserialize};
use tsify::Tsify;

/// Unique identifier for message correlation
pub type MessageId = String;

/// Base message envelope for all inter-component communication
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct Message<T> {
    /// Unique message ID for request/response matching
    pub id: MessageId,
    /// Timestamp (Unix ms)
    pub timestamp: u64,
    /// Message payload
    pub payload: T,
}

/// Result wrapper for all responses
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(tag = "status")]
pub enum MessageResult<T> {
    #[serde(rename = "ok")]
    Ok { data: T },
    #[serde(rename = "error")]
    Error { code: ErrorCode, message: String },
}

#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub enum ErrorCode {
    NotFound,
    InvalidQuery,
    ParseError,
    NetworkError,
    StorageError,
    AuthError,
    Unknown,
}
```

### Component Message Types

Each component defines its own message types that implement the base protocol:

| Component | Request Types | Response Types |
|-----------|---------------|----------------|
| DataEngine | `LoadRequest`, `QueryRequest`, `SchemaRequest` | `LoadResult`, `QueryResult`, `SchemaResult` |
| ChartEngine | `RenderRequest`, `ExportRequest` | `RenderResult`, `ExportResult` |
| EditorEngine | `ExecuteRequest`, `FormatRequest` | `ExecuteResult`, `FormatResult` |
| NotesEngine | `PublishRequest`, `FetchRequest` | `PublishResult`, `FetchResult` |
| StorageEngine | `SaveRequest`, `LoadRequest`, `ClearRequest` | `SaveResult`, `LoadResult`, `ClearResult` |
| ExportEngine | `ExportDataRequest`, `ExportNotebookRequest` | `ExportResult` |

## Data Flow

### 1. Loading Data

```
User clicks file → UI Shell
    → Message{LoadRequest} → DataEngine Worker
    → Fetch Parquet from GitHub
    → Register table in DuckDB
    → Message{LoadResult} → UI Shell
    → Update sidebar (file loaded indicator)
```

### 2. Running Query

```
User writes SQL → EditorEngine
    → Message{ExecuteRequest} → DataEngine Worker  
    → DuckDB executes query
    → Message{QueryResult} → UI Shell
    → Display in results table
    → Optional: Message{RenderRequest} → ChartEngine
```

### 3. Publishing Note

```
User writes note → EditorEngine (Markdown cell)
    → Message{PublishRequest} → NotesEngine
    → Sign with Nostr key (NIP-07/manual/NIP-46)
    → Publish to relays with hashtags
    → Message{PublishResult} → UI Shell
    → Show confirmation + note ID
```

## File Structure

```
playground/
├── Cargo.toml                 # Rust workspace
├── types/                     # Shared Rust types
│   ├── Cargo.toml
│   └── src/
│       ├── lib.rs
│       ├── messages.rs        # Base message types
│       ├── data.rs            # DataEngine types
│       ├── chart.rs           # ChartEngine types
│       ├── editor.rs          # EditorEngine types
│       ├── notes.rs           # NotesEngine types
│       └── storage.rs         # StorageEngine types
├── data-engine/               # DuckDB WASM worker
│   ├── Cargo.toml
│   └── src/
│       └── lib.rs
├── pkg/                       # WASM build output
├── src/                       # TypeScript source
│   ├── index.ts               # Entry point
│   ├── shell.ts               # UI Shell
│   ├── message-bus.ts         # Pub/sub system
│   ├── engines/
│   │   ├── data.ts            # DataEngine JS wrapper
│   │   ├── chart.ts           # ChartEngine
│   │   ├── editor.ts          # EditorEngine
│   │   ├── notes.ts           # NotesEngine
│   │   ├── storage.ts         # StorageEngine
│   │   └── export.ts          # ExportEngine
│   └── components/
│       ├── tabs.ts
│       ├── sidebar.ts
│       ├── results-table.ts
│       └── chart-builder.ts
├── dist/                      # Build output
└── package.json
```

## Technology Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| Types | Rust + tsify | 1.75+ | Type definitions, WASM bindings |
| SQL Engine | DuckDB-WASM | 1.29+ | Parquet queries, analytics |
| Editor | Monaco | 0.45+ | SQL + Markdown editing |
| Charts | Chart.js + chartjs-plugin-* | 4.4+ | All visualizations |
| Maps | Leaflet | 1.9+ | Choropleth district maps |
| Nostr | nostr-tools | 2.0+ | Note publishing, key management |
| Storage | IndexedDB (idb) | 8.0+ | Caching, notebook persistence |
| Build | Vite + wasm-pack | 5.0+ | Bundling |

## Data Formats

### Source Data (GitHub Hosted)

| File | Format | Size | Notes |
|------|--------|------|-------|
| `real_estate_tax.parquet` | Parquet | ~30-50 MB | Converted from 212 MB JSON |
| `ownership_analysis.parquet` | Parquet | ~50 KB | From 340 KB JSON |
| `districts.parquet` | Parquet | ~100 KB | GeoJSON converted |
| `*.json` | JSON | Various | Available for download |

### Notebook Format (Save/Load)

```json
{
  "version": 2,
  "created": "2026-01-31T12:00:00Z",
  "modified": "2026-01-31T14:30:00Z",
  "metadata": {
    "title": "LLC Ownership Analysis",
    "author": "npub1...",
    "tags": ["fredco", "property", "llc"]
  },
  "cells": [
    {
      "id": "cell-1",
      "type": "markdown",
      "content": "# Analysis of LLC Property Ownership\n\nThis notebook explores...",
      "created": "2026-01-31T12:00:00Z"
    },
    {
      "id": "cell-2", 
      "type": "sql",
      "content": "SELECT entity_type, COUNT(*) FROM tax GROUP BY 1",
      "output": { "columns": [...], "rows": [...] },
      "executionTime": 45,
      "created": "2026-01-31T12:05:00Z"
    }
  ],
  "loadedData": ["real_estate_tax", "districts"],
  "charts": [
    {
      "id": "chart-1",
      "type": "bar",
      "sourceCell": "cell-2",
      "config": { ... }
    }
  ]
}
```

## Nostr Integration

### Event Kinds

| Kind | Purpose | Tags |
|------|---------|------|
| 1 | Short note (comment) | `#fredco-data`, `#[dataset]` |
| 30023 | Long-form article (analysis) | `d:[notebook-id]`, `#fredco-data` |

### NIP-05 Verification

Users with `@virginiafreedom.tech` NIP-05 identifiers are considered "verified contributors". Others are prompted to contact Shenandoah Bitcoin Club for activation.

### Key Management Options

1. **NIP-07**: Browser extension (nos2x, Alby, etc.)
2. **NIP-46**: Remote signer (Nostr Connect)
3. **Manual nsec**: Direct key entry (advanced)
4. **Ephemeral**: Generated per-session (anonymous)

Configuration stored in localStorage, synced via StorageEngine.

## Security Considerations

1. **WASM Sandbox**: DataEngine runs in Web Worker, isolated from DOM
2. **No Server State**: All processing client-side; GitHub serves static files
3. **Nostr Keys**: Never transmitted; signing happens locally
4. **CSP**: Strict Content-Security-Policy for production

## Performance Targets

| Metric | Target |
|--------|--------|
| Initial bundle load | < 5 MB gzipped |
| Time to interactive | < 3 seconds |
| Query (1M rows) | < 500 ms |
| Chart render | < 100 ms |
| Note publish | < 2 seconds |

## Build & Deploy

```bash
# Development
cd playground
npm install
npm run dev

# Build
npm run build:wasm   # Compile Rust to WASM
npm run build        # Bundle everything

# Deploy (GitHub Pages)
npm run deploy
```

Output: Single `playground.html` + `assets/` directory with all chunks.
