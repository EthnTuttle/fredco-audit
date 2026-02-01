/**
 * DataEngine - DuckDB-WASM wrapper for SQL queries
 * 
 * Provides initialization and query execution for Parquet data files.
 */

import * as duckdb from '@duckdb/duckdb-wasm';

// DuckDB instance
let db: duckdb.AsyncDuckDB | null = null;
let conn: duckdb.AsyncDuckDBConnection | null = null;

// Parquet files available for loading
const PARQUET_BASE_URL = '../data/parquet';
const PARQUET_FILES = [
  'real_estate_tax.parquet',
  'county_department_detail.parquet',
  'districts.parquet',
  'ownership_analysis.parquet',
  'county_budget_schools.parquet',
  'county_government_analysis.parquet',
  'vdoe_table18_admin.parquet',
  'vdoe_table19_instructional.parquet',
  'tax_summary.parquet',
  'expenditures.parquet',
  'apa_data.parquet',
  'vdoe_table15_expenditures.parquet',
  'vdoe_table8_enrollment.parquet',
  'apa_education_expenditures.parquet',
  'vdoe_table17_ratios.parquet',
  'enrollment.parquet',
];

/**
 * Query result type
 */
export interface QueryResult {
  columns: string[];
  rows: unknown[][];
  rowCount: number;
  executionTimeMs: number;
}

/**
 * Initialize DuckDB-WASM
 */
export async function initDataEngine(): Promise<void> {
  if (db) {
    console.log('[DataEngine] Already initialized');
    return;
  }

  console.log('[DataEngine] Initializing DuckDB-WASM...');

  // Select best bundle for this browser
  const JSDELIVR_BUNDLES = duckdb.getJsDelivrBundles();
  const bundle = await duckdb.selectBundle(JSDELIVR_BUNDLES);

  if (!bundle.mainWorker) {
    throw new Error('No DuckDB worker available');
  }

  // Create worker
  const worker = new Worker(bundle.mainWorker);
  const logger = new duckdb.ConsoleLogger();

  // Instantiate DuckDB
  db = new duckdb.AsyncDuckDB(logger, worker);
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);

  // Open connection
  conn = await db.connect();

  console.log('[DataEngine] DuckDB ready');

  // Load Parquet files
  await loadParquetFiles();
}

/**
 * Load Parquet files into DuckDB
 */
async function loadParquetFiles(): Promise<void> {
  if (!db || !conn) throw new Error('DuckDB not initialized');

  console.log('[DataEngine] Loading Parquet files...');

  for (const filename of PARQUET_FILES) {
    const tableName = filename.replace('.parquet', '').replace(/-/g, '_');
    const url = `${PARQUET_BASE_URL}/${filename}`;

    try {
      // Register the Parquet file
      await db.registerFileURL(filename, url, duckdb.DuckDBDataProtocol.HTTP, false);

      // Create a view for the file
      await conn.query(`CREATE VIEW IF NOT EXISTS ${tableName} AS SELECT * FROM parquet_scan('${filename}')`);

      console.log(`[DataEngine] Loaded: ${tableName}`);
    } catch (error) {
      console.warn(`[DataEngine] Failed to load ${filename}:`, error);
    }
  }
}

/**
 * Execute a SQL query
 */
export async function executeQuery(sql: string): Promise<QueryResult> {
  if (!conn) throw new Error('DuckDB not initialized');

  const startTime = performance.now();

  try {
    const result = await conn.query(sql);
    const executionTimeMs = performance.now() - startTime;

    // Extract column names
    const columns = result.schema.fields.map(f => f.name);

    // Extract rows
    const rows: unknown[][] = [];
    for (const row of result) {
      const rowData: unknown[] = [];
      for (const col of columns) {
        rowData.push(row[col]);
      }
      rows.push(rowData);
    }

    return {
      columns,
      rows,
      rowCount: rows.length,
      executionTimeMs,
    };
  } catch (error) {
    throw new Error(`Query failed: ${error instanceof Error ? error.message : String(error)}`);
  }
}

/**
 * Get list of loaded tables
 */
export async function getLoadedTables(): Promise<string[]> {
  if (!conn) return [];

  try {
    const result = await conn.query("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name");
    const tables: string[] = [];
    for (const row of result) {
      tables.push(String(row.name));
    }
    return tables;
  } catch {
    return [];
  }
}

/**
 * Get table schema
 */
export async function getTableSchema(tableName: string): Promise<{ name: string; type: string }[]> {
  if (!conn) throw new Error('DuckDB not initialized');

  const result = await conn.query(`DESCRIBE ${tableName}`);
  const schema: { name: string; type: string }[] = [];
  
  for (const row of result) {
    schema.push({
      name: String(row.column_name),
      type: String(row.column_type),
    });
  }
  
  return schema;
}

/**
 * Load a custom Parquet file
 */
export async function loadParquetUrl(url: string, tableName: string): Promise<void> {
  if (!db || !conn) throw new Error('DuckDB not initialized');

  const filename = `${tableName}.parquet`;
  await db.registerFileURL(filename, url, duckdb.DuckDBDataProtocol.HTTP, false);
  await conn.query(`CREATE VIEW IF NOT EXISTS ${tableName} AS SELECT * FROM parquet_scan('${filename}')`);
  
  console.log(`[DataEngine] Loaded custom table: ${tableName}`);
}

/**
 * Close the database connection
 */
export async function closeDataEngine(): Promise<void> {
  if (conn) {
    await conn.close();
    conn = null;
  }
  if (db) {
    await db.terminate();
    db = null;
  }
  console.log('[DataEngine] Closed');
}
