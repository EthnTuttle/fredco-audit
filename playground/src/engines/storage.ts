/**
 * StorageEngine - IndexedDB wrapper for persistent storage
 * 
 * Provides caching for Parquet files, notebook persistence,
 * and user preferences storage.
 */

// Database configuration
const DB_NAME = 'fcps_audit_db';
const DB_VERSION = 1;

// Store names
const STORES = {
  PARQUET_CACHE: 'parquet_cache',
  NOTEBOOKS: 'notebooks',
  PREFERENCES: 'preferences',
  METADATA: 'metadata',
} as const;

// Database instance
let db: IDBDatabase | null = null;

/**
 * Cached Parquet file metadata
 */
export interface CachedParquet {
  url: string;
  size: number;
  etag?: string;
  fetchedAt: number;
  lastAccessed: number;
  contentHash: string;
}

/**
 * Notebook summary for listing
 */
export interface NotebookSummary {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  cellCount: number;
  tags: string[];
  nostrEventId?: string;
}

/**
 * Full notebook document
 */
export interface Notebook {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  cells: NotebookCell[];
  metadata: NotebookMetadata;
  nostrEventId?: string;
}

/**
 * Notebook cell
 */
export interface NotebookCell {
  id: string;
  type: 'sql' | 'markdown';
  content: string;
  output?: CellOutput;
  collapsed?: boolean;
}

/**
 * Cell output
 */
export interface CellOutput {
  type: 'table' | 'error' | 'markdown';
  data: unknown;
  executedAt: number;
  durationMs: number;
}

/**
 * Notebook metadata
 */
export interface NotebookMetadata {
  description?: string;
  tags: string[];
  dataSources: string[];
  schemaVersion: number;
}

/**
 * User preferences
 */
export interface UserPreferences {
  theme: 'light' | 'dark' | 'system';
  editor: EditorPreferences;
  query: QueryPreferences;
  nostr: NostrPreferences;
}

/**
 * Editor preferences
 */
export interface EditorPreferences {
  fontSize: number;
  tabSize: number;
  lineNumbers: boolean;
  wordWrap: boolean;
  autocomplete: boolean;
}

/**
 * Query preferences
 */
export interface QueryPreferences {
  maxRows: number;
  timeoutSeconds: number;
  autoRun: boolean;
}

/**
 * Nostr preferences
 */
export interface NostrPreferences {
  npub?: string;
  relays: string[];
  autoPublish: boolean;
}

/**
 * Storage quota info
 */
export interface StorageQuota {
  total?: number;
  used: number;
  available?: number;
  usagePercent?: number;
}

/**
 * Cache statistics
 */
export interface CacheStats {
  fileCount: number;
  totalSize: number;
  oldestEntry?: number;
  newestEntry?: number;
}

/**
 * Default preferences
 */
const DEFAULT_PREFERENCES: UserPreferences = {
  theme: 'dark',
  editor: {
    fontSize: 14,
    tabSize: 2,
    lineNumbers: true,
    wordWrap: false,
    autocomplete: true,
  },
  query: {
    maxRows: 10000,
    timeoutSeconds: 30,
    autoRun: false,
  },
  nostr: {
    relays: [
      'wss://relay.damus.io',
      'wss://nos.lol',
      'wss://relay.nostr.band',
    ],
    autoPublish: false,
  },
};

/**
 * Initialize the database
 */
export async function initStorage(): Promise<void> {
  if (db) {
    console.log('[StorageEngine] Already initialized');
    return;
  }

  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => {
      console.error('[StorageEngine] Failed to open database:', request.error);
      reject(request.error);
    };

    request.onsuccess = () => {
      db = request.result;
      console.log('[StorageEngine] Database opened');
      resolve();
    };

    request.onupgradeneeded = (event) => {
      const database = (event.target as IDBOpenDBRequest).result;
      
      // Create parquet_cache store
      if (!database.objectStoreNames.contains(STORES.PARQUET_CACHE)) {
        const cacheStore = database.createObjectStore(STORES.PARQUET_CACHE, { keyPath: 'url' });
        cacheStore.createIndex('fetchedAt', 'fetchedAt');
        cacheStore.createIndex('lastAccessed', 'lastAccessed');
        cacheStore.createIndex('size', 'size');
      }

      // Create notebooks store
      if (!database.objectStoreNames.contains(STORES.NOTEBOOKS)) {
        const notebooksStore = database.createObjectStore(STORES.NOTEBOOKS, { keyPath: 'id' });
        notebooksStore.createIndex('title', 'title');
        notebooksStore.createIndex('createdAt', 'createdAt');
        notebooksStore.createIndex('updatedAt', 'updatedAt');
      }

      // Create preferences store
      if (!database.objectStoreNames.contains(STORES.PREFERENCES)) {
        database.createObjectStore(STORES.PREFERENCES, { keyPath: 'key' });
      }

      // Create metadata store
      if (!database.objectStoreNames.contains(STORES.METADATA)) {
        database.createObjectStore(STORES.METADATA, { keyPath: 'key' });
      }

      console.log('[StorageEngine] Database schema created');
    };
  });
}

/**
 * Get a transaction
 */
function getTransaction(storeNames: string | string[], mode: IDBTransactionMode): IDBTransaction {
  if (!db) throw new Error('Database not initialized');
  return db.transaction(storeNames, mode);
}

/**
 * Get an object store
 */
function getStore(storeName: string, mode: IDBTransactionMode): IDBObjectStore {
  return getTransaction(storeName, mode).objectStore(storeName);
}

// ============================================================================
// Cache Operations
// ============================================================================

/**
 * Check if URL is cached
 */
export async function checkCache(url: string): Promise<CachedParquet | null> {
  return new Promise((resolve, reject) => {
    try {
      const store = getStore(STORES.PARQUET_CACHE, 'readonly');
      const request = store.get(url);
      
      request.onsuccess = () => {
        const result = request.result as CachedParquet | undefined;
        if (result) {
          // Update last accessed time
          updateLastAccessed(url);
        }
        resolve(result ?? null);
      };
      
      request.onerror = () => reject(request.error);
    } catch (error) {
      reject(error);
    }
  });
}

/**
 * Update last accessed time for a cache entry
 */
async function updateLastAccessed(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    try {
      const store = getStore(STORES.PARQUET_CACHE, 'readwrite');
      const request = store.get(url);
      
      request.onsuccess = () => {
        const entry = request.result as CachedParquet | undefined;
        if (entry) {
          entry.lastAccessed = Date.now();
          store.put(entry);
        }
        resolve();
      };
      
      request.onerror = () => reject(request.error);
    } catch (error) {
      reject(error);
    }
  });
}

/**
 * Store Parquet data in cache
 */
export async function cacheParquet(
  url: string,
  data: ArrayBuffer,
  etag?: string
): Promise<void> {
  return new Promise((resolve, reject) => {
    try {
      const store = getStore(STORES.PARQUET_CACHE, 'readwrite');
      
      // Create metadata
      const metadata: CachedParquet = {
        url,
        size: data.byteLength,
        etag,
        fetchedAt: Date.now(),
        lastAccessed: Date.now(),
        contentHash: hashArrayBuffer(data),
      };

      // Store metadata
      const metaRequest = store.put(metadata);
      
      metaRequest.onsuccess = () => {
        // Store actual data in a separate key
        const dataStore = getStore(STORES.PARQUET_CACHE, 'readwrite');
        dataStore.put({ url: `${url}:data`, data });
        console.log(`[StorageEngine] Cached: ${url} (${formatBytes(data.byteLength)})`);
        resolve();
      };
      
      metaRequest.onerror = () => reject(metaRequest.error);
    } catch (error) {
      reject(error);
    }
  });
}

/**
 * Get cached Parquet data
 */
export async function getCachedParquet(url: string): Promise<ArrayBuffer | null> {
  return new Promise((resolve, reject) => {
    try {
      const store = getStore(STORES.PARQUET_CACHE, 'readonly');
      const request = store.get(`${url}:data`);
      
      request.onsuccess = () => {
        const result = request.result as { data: ArrayBuffer } | undefined;
        resolve(result?.data ?? null);
      };
      
      request.onerror = () => reject(request.error);
    } catch (error) {
      reject(error);
    }
  });
}

/**
 * Evict a cache entry
 */
export async function evictCache(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    try {
      const store = getStore(STORES.PARQUET_CACHE, 'readwrite');
      store.delete(url);
      store.delete(`${url}:data`);
      console.log(`[StorageEngine] Evicted: ${url}`);
      resolve();
    } catch (error) {
      reject(error);
    }
  });
}

/**
 * Clear all cache
 */
export async function clearCache(): Promise<void> {
  return new Promise((resolve, reject) => {
    try {
      const store = getStore(STORES.PARQUET_CACHE, 'readwrite');
      const request = store.clear();
      
      request.onsuccess = () => {
        console.log('[StorageEngine] Cache cleared');
        resolve();
      };
      
      request.onerror = () => reject(request.error);
    } catch (error) {
      reject(error);
    }
  });
}

/**
 * Get cache statistics
 */
export async function getCacheStats(): Promise<CacheStats> {
  return new Promise((resolve, reject) => {
    try {
      const store = getStore(STORES.PARQUET_CACHE, 'readonly');
      const request = store.openCursor();
      
      const stats: CacheStats = {
        fileCount: 0,
        totalSize: 0,
        oldestEntry: undefined,
        newestEntry: undefined,
      };

      request.onsuccess = () => {
        const cursor = request.result;
        if (cursor) {
          const entry = cursor.value as CachedParquet;
          // Skip data entries (only count metadata)
          if (!entry.url.endsWith(':data')) {
            stats.fileCount++;
            stats.totalSize += entry.size;
            
            if (!stats.oldestEntry || entry.fetchedAt < stats.oldestEntry) {
              stats.oldestEntry = entry.fetchedAt;
            }
            if (!stats.newestEntry || entry.fetchedAt > stats.newestEntry) {
              stats.newestEntry = entry.fetchedAt;
            }
          }
          cursor.continue();
        } else {
          resolve(stats);
        }
      };
      
      request.onerror = () => reject(request.error);
    } catch (error) {
      reject(error);
    }
  });
}

// ============================================================================
// Notebook Operations
// ============================================================================

/**
 * Save a notebook
 */
export async function saveNotebook(notebook: Notebook): Promise<void> {
  return new Promise((resolve, reject) => {
    try {
      const store = getStore(STORES.NOTEBOOKS, 'readwrite');
      notebook.updatedAt = Date.now();
      const request = store.put(notebook);
      
      request.onsuccess = () => {
        console.log(`[StorageEngine] Saved notebook: ${notebook.id}`);
        resolve();
      };
      
      request.onerror = () => reject(request.error);
    } catch (error) {
      reject(error);
    }
  });
}

/**
 * Load a notebook
 */
export async function loadNotebook(id: string): Promise<Notebook | null> {
  return new Promise((resolve, reject) => {
    try {
      const store = getStore(STORES.NOTEBOOKS, 'readonly');
      const request = store.get(id);
      
      request.onsuccess = () => {
        resolve(request.result as Notebook | null);
      };
      
      request.onerror = () => reject(request.error);
    } catch (error) {
      reject(error);
    }
  });
}

/**
 * Delete a notebook
 */
export async function deleteNotebook(id: string): Promise<void> {
  return new Promise((resolve, reject) => {
    try {
      const store = getStore(STORES.NOTEBOOKS, 'readwrite');
      const request = store.delete(id);
      
      request.onsuccess = () => {
        console.log(`[StorageEngine] Deleted notebook: ${id}`);
        resolve();
      };
      
      request.onerror = () => reject(request.error);
    } catch (error) {
      reject(error);
    }
  });
}

/**
 * List all notebooks
 */
export async function listNotebooks(): Promise<NotebookSummary[]> {
  return new Promise((resolve, reject) => {
    try {
      const store = getStore(STORES.NOTEBOOKS, 'readonly');
      const request = store.openCursor();
      
      const notebooks: NotebookSummary[] = [];

      request.onsuccess = () => {
        const cursor = request.result;
        if (cursor) {
          const notebook = cursor.value as Notebook;
          notebooks.push({
            id: notebook.id,
            title: notebook.title,
            createdAt: notebook.createdAt,
            updatedAt: notebook.updatedAt,
            cellCount: notebook.cells.length,
            tags: notebook.metadata.tags,
            nostrEventId: notebook.nostrEventId,
          });
          cursor.continue();
        } else {
          // Sort by updatedAt descending
          notebooks.sort((a, b) => b.updatedAt - a.updatedAt);
          resolve(notebooks);
        }
      };
      
      request.onerror = () => reject(request.error);
    } catch (error) {
      reject(error);
    }
  });
}

/**
 * Create a new notebook
 */
export function createNotebook(title: string = 'Untitled Notebook'): Notebook {
  const now = Date.now();
  return {
    id: generateId(),
    title,
    createdAt: now,
    updatedAt: now,
    cells: [
      {
        id: generateId(),
        type: 'sql',
        content: '-- Enter your SQL query here\nSELECT * FROM real_estate_tax LIMIT 10',
      },
    ],
    metadata: {
      tags: [],
      dataSources: [],
      schemaVersion: 1,
    },
  };
}

// ============================================================================
// Preferences Operations
// ============================================================================

/**
 * Get user preferences
 */
export async function getPreferences(): Promise<UserPreferences> {
  return new Promise((resolve, reject) => {
    try {
      const store = getStore(STORES.PREFERENCES, 'readonly');
      const request = store.get('user_preferences');
      
      request.onsuccess = () => {
        const result = request.result as { key: string; value: UserPreferences } | undefined;
        resolve(result?.value ?? DEFAULT_PREFERENCES);
      };
      
      request.onerror = () => reject(request.error);
    } catch (error) {
      reject(error);
    }
  });
}

/**
 * Save user preferences
 */
export async function savePreferences(preferences: UserPreferences): Promise<void> {
  return new Promise((resolve, reject) => {
    try {
      const store = getStore(STORES.PREFERENCES, 'readwrite');
      const request = store.put({ key: 'user_preferences', value: preferences });
      
      request.onsuccess = () => {
        console.log('[StorageEngine] Preferences saved');
        resolve();
      };
      
      request.onerror = () => reject(request.error);
    } catch (error) {
      reject(error);
    }
  });
}

/**
 * Reset preferences to defaults
 */
export async function resetPreferences(): Promise<void> {
  return savePreferences(DEFAULT_PREFERENCES);
}

// ============================================================================
// Storage Quota
// ============================================================================

/**
 * Get storage quota information
 */
export async function getStorageQuota(): Promise<StorageQuota> {
  if (navigator.storage && navigator.storage.estimate) {
    const estimate = await navigator.storage.estimate();
    return {
      total: estimate.quota,
      used: estimate.usage ?? 0,
      available: estimate.quota ? estimate.quota - (estimate.usage ?? 0) : undefined,
      usagePercent: estimate.quota && estimate.usage 
        ? (estimate.usage / estimate.quota) * 100 
        : undefined,
    };
  }
  
  // Fallback if StorageManager API not available
  return { used: 0 };
}

/**
 * Request persistent storage
 */
export async function requestPersistence(): Promise<boolean> {
  if (navigator.storage && navigator.storage.persist) {
    const granted = await navigator.storage.persist();
    console.log(`[StorageEngine] Persistent storage ${granted ? 'granted' : 'denied'}`);
    return granted;
  }
  return false;
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Generate a unique ID
 */
function generateId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`;
}

/**
 * Simple hash for ArrayBuffer (for cache validation)
 */
function hashArrayBuffer(buffer: ArrayBuffer): string {
  const view = new Uint8Array(buffer);
  let hash = 0;
  for (let i = 0; i < view.length; i += 1000) { // Sample every 1000 bytes for speed
    hash = ((hash << 5) - hash) + view[i];
    hash = hash & hash;
  }
  return hash.toString(16);
}

/**
 * Format bytes to human readable
 */
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

/**
 * Export notebook as JSON
 */
export function exportNotebookJson(notebook: Notebook): string {
  return JSON.stringify(notebook, null, 2);
}

/**
 * Import notebook from JSON
 */
export function importNotebookJson(json: string): Notebook {
  const notebook = JSON.parse(json) as Notebook;
  // Generate new ID to avoid conflicts
  notebook.id = generateId();
  notebook.createdAt = Date.now();
  notebook.updatedAt = Date.now();
  return notebook;
}

/**
 * Close the database
 */
export function closeStorage(): void {
  if (db) {
    db.close();
    db = null;
    console.log('[StorageEngine] Database closed');
  }
}
