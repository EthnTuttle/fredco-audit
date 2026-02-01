# DataEngine Component Specification

**Version:** 1.0  
**Status:** Draft  
**Last Updated:** 2026-01-31

---

## 1. Purpose

The DataEngine is the core data access layer for the FCPS audit application. It provides SQL query capabilities over Parquet data files using DuckDB-WASM, running entirely in the browser without server dependencies.

### 1.1 Responsibilities

- Load and register Parquet files from GitHub-hosted storage
- Execute SQL queries against registered tables
- Provide schema introspection for registered tables
- Manage table lifecycle (register, unregister, list)
- Run all operations in a Web Worker to prevent UI blocking
- Return strongly-typed results via message passing

### 1.2 Non-Responsibilities

- Data transformation/aggregation logic (handled by query layer)
- Caching strategies (handled by application layer)
- UI state management
- Network retry logic (handled by caller)

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Main Thread                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              DataEngineClient (TS)                    │  │
│  │  - Async API for queries                              │  │
│  │  - Request/response correlation                       │  │
│  │  - Type-safe message serialization                    │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                  │
│                          │ postMessage                      │
│                          ▼                                  │
├─────────────────────────────────────────────────────────────┤
│                      Web Worker                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              DataEngine (Rust/WASM)                   │  │
│  │  - Message dispatch                                   │  │
│  │  - DuckDB-WASM instance management                    │  │
│  │  - Query execution                                    │  │
│  │  - Schema introspection                               │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  DuckDB-WASM                          │  │
│  │  - SQL parsing and execution                          │  │
│  │  - Parquet file reading                               │  │
│  │  - In-memory table storage                            │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Rust Type Definitions

### 3.1 Core Types

```rust
use serde::{Deserialize, Serialize};
use tsify::Tsify;

/// Unique identifier for correlating requests with responses
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct RequestId(pub String);

/// Column data type enumeration
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ColumnType {
    Boolean,
    TinyInt,
    SmallInt,
    Integer,
    BigInt,
    Float,
    Double,
    Varchar,
    Date,
    Timestamp,
    Decimal,
    Blob,
    Unknown,
}

/// Schema definition for a single column
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(rename_all = "camelCase")]
pub struct ColumnSchema {
    pub name: String,
    pub column_type: ColumnType,
    pub nullable: bool,
}

/// Schema definition for a table
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(rename_all = "camelCase")]
pub struct TableSchema {
    pub table_name: String,
    pub columns: Vec<ColumnSchema>,
    pub row_count: Option<u64>,
}

/// Metadata about a registered table
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(rename_all = "camelCase")]
pub struct TableInfo {
    pub name: String,
    pub source_url: String,
    pub loaded_at: String,  // ISO 8601 timestamp
    pub row_count: u64,
    pub size_bytes: u64,
}

/// A single row of query results (column name -> JSON value)
pub type Row = std::collections::HashMap<String, serde_json::Value>;

/// Query execution results
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(rename_all = "camelCase")]
pub struct QueryResult {
    pub columns: Vec<ColumnSchema>,
    pub rows: Vec<Row>,
    pub row_count: u64,
    pub execution_time_ms: f64,
}
```

### 3.2 Request Types

```rust
/// All possible requests to the DataEngine
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(tag = "type", rename_all = "camelCase")]
pub enum DataEngineRequest {
    /// Initialize the DuckDB instance
    Initialize,
    
    /// Load a Parquet file and register it as a table
    #[serde(rename_all = "camelCase")]
    LoadTable {
        table_name: String,
        parquet_url: String,
    },
    
    /// Unregister and remove a table from memory
    #[serde(rename_all = "camelCase")]
    UnloadTable {
        table_name: String,
    },
    
    /// Execute a SQL query
    #[serde(rename_all = "camelCase")]
    Query {
        sql: String,
        /// Optional limit override (default: 10000)
        limit: Option<u32>,
    },
    
    /// Get schema for a specific table
    #[serde(rename_all = "camelCase")]
    GetSchema {
        table_name: String,
    },
    
    /// List all registered tables
    ListTables,
    
    /// Gracefully shutdown the engine
    Shutdown,
}

/// Wrapper including request ID for correlation
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(rename_all = "camelCase")]
pub struct DataEngineMessage {
    pub id: RequestId,
    pub request: DataEngineRequest,
}
```

### 3.3 Response Types

```rust
/// Error information returned on failure
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(rename_all = "camelCase")]
pub struct DataEngineError {
    pub code: ErrorCode,
    pub message: String,
    pub details: Option<String>,
}

/// Error code enumeration
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ErrorCode {
    /// DuckDB not yet initialized
    NotInitialized,
    /// Failed to fetch Parquet file
    FetchFailed,
    /// Invalid Parquet file format
    InvalidParquet,
    /// Table not found
    TableNotFound,
    /// Table already exists
    TableExists,
    /// SQL syntax error
    SqlSyntaxError,
    /// SQL execution error
    SqlExecutionError,
    /// Internal engine error
    InternalError,
}

/// All possible response payloads
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(tag = "type", rename_all = "camelCase")]
pub enum DataEngineResponsePayload {
    /// Initialization complete
    Initialized {
        version: String,
    },
    
    /// Table loaded successfully
    #[serde(rename_all = "camelCase")]
    TableLoaded {
        info: TableInfo,
    },
    
    /// Table unloaded successfully
    #[serde(rename_all = "camelCase")]
    TableUnloaded {
        table_name: String,
    },
    
    /// Query executed successfully
    #[serde(rename_all = "camelCase")]
    QueryResult {
        result: QueryResult,
    },
    
    /// Schema retrieved successfully
    #[serde(rename_all = "camelCase")]
    Schema {
        schema: TableSchema,
    },
    
    /// List of all tables
    #[serde(rename_all = "camelCase")]
    TableList {
        tables: Vec<TableInfo>,
    },
    
    /// Engine shutdown complete
    ShutdownComplete,
    
    /// Error response
    #[serde(rename_all = "camelCase")]
    Error {
        error: DataEngineError,
    },
}

/// Response wrapper including correlation ID
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(rename_all = "camelCase")]
pub struct DataEngineResponse {
    pub id: RequestId,
    pub payload: DataEngineResponsePayload,
}
```

---

## 4. Message Protocol

### 4.1 Communication Flow

```
Main Thread                          Web Worker
     │                                    │
     │  ──── DataEngineMessage ────────►  │
     │       { id, request }              │
     │                                    │
     │                              [process]
     │                                    │
     │  ◄──── DataEngineResponse ──────  │
     │        { id, payload }             │
     │                                    │
```

### 4.2 Request/Response Correlation

Every request includes a unique `RequestId` (UUID v4). The response echoes this ID back, allowing the client to correlate responses with pending requests.

### 4.3 Message Serialization

Messages are serialized as JSON via `serde_json`. The Web Worker receives and sends messages through the standard `postMessage` API.

---

## 5. TypeScript Client Wrapper

```typescript
import type {
  DataEngineMessage,
  DataEngineRequest,
  DataEngineResponse,
  DataEngineResponsePayload,
  QueryResult,
  TableInfo,
  TableSchema,
  DataEngineError,
} from './types';

type PendingRequest = {
  resolve: (payload: DataEngineResponsePayload) => void;
  reject: (error: DataEngineError) => void;
};

export class DataEngineClient {
  private worker: Worker;
  private pending: Map<string, PendingRequest> = new Map();
  private initialized: boolean = false;

  constructor() {
    this.worker = new Worker(
      new URL('./data-engine.worker.ts', import.meta.url),
      { type: 'module' }
    );
    
    this.worker.onmessage = (event: MessageEvent<DataEngineResponse>) => {
      this.handleResponse(event.data);
    };
    
    this.worker.onerror = (error) => {
      console.error('DataEngine worker error:', error);
    };
  }

  private generateId(): string {
    return crypto.randomUUID();
  }

  private send(request: DataEngineRequest): Promise<DataEngineResponsePayload> {
    return new Promise((resolve, reject) => {
      const id = this.generateId();
      
      this.pending.set(id, { resolve, reject });
      
      const message: DataEngineMessage = { id: { 0: id }, request };
      this.worker.postMessage(message);
    });
  }

  private handleResponse(response: DataEngineResponse): void {
    const id = response.id[0];
    const pending = this.pending.get(id);
    
    if (!pending) {
      console.warn('Received response for unknown request:', id);
      return;
    }
    
    this.pending.delete(id);
    
    if (response.payload.type === 'error') {
      pending.reject(response.payload.error);
    } else {
      pending.resolve(response.payload);
    }
  }

  /**
   * Initialize the DuckDB-WASM instance.
   * Must be called before any other operations.
   */
  async initialize(): Promise<string> {
    const response = await this.send({ type: 'initialize' });
    
    if (response.type !== 'initialized') {
      throw new Error('Unexpected response type');
    }
    
    this.initialized = true;
    return response.version;
  }

  /**
   * Load a Parquet file from a URL and register it as a table.
   */
  async loadTable(tableName: string, parquetUrl: string): Promise<TableInfo> {
    this.ensureInitialized();
    
    const response = await this.send({
      type: 'loadTable',
      tableName,
      parquetUrl,
    });
    
    if (response.type !== 'tableLoaded') {
      throw new Error('Unexpected response type');
    }
    
    return response.info;
  }

  /**
   * Unload a table from memory.
   */
  async unloadTable(tableName: string): Promise<void> {
    this.ensureInitialized();
    
    const response = await this.send({
      type: 'unloadTable',
      tableName,
    });
    
    if (response.type !== 'tableUnloaded') {
      throw new Error('Unexpected response type');
    }
  }

  /**
   * Execute a SQL query and return results.
   */
  async query(sql: string, limit?: number): Promise<QueryResult> {
    this.ensureInitialized();
    
    const response = await this.send({
      type: 'query',
      sql,
      limit: limit ?? null,
    });
    
    if (response.type !== 'queryResult') {
      throw new Error('Unexpected response type');
    }
    
    return response.result;
  }

  /**
   * Get the schema for a specific table.
   */
  async getSchema(tableName: string): Promise<TableSchema> {
    this.ensureInitialized();
    
    const response = await this.send({
      type: 'getSchema',
      tableName,
    });
    
    if (response.type !== 'schema') {
      throw new Error('Unexpected response type');
    }
    
    return response.schema;
  }

  /**
   * List all registered tables.
   */
  async listTables(): Promise<TableInfo[]> {
    this.ensureInitialized();
    
    const response = await this.send({ type: 'listTables' });
    
    if (response.type !== 'tableList') {
      throw new Error('Unexpected response type');
    }
    
    return response.tables;
  }

  /**
   * Gracefully shutdown the engine.
   */
  async shutdown(): Promise<void> {
    const response = await this.send({ type: 'shutdown' });
    
    if (response.type !== 'shutdownComplete') {
      throw new Error('Unexpected response type');
    }
    
    this.worker.terminate();
    this.initialized = false;
  }

  private ensureInitialized(): void {
    if (!this.initialized) {
      throw new Error('DataEngine not initialized. Call initialize() first.');
    }
  }
}
```

---

## 6. Web Worker Implementation Outline

```typescript
// data-engine.worker.ts
import initDuckDB, { Database } from '@aspect/duckdb-wasm';
import type { DataEngineMessage, DataEngineResponse } from './types';

let db: Database | null = null;
const tables: Map<string, { url: string; loadedAt: Date }> = new Map();

self.onmessage = async (event: MessageEvent<DataEngineMessage>) => {
  const { id, request } = event.data;
  
  try {
    const payload = await handleRequest(request);
    respond({ id, payload });
  } catch (error) {
    respond({
      id,
      payload: {
        type: 'error',
        error: {
          code: 'INTERNAL_ERROR',
          message: error instanceof Error ? error.message : 'Unknown error',
          details: null,
        },
      },
    });
  }
};

async function handleRequest(request: DataEngineRequest): Promise<DataEngineResponsePayload> {
  switch (request.type) {
    case 'initialize':
      return handleInitialize();
    case 'loadTable':
      return handleLoadTable(request.tableName, request.parquetUrl);
    case 'unloadTable':
      return handleUnloadTable(request.tableName);
    case 'query':
      return handleQuery(request.sql, request.limit);
    case 'getSchema':
      return handleGetSchema(request.tableName);
    case 'listTables':
      return handleListTables();
    case 'shutdown':
      return handleShutdown();
  }
}

function respond(response: DataEngineResponse): void {
  self.postMessage(response);
}

// Handler implementations would follow...
```

---

## 7. Error Handling

### 7.1 Error Categories

| Code | Description | Recovery |
|------|-------------|----------|
| `NOT_INITIALIZED` | Engine not initialized | Call `initialize()` first |
| `FETCH_FAILED` | Network error loading Parquet | Retry with exponential backoff |
| `INVALID_PARQUET` | Corrupted or invalid file | Check file URL, report to admin |
| `TABLE_NOT_FOUND` | Query references unknown table | Load table first |
| `TABLE_EXISTS` | Table name already registered | Use different name or unload first |
| `SQL_SYNTAX_ERROR` | Invalid SQL syntax | Fix query syntax |
| `SQL_EXECUTION_ERROR` | Runtime query error | Check column names, types |
| `INTERNAL_ERROR` | Unexpected engine error | Report bug, retry |

### 7.2 Client Error Handling Pattern

```typescript
try {
  const result = await engine.query('SELECT * FROM enrollment');
  // Handle success
} catch (error) {
  if (error.code === 'TABLE_NOT_FOUND') {
    // Load the table first
    await engine.loadTable('enrollment', PARQUET_URLS.enrollment);
    // Retry query
  } else if (error.code === 'SQL_SYNTAX_ERROR') {
    // Show user-friendly error message
    showError(`Query error: ${error.message}`);
  } else {
    // Log and show generic error
    console.error('DataEngine error:', error);
    showError('An unexpected error occurred');
  }
}
```

---

## 8. Example Usage

### 8.1 Basic Initialization and Query

```typescript
import { DataEngineClient } from './data-engine-client';

const PARQUET_BASE = 'https://raw.githubusercontent.com/user/fcps-audit/main/data/parquet';

async function main() {
  // Create and initialize
  const engine = new DataEngineClient();
  const version = await engine.initialize();
  console.log(`DuckDB initialized: ${version}`);
  
  // Load tables
  await engine.loadTable('enrollment', `${PARQUET_BASE}/table8_enrollment.parquet`);
  await engine.loadTable('expenditures', `${PARQUET_BASE}/table15_expenditures.parquet`);
  
  // Run a query
  const result = await engine.query(`
    SELECT 
      e.division_name,
      e.fiscal_year,
      e.adm_total,
      x.total_per_pupil
    FROM enrollment e
    JOIN expenditures x 
      ON e.division_code = x.division_code 
      AND e.fiscal_year = x.fiscal_year
    WHERE e.division_code = '069'
    ORDER BY e.fiscal_year
  `);
  
  console.log(`Query returned ${result.rowCount} rows in ${result.executionTimeMs}ms`);
  console.table(result.rows);
  
  // Cleanup
  await engine.shutdown();
}
```

### 8.2 Schema Introspection

```typescript
async function exploreTable(engine: DataEngineClient, tableName: string) {
  const schema = await engine.getSchema(tableName);
  
  console.log(`Table: ${schema.tableName}`);
  console.log(`Rows: ${schema.rowCount ?? 'unknown'}`);
  console.log('Columns:');
  
  for (const col of schema.columns) {
    const nullable = col.nullable ? 'NULL' : 'NOT NULL';
    console.log(`  ${col.name}: ${col.columnType} ${nullable}`);
  }
}
```

### 8.3 React Hook Integration

```typescript
import { useEffect, useState } from 'react';
import { DataEngineClient, QueryResult } from './data-engine-client';

// Singleton engine instance
let enginePromise: Promise<DataEngineClient> | null = null;

async function getEngine(): Promise<DataEngineClient> {
  if (!enginePromise) {
    enginePromise = (async () => {
      const engine = new DataEngineClient();
      await engine.initialize();
      return engine;
    })();
  }
  return enginePromise;
}

export function useQuery(sql: string, deps: unknown[] = []) {
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    
    async function run() {
      try {
        setLoading(true);
        setError(null);
        
        const engine = await getEngine();
        const data = await engine.query(sql);
        
        if (!cancelled) {
          setResult(data);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e : new Error(String(e)));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    
    run();
    
    return () => {
      cancelled = true;
    };
  }, [sql, ...deps]);

  return { result, error, loading };
}
```

---

## 9. Performance Considerations

### 9.1 Web Worker Benefits

- SQL queries run off the main thread
- UI remains responsive during large queries
- Parquet file fetching doesn't block rendering

### 9.2 Query Limits

- Default row limit: 10,000 rows per query
- Maximum row limit: 100,000 rows
- Large result sets should use pagination via `LIMIT/OFFSET`

### 9.3 Memory Management

- Parquet files are loaded into DuckDB's memory
- Call `unloadTable()` to free memory for unused tables
- Total memory limited by browser constraints (~2GB typical)

### 9.4 Recommended Patterns

```typescript
// Good: Aggregate in SQL, return small result
const result = await engine.query(`
  SELECT fiscal_year, SUM(total_per_pupil) as total
  FROM expenditures
  GROUP BY fiscal_year
`);

// Avoid: Returning large raw datasets
const result = await engine.query(`
  SELECT * FROM large_table
`);
```

---

## 10. Acceptance Criteria

### 10.1 Initialization

- [ ] DuckDB-WASM loads successfully in Web Worker
- [ ] `initialize()` returns DuckDB version string
- [ ] Multiple `initialize()` calls are idempotent
- [ ] Errors before initialization return `NOT_INITIALIZED`

### 10.2 Table Loading

- [ ] Parquet files load from HTTPS URLs
- [ ] Table name is registered and queryable
- [ ] `TableInfo` includes accurate row count and size
- [ ] Duplicate table names return `TABLE_EXISTS` error
- [ ] Invalid URLs return `FETCH_FAILED` error
- [ ] Corrupt files return `INVALID_PARQUET` error

### 10.3 Query Execution

- [ ] Valid SQL returns `QueryResult` with rows
- [ ] Column types are correctly identified
- [ ] Execution time is measured and returned
- [ ] Row limit is enforced (default 10,000)
- [ ] Custom limit parameter works
- [ ] Syntax errors return `SQL_SYNTAX_ERROR`
- [ ] Runtime errors return `SQL_EXECUTION_ERROR`

### 10.4 Schema Introspection

- [ ] `getSchema()` returns all columns with types
- [ ] Nullable flag is accurate
- [ ] Row count is included when available
- [ ] Unknown table returns `TABLE_NOT_FOUND`

### 10.5 Table Management

- [ ] `listTables()` returns all registered tables
- [ ] `unloadTable()` removes table from memory
- [ ] Unloaded tables are no longer queryable
- [ ] Unloading unknown table returns `TABLE_NOT_FOUND`

### 10.6 Shutdown

- [ ] `shutdown()` terminates worker cleanly
- [ ] Pending requests are rejected
- [ ] Worker can be recreated after shutdown

### 10.7 Error Handling

- [ ] All errors include appropriate `ErrorCode`
- [ ] Error messages are human-readable
- [ ] Request IDs are always echoed in responses
- [ ] Worker errors don't crash main thread

### 10.8 Performance

- [ ] Queries don't block main thread
- [ ] UI remains responsive during large queries
- [ ] Memory usage stays within browser limits

---

## 11. Future Enhancements

- **Streaming results**: For very large queries, stream rows in batches
- **Query cancellation**: Ability to cancel long-running queries
- **Prepared statements**: Cache parsed queries for repeated execution
- **IndexedDB caching**: Cache Parquet files locally for offline use
- **Query history**: Track and replay previous queries
