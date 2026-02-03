/**
 * DataEngine - DuckDB-WASM wrapper for SQL queries
 * 
 * Provides initialization and query execution for Parquet data files.
 * Includes IndexedDB caching and SHA-256 integrity verification.
 */

import * as duckdb from '@duckdb/duckdb-wasm';
import { 
  initStorage, 
  checkCache, 
  cacheParquet, 
  getCachedParquet,
  evictCache
} from './storage';
import {
  showIntegrityFailureDialog,
  type IntegrityFailure
} from './feedback';

// Re-export for type safety
export type { IntegrityFailure };

// DuckDB instance
let db: duckdb.AsyncDuckDB | null = null;
let conn: duckdb.AsyncDuckDBConnection | null = null;

// Parquet files available for loading (served from public/parquet via symlink)
const PARQUET_BASE_URL = './parquet';

/**
 * Parquet file manifest with SHA-256 hashes for integrity verification.
 * Generate with: sha256sum data/parquet/*.parquet
 * These hashes should be published with GitHub releases.
 * Last updated: 2026-02-01
 */
export const PARQUET_MANIFEST: Record<string, { size: number; sha256: string }> = {
  // Large files
  'real_estate_tax.parquet': { 
    size: 23246016, 
    sha256: 'd70fdfb79d2f8ac88a5afcc8bdb86c0d504e54d8d0077fac6e2fa9ee646a2785' 
  },
  'county_department_detail.parquet': { 
    size: 4133890, 
    sha256: 'f911864d8815dc90871dd171674cb01c7fe526b3558ccfda271861a82f312cef' 
  },
  'districts.parquet': { 
    size: 305773, 
    sha256: 'ba6b315662b05ba0b46bb847ae9beb0ccc1f44a9234ec687506a92a4eefc9342' 
  },
  'ownership_analysis.parquet': { 
    size: 111694, 
    sha256: 'ca3874ac75cc290f454a7ad85f83dc034a228ec0d844bebb15a712bf997ef25b' 
  },
  
  // County budget data
  'county_budget_schools.parquet': { 
    size: 38723, 
    sha256: '576a55a638a27b401eec208d4d9996177a6263cc050bd4010139fda87190fc11' 
  },
  'county_govt_time_series.parquet': { 
    size: 15087, 
    sha256: '11652e10d60979c12f5960a618f4f5a7dee589a6bcf3926ef293e9a326927716' 
  },
  'county_govt_budget_detail.parquet': { 
    size: 7384, 
    sha256: '5cf49fbb0b7a8d89f3dbefad216695d81e8e833da92f55cd249301410b25282b' 
  },
  
  // VDOE tables
  'vdoe_table18_admin.parquet': { 
    size: 30380, 
    sha256: '8f3279e853326193c2eb6c1e4474155dc9ff6d44563f871296e9190ddbec0814' 
  },
  'vdoe_table19_instructional.parquet': { 
    size: 30495, 
    sha256: '763ec69b854e0f1ab439d098646d9e612e791f7b7ea58145da67a4d394973edd' 
  },
  'vdoe_table15_expenditures.parquet': { 
    size: 13398, 
    sha256: '31167bfa3890ea45728ba190a719c32e7a1308cc994d403e63f1d53047dc011b' 
  },
  'vdoe_table8_enrollment.parquet': { 
    size: 12161, 
    sha256: '10f42d3ec9545ced2225a6af92c1111b2984bf97e58e4d369350281b45fa9c1c' 
  },
  'vdoe_table17_ratios.parquet': { 
    size: 9498, 
    sha256: 'b6bc103ad326fa35ef8abd49f2f60410f72b0bd224e2b0e290c14d7fa5cd0d38' 
  },
  
  // APA data (flattened by exhibit)
  'apa_exhibit_b.parquet': { 
    size: 25296, 
    sha256: '61eb1dccd5fedaa0d1f04e4069997c3db38968088cd76daf29fa9f6ebb825fc2' 
  },
  'apa_education_by_division.parquet': { 
    size: 23691, 
    sha256: 'cc884f1776afd74ca41edd0abf20e5846f4ed061387be389c634bcdd14e7c30e' 
  },
  'apa_exhibit_b2.parquet': { 
    size: 14446, 
    sha256: '129671845fc51593a2e2391b3ed8af82bb7fae6421fae4ac095c1f634f710344' 
  },
  'apa_exhibit_e.parquet': { 
    size: 14356, 
    sha256: '5614ea0f2bf1517fbe025980d1fb33e4be394869db88caa85b456d87667afb19' 
  },
  'apa_exhibit_d.parquet': { 
    size: 13479, 
    sha256: 'a9762aa25915671beebe6641006065fc20903c91f5287d95d2562c72164a5bf3' 
  },
  'apa_exhibit_g.parquet': { 
    size: 11789, 
    sha256: '55ae3a2453308b2adb237d434d001befb34b70679bbce1e0cf7739aa9b9eaef2' 
  },
  'apa_exhibit_b1.parquet': { 
    size: 11098, 
    sha256: '6603376d809e1c0a79ea844c1cb23a35ac00404d836f6399cd4af4aace11a671' 
  },
  'apa_exhibit_h.parquet': { 
    size: 10709, 
    sha256: '4a28fef967a559489aa5c3d93c7ee63032ffe4653ea579776b5013a360c7c589' 
  },
  
  // Other data
  'tax_summary.parquet': { 
    size: 30880, 
    sha256: '4ee42259d384b5555ed18f268b5a463665eb8d0ef743e9616705def1b7ec88ee' 
  },
  'expenditures.parquet': { 
    size: 15976, 
    sha256: 'cb95cf1f25d3c2ce2b95d6f92d17e5aefd4c5e9004c425b97279ba9e37ce50b3' 
  },
  'enrollment.parquet': { 
    size: 6461, 
    sha256: 'c2b1903a849b087cb714e28efc7f6a229ff980b0d5a2547c22b1ec42e7a02bb9' 
  },
};

const PARQUET_FILES = Object.keys(PARQUET_MANIFEST);

/**
 * Optional GIS datasets that can be loaded on demand.
 * These are larger files stored in data/processed/gis/
 */
export interface GISDataset {
  name: string;
  filename: string;
  description: string;
  size: number;
}

export const GIS_DATASETS: GISDataset[] = [
  { name: 'airport_overlay', filename: 'airport_overlay.parquet', description: 'Airport overlay zones', size: 57724 },
  { name: 'comp_plan_applications', filename: 'comp_plan_applications.parquet', description: 'Comprehensive plan applications', size: 20770 },
  { name: 'conservation_easements', filename: 'conservation_easements.parquet', description: 'Protected lands', size: 282312 },
  { name: 'county_parcels', filename: 'county_parcels.parquet', description: 'County parcels', size: 49689929 },
  { name: 'county_parcels_raw', filename: 'county_parcels_raw.parquet', description: 'County parcels (raw)', size: 45445339 },
  { name: 'eastern_road_plan', filename: 'eastern_road_plan.parquet', description: 'Eastern road plan', size: 948607 },
  { name: 'fire_districts', filename: 'fire_districts.parquet', description: 'Fire & rescue districts', size: 633399 },
  { name: 'fire_stations', filename: 'fire_stations.parquet', description: 'Fire station locations', size: 15184 },
  { name: 'frederick_parcels', filename: 'frederick_parcels.parquet', description: 'Frederick parcels with geometry', size: 43791373 },
  { name: 'frederick_parcels_raw', filename: 'frederick_parcels_raw.parquet', description: 'Frederick parcels (raw)', size: 42858290 },
  { name: 'future_rt37_bypass', filename: 'future_rt37_bypass.parquet', description: 'Future RT-37 bypass route', size: 468376 },
  { name: 'growth_area_parcels', filename: 'growth_area_parcels.parquet', description: 'Parcels in growth areas', size: 6015505 },
  { name: 'growth_areas', filename: 'growth_areas.parquet', description: 'Urban growth areas', size: 750667 },
  { name: 'interstate_overlay', filename: 'interstate_overlay.parquet', description: 'Interstate overlay zones', size: 59357 },
  { name: 'long_range_land_use', filename: 'long_range_land_use.parquet', description: 'Future land use plan', size: 1450160 },
  { name: 'magisterial_districts', filename: 'magisterial_districts.parquet', description: 'Magisterial voting districts', size: 182533 },
  { name: 'parcels_growth_analysis', filename: 'parcels_growth_analysis.parquet', description: 'Parcels with growth analysis', size: 49706515 },
  { name: 'parcels_with_growth_analysis', filename: 'parcels_with_growth_analysis.parquet', description: 'Parcels with growth data', size: 43787674 },
  { name: 'proffer_points', filename: 'proffer_points.parquet', description: 'Proffer locations', size: 76637 },
  { name: 'public_schools', filename: 'public_schools.parquet', description: 'School locations', size: 17583 },
  { name: 'rezonings', filename: 'rezonings.parquet', description: 'Rezoning applications', size: 28092 },
  { name: 'school_districts', filename: 'school_districts.parquet', description: 'School attendance zones', size: 147672 },
  { name: 'streets', filename: 'streets.parquet', description: 'Street centerlines', size: 7333494 },
  { name: 'swsa', filename: 'swsa.parquet', description: 'Sewer/water service areas', size: 57217 },
  { name: 'uda', filename: 'uda.parquet', description: 'Urban development areas', size: 51740 },
  { name: 'zoning', filename: 'zoning.parquet', description: 'Zoning districts', size: 1246798 },
];

// GIS files are served from data/processed/gis/ via GitHub Pages
const GIS_BASE_URL = '../data/processed/gis';

// Track which GIS datasets are loaded
const loadedGISDatasets: Set<string> = new Set();

// Cache settings
const CACHE_ENABLED = true;
const VERIFY_INTEGRITY = true;

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
 * Initialize DuckDB-WASM with caching support
 */
export async function initDataEngine(): Promise<void> {
  if (db) {
    console.log('[DataEngine] Already initialized');
    return;
  }

  console.log('[DataEngine] Initializing DuckDB-WASM...');

  // Initialize IndexedDB storage for caching
  if (CACHE_ENABLED) {
    try {
      await initStorage();
      console.log('[DataEngine] Cache storage ready');
    } catch (error) {
      console.warn('[DataEngine] Cache unavailable, will fetch from network:', error);
    }
  }

  // Use local DuckDB WASM files to avoid CORS issues
  // Resolve from the page URL (handles both dev and prod with base path)
  const baseUrl = new URL(window.location.href);
  const basePath = baseUrl.pathname.endsWith('/') 
    ? baseUrl.pathname 
    : baseUrl.pathname + '/';
  const DUCKDB_BASE = `${baseUrl.origin}${basePath}duckdb/`;
  
  const mainModule = `${DUCKDB_BASE}duckdb-eh.wasm`;
  const mainWorker = `${DUCKDB_BASE}duckdb-browser-eh.worker.js`;

  console.log('[DataEngine] Using local DuckDB bundle:', { mainModule, mainWorker });

  // Create worker from local file
  const worker = new Worker(mainWorker);
  const logger = new duckdb.ConsoleLogger();

  // Instantiate DuckDB
  db = new duckdb.AsyncDuckDB(logger, worker);
  await db.instantiate(mainModule);

  // Open connection
  conn = await db.connect();

  console.log('[DataEngine] DuckDB ready');

  // Load Parquet files (with caching)
  await loadParquetFiles();
}

/**
 * Load Parquet files into DuckDB with caching
 */
async function loadParquetFiles(): Promise<void> {
  if (!db || !conn) throw new Error('DuckDB not initialized');

  console.log('[DataEngine] Loading Parquet files...');

  const loadPromises = PARQUET_FILES.map(async (filename) => {
    const tableName = filename.replace('.parquet', '').replace(/-/g, '_');
    const url = `${PARQUET_BASE_URL}/${filename}`;

    try {
      // Try to load from cache first
      const data = await loadWithCache(url, filename);
      
      if (data) {
        // Register from buffer (cached or freshly fetched)
        await db!.registerFileBuffer(filename, new Uint8Array(data));
      } else {
        // Fallback to HTTP protocol if caching failed
        await db!.registerFileURL(filename, url, duckdb.DuckDBDataProtocol.HTTP, false);
      }

      // Create a view for the file
      await conn!.query(`CREATE VIEW IF NOT EXISTS ${tableName} AS SELECT * FROM parquet_scan('${filename}')`);

      console.log(`[DataEngine] Loaded: ${tableName}`);
    } catch (error) {
      console.warn(`[DataEngine] Failed to load ${filename}:`, error);
    }
  });

  await Promise.all(loadPromises);
}

/**
 * Load a file with caching support
 */
async function loadWithCache(url: string, filename: string): Promise<ArrayBuffer | null> {
  if (!CACHE_ENABLED) {
    return fetchAndCache(url, filename);
  }

  try {
    // Check if we have it cached
    const cached = await checkCache(url);
    
    if (cached) {
      // Get cached data
      const data = await getCachedParquet(url);
      
      if (data) {
        // Verify integrity if hash is available
        const manifest = PARQUET_MANIFEST[filename];
        if (VERIFY_INTEGRITY && manifest?.sha256) {
          const actualHash = await computeSha256(data);
          const isValid = actualHash === manifest.sha256.toLowerCase();
          
          if (!isValid) {
            console.warn(`[DataEngine] Cache integrity check failed for ${filename}`);
            
            // Show feedback dialog to user
            const failure: IntegrityFailure = {
              filename,
              url,
              expectedHash: manifest.sha256,
              actualHash,
              expectedSize: manifest.size,
              actualSize: data.byteLength,
              timestamp: Date.now(),
              source: 'cache',
            };
            
            // Show dialog and wait for user choice
            await showIntegrityFailureDialog(failure);
            
            // Evict the bad cache entry and re-fetch
            await evictCache(url);
            return fetchAndCache(url, filename);
          }
        }
        
        console.log(`[DataEngine] Cache hit: ${filename}`);
        return data;
      }
    }

    // Not cached or cache miss - fetch from network
    return fetchAndCache(url, filename);
  } catch (error) {
    console.warn(`[DataEngine] Cache error for ${filename}:`, error);
    return fetchAndCache(url, filename);
  }
}

/**
 * Fetch from network and store in cache
 * 
 * IMPORTANT: DuckDB's registerFileBuffer() takes ownership of the ArrayBuffer,
 * causing it to become "detached". We must make a copy BEFORE passing to DuckDB
 * and cache that copy, then return the original for DuckDB to consume.
 */
async function fetchAndCache(url: string, filename: string): Promise<ArrayBuffer | null> {
  try {
    console.log(`[DataEngine] Fetching: ${filename}`);
    const response = await fetch(url);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.arrayBuffer();
    const etag = response.headers.get('etag') ?? undefined;

    // Store in cache (don't await - let it happen in background)
    // CRITICAL: Make a copy BEFORE DuckDB takes ownership of the original
    if (CACHE_ENABLED) {
      const cacheData = data.slice(0); // Create a copy for caching
      cacheParquet(url, cacheData, etag).catch((err) => {
        console.warn(`[DataEngine] Failed to cache ${filename}:`, err);
      });
    }

    // Return original - DuckDB will take ownership
    return data;
  } catch (error) {
    console.error(`[DataEngine] Fetch failed for ${filename}:`, error);
    return null;
  }
}

/**
 * Compute SHA-256 hash of data (for integrity verification and manifest generation)
 */
export async function computeSha256(data: ArrayBuffer): Promise<string> {
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
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
 * Get list of available GIS datasets
 */
export function getAvailableGISDatasets(): GISDataset[] {
  return GIS_DATASETS;
}

/**
 * Check if a GIS dataset is loaded
 */
export function isGISDatasetLoaded(name: string): boolean {
  return loadedGISDatasets.has(name);
}

/**
 * Load a GIS dataset on demand
 */
export async function loadGISDataset(name: string): Promise<void> {
  if (!db || !conn) throw new Error('DuckDB not initialized');
  
  const dataset = GIS_DATASETS.find(d => d.name === name);
  if (!dataset) throw new Error(`Unknown GIS dataset: ${name}`);
  
  if (loadedGISDatasets.has(name)) {
    console.log(`[DataEngine] GIS dataset already loaded: ${name}`);
    return;
  }

  const url = `${GIS_BASE_URL}/${dataset.filename}`;
  console.log(`[DataEngine] Loading GIS dataset: ${name} from ${url}`);

  try {
    // Fetch the file
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.arrayBuffer();
    
    // Cache it if caching is enabled
    if (CACHE_ENABLED) {
      const cacheData = data.slice(0);
      cacheParquet(url, cacheData).catch(err => {
        console.warn(`[DataEngine] Failed to cache GIS ${name}:`, err);
      });
    }
    
    // Register with DuckDB
    await db.registerFileBuffer(dataset.filename, new Uint8Array(data));
    await conn.query(`CREATE VIEW IF NOT EXISTS ${name} AS SELECT * FROM parquet_scan('${dataset.filename}')`);
    
    loadedGISDatasets.add(name);
    console.log(`[DataEngine] Loaded GIS dataset: ${name}`);
  } catch (error) {
    console.error(`[DataEngine] Failed to load GIS dataset ${name}:`, error);
    throw error;
  }
}

/**
 * Unload a GIS dataset to free memory
 */
export async function unloadGISDataset(name: string): Promise<void> {
  if (!conn) throw new Error('DuckDB not initialized');
  
  if (!loadedGISDatasets.has(name)) {
    return;
  }

  try {
    await conn.query(`DROP VIEW IF EXISTS ${name}`);
    loadedGISDatasets.delete(name);
    console.log(`[DataEngine] Unloaded GIS dataset: ${name}`);
  } catch (error) {
    console.error(`[DataEngine] Failed to unload GIS dataset ${name}:`, error);
    throw error;
  }
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
