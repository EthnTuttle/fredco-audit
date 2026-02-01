# StorageEngine Component Specification

## 1. Overview

### 1.1 Purpose

The StorageEngine provides persistent browser storage for the FCPS Audit application, managing cached data files, user notebooks, and application preferences. It abstracts IndexedDB operations behind a type-safe Rust/WASM interface.

### 1.2 Responsibilities

- **Parquet Caching**: Store downloaded Parquet files to avoid redundant network requests
- **Notebook Persistence**: Save and load user notebooks as JSON documents
- **Preference Management**: Persist user settings including Nostr keys and UI preferences
- **Quota Management**: Monitor storage usage and handle quota exceeded errors gracefully
- **Data Integrity**: Ensure stored data remains valid and recoverable

### 1.3 Design Principles

1. **Offline-First**: Cached data enables offline analysis
2. **Type Safety**: All stored data has corresponding Rust types
3. **Graceful Degradation**: Storage failures don't crash the application
4. **Transparent Quotas**: Users understand storage limits and usage

---

## 2. IndexedDB Schema

### 2.1 Database Structure

```
Database: fcps_audit_db
Version: 1

Object Stores:
├── parquet_cache      # Cached Parquet file data
├── notebooks          # User notebook documents  
├── preferences        # User settings and keys
└── metadata           # Cache metadata and timestamps
```

### 2.2 Object Store Definitions

#### parquet_cache

Stores raw Parquet file bytes with metadata for cache invalidation.

| Field | Type | Index | Description |
|-------|------|-------|-------------|
| `url` | String | Primary | Source URL (unique identifier) |
| `data` | ArrayBuffer | - | Raw Parquet bytes |
| `size` | u64 | Yes | File size in bytes |
| `etag` | Option<String> | - | HTTP ETag for validation |
| `fetched_at` | i64 | Yes | Unix timestamp of fetch |
| `last_accessed` | i64 | Yes | Unix timestamp of last use |
| `content_hash` | String | - | SHA-256 of content |

#### notebooks

Stores user-created notebook documents.

| Field | Type | Index | Description |
|-------|------|-------|-------------|
| `id` | String | Primary | UUID v4 identifier |
| `title` | String | Yes | Notebook title |
| `created_at` | i64 | Yes | Creation timestamp |
| `updated_at` | i64 | Yes | Last modification timestamp |
| `cells` | JSON | - | Array of notebook cells |
| `metadata` | JSON | - | Notebook metadata |
| `nostr_event_id` | Option<String> | Yes | Published Nostr event ID |

#### preferences

Stores user preferences and configuration.

| Field | Type | Index | Description |
|-------|------|-------|-------------|
| `key` | String | Primary | Preference identifier |
| `value` | JSON | - | Preference value |
| `updated_at` | i64 | - | Last update timestamp |

#### metadata

Stores cache statistics and housekeeping data.

| Field | Type | Index | Description |
|-------|------|-------|-------------|
| `key` | String | Primary | Metadata key |
| `value` | JSON | - | Metadata value |

---

## 3. Rust Type Definitions

### 3.1 Cache Types

```rust
use serde::{Deserialize, Serialize};
use js_sys::{ArrayBuffer, Uint8Array};
use wasm_bindgen::prelude::*;

/// Cached Parquet file entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CachedParquet {
    /// Source URL (primary key)
    pub url: String,
    /// File size in bytes
    pub size: u64,
    /// HTTP ETag for cache validation
    pub etag: Option<String>,
    /// Unix timestamp when fetched
    pub fetched_at: i64,
    /// Unix timestamp of last access
    pub last_accessed: i64,
    /// SHA-256 hash of content
    pub content_hash: String,
}

/// Cache entry with data (for retrieval)
#[derive(Debug)]
pub struct CachedParquetWithData {
    pub metadata: CachedParquet,
    pub data: Vec<u8>,
}

/// Cache validation result
#[derive(Debug, Clone, PartialEq)]
pub enum CacheValidation {
    /// Cache is valid, use stored data
    Valid,
    /// Cache is stale, revalidate with server
    Stale,
    /// No cache entry exists
    Missing,
}

/// Cache statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheStats {
    /// Total number of cached files
    pub file_count: u32,
    /// Total size in bytes
    pub total_size: u64,
    /// Oldest entry timestamp
    pub oldest_entry: Option<i64>,
    /// Newest entry timestamp  
    pub newest_entry: Option<i64>,
}
```

### 3.2 Notebook Types

```rust
/// Unique notebook identifier
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct NotebookId(pub String);

impl NotebookId {
    pub fn new() -> Self {
        Self(uuid::Uuid::new_v4().to_string())
    }
    
    pub fn from_string(s: String) -> Self {
        Self(s)
    }
}

/// Complete notebook document
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Notebook {
    /// Unique identifier
    pub id: NotebookId,
    /// Display title
    pub title: String,
    /// Creation timestamp (Unix ms)
    pub created_at: i64,
    /// Last modification timestamp (Unix ms)
    pub updated_at: i64,
    /// Ordered list of cells
    pub cells: Vec<NotebookCell>,
    /// Notebook metadata
    pub metadata: NotebookMetadata,
    /// Nostr event ID if published
    pub nostr_event_id: Option<String>,
}

/// Individual notebook cell
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotebookCell {
    /// Cell unique identifier
    pub id: String,
    /// Cell type
    pub cell_type: CellType,
    /// Cell content (SQL, Markdown, etc.)
    pub content: String,
    /// Last execution output (if applicable)
    pub output: Option<CellOutput>,
    /// Cell-specific metadata
    pub metadata: CellMetadata,
}

/// Cell type enumeration
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CellType {
    /// SQL query cell
    Sql,
    /// Markdown documentation cell
    Markdown,
    /// Chart visualization cell
    Chart,
}

/// Cell execution output
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CellOutput {
    /// Output type
    pub output_type: OutputType,
    /// Output data (JSON for tables, base64 for images)
    pub data: serde_json::Value,
    /// Execution timestamp
    pub executed_at: i64,
    /// Execution duration in milliseconds
    pub duration_ms: u32,
    /// Row count for table outputs
    pub row_count: Option<u32>,
}

/// Output type enumeration
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OutputType {
    /// Tabular data
    Table,
    /// Error message
    Error,
    /// Chart specification
    Chart,
    /// Rendered markdown
    Markdown,
}

/// Cell metadata
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct CellMetadata {
    /// Whether cell is collapsed
    #[serde(default)]
    pub collapsed: bool,
    /// Execution count
    #[serde(default)]
    pub execution_count: u32,
    /// Chart configuration (for chart cells)
    pub chart_config: Option<ChartConfig>,
}

/// Chart configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChartConfig {
    pub chart_type: String,
    pub x_column: Option<String>,
    pub y_columns: Vec<String>,
    pub options: serde_json::Value,
}

/// Notebook metadata
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct NotebookMetadata {
    /// Notebook description
    pub description: Option<String>,
    /// Tags for organization
    #[serde(default)]
    pub tags: Vec<String>,
    /// Data sources referenced
    #[serde(default)]
    pub data_sources: Vec<String>,
    /// Schema version for migrations
    #[serde(default = "default_schema_version")]
    pub schema_version: u32,
}

fn default_schema_version() -> u32 { 1 }

/// Notebook list entry (without full cell data)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotebookSummary {
    pub id: NotebookId,
    pub title: String,
    pub created_at: i64,
    pub updated_at: i64,
    pub cell_count: usize,
    pub tags: Vec<String>,
    pub nostr_event_id: Option<String>,
}
```

### 3.3 Preference Types

```rust
/// User preferences container
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct UserPreferences {
    /// UI theme
    pub theme: Theme,
    /// Nostr configuration
    pub nostr: NostrPreferences,
    /// Editor preferences
    pub editor: EditorPreferences,
    /// Query preferences
    pub query: QueryPreferences,
}

/// Theme setting
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Theme {
    Light,
    Dark,
    System,
}

impl Default for Theme {
    fn default() -> Self { Self::System }
}

/// Nostr-related preferences
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct NostrPreferences {
    /// Encrypted private key (nsec)
    /// Encrypted with user-provided passphrase
    pub encrypted_nsec: Option<EncryptedKey>,
    /// Public key (npub) - not sensitive
    pub npub: Option<String>,
    /// Preferred relay URLs
    #[serde(default)]
    pub relays: Vec<String>,
    /// Auto-publish notebooks
    #[serde(default)]
    pub auto_publish: bool,
}

/// Encrypted key storage
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EncryptedKey {
    /// Encrypted data (base64)
    pub ciphertext: String,
    /// Encryption salt (base64)
    pub salt: String,
    /// Encryption algorithm identifier
    pub algorithm: String,
}

/// Editor preferences
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EditorPreferences {
    /// Font size in pixels
    #[serde(default = "default_font_size")]
    pub font_size: u32,
    /// Tab size in spaces
    #[serde(default = "default_tab_size")]
    pub tab_size: u32,
    /// Enable line numbers
    #[serde(default = "default_true")]
    pub line_numbers: bool,
    /// Enable word wrap
    #[serde(default)]
    pub word_wrap: bool,
    /// Enable autocomplete
    #[serde(default = "default_true")]
    pub autocomplete: bool,
}

fn default_font_size() -> u32 { 14 }
fn default_tab_size() -> u32 { 2 }
fn default_true() -> bool { true }

impl Default for EditorPreferences {
    fn default() -> Self {
        Self {
            font_size: 14,
            tab_size: 2,
            line_numbers: true,
            word_wrap: false,
            autocomplete: true,
        }
    }
}

/// Query execution preferences
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryPreferences {
    /// Maximum rows to return
    #[serde(default = "default_max_rows")]
    pub max_rows: u32,
    /// Query timeout in seconds
    #[serde(default = "default_timeout")]
    pub timeout_seconds: u32,
    /// Auto-run cells on load
    #[serde(default)]
    pub auto_run: bool,
}

fn default_max_rows() -> u32 { 10000 }
fn default_timeout() -> u32 { 30 }

impl Default for QueryPreferences {
    fn default() -> Self {
        Self {
            max_rows: 10000,
            timeout_seconds: 30,
            auto_run: false,
        }
    }
}
```

### 3.4 Storage Status Types

```rust
/// Storage quota information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StorageQuota {
    /// Total quota in bytes (if available)
    pub total: Option<u64>,
    /// Used storage in bytes
    pub used: u64,
    /// Available storage in bytes (if calculable)
    pub available: Option<u64>,
    /// Usage percentage (0-100)
    pub usage_percent: Option<f32>,
}

/// Storage operation result
#[derive(Debug, Clone)]
pub enum StorageResult<T> {
    Ok(T),
    QuotaExceeded { required: u64, available: u64 },
    NotFound,
    Corrupted { key: String, error: String },
    DatabaseError(String),
}

impl<T> StorageResult<T> {
    pub fn is_ok(&self) -> bool {
        matches!(self, StorageResult::Ok(_))
    }
    
    pub fn ok(self) -> Option<T> {
        match self {
            StorageResult::Ok(v) => Some(v),
            _ => None,
        }
    }
}
```

---

## 4. Message Protocol

### 4.1 Inbound Messages (to StorageEngine)

```rust
/// Messages sent to the StorageEngine
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "payload")]
pub enum StorageCommand {
    // === Cache Operations ===
    
    /// Check if URL is cached and valid
    CheckCache {
        url: String,
        /// Optional ETag for validation
        etag: Option<String>,
    },
    
    /// Store Parquet data in cache
    CacheParquet {
        url: String,
        data: Vec<u8>,
        etag: Option<String>,
    },
    
    /// Retrieve cached Parquet data
    GetCachedParquet {
        url: String,
    },
    
    /// Remove specific cache entry
    EvictCache {
        url: String,
    },
    
    /// Clear all cached data
    ClearCache,
    
    /// Get cache statistics
    GetCacheStats,
    
    // === Notebook Operations ===
    
    /// Save notebook
    SaveNotebook {
        notebook: Notebook,
    },
    
    /// Load notebook by ID
    LoadNotebook {
        id: NotebookId,
    },
    
    /// Delete notebook
    DeleteNotebook {
        id: NotebookId,
    },
    
    /// List all notebooks
    ListNotebooks,
    
    /// Export notebook as JSON string
    ExportNotebook {
        id: NotebookId,
    },
    
    /// Import notebook from JSON string
    ImportNotebook {
        json: String,
    },
    
    // === Preference Operations ===
    
    /// Get all preferences
    GetPreferences,
    
    /// Update preferences (partial update)
    UpdatePreferences {
        preferences: UserPreferences,
    },
    
    /// Set specific preference
    SetPreference {
        key: String,
        value: serde_json::Value,
    },
    
    /// Clear all preferences
    ClearPreferences,
    
    // === Storage Management ===
    
    /// Get storage quota information
    GetQuota,
    
    /// Run storage cleanup (LRU eviction)
    RunCleanup {
        /// Target bytes to free
        target_bytes: u64,
    },
    
    /// Export all data (for backup)
    ExportAll,
    
    /// Import backup data
    ImportAll {
        data: ExportedData,
    },
}
```

### 4.2 Outbound Messages (from StorageEngine)

```rust
/// Messages emitted by the StorageEngine
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "payload")]
pub enum StorageEvent {
    // === Cache Events ===
    
    /// Cache check result
    CacheStatus {
        url: String,
        status: CacheValidation,
        metadata: Option<CachedParquet>,
    },
    
    /// Parquet cached successfully
    ParquetCached {
        url: String,
        size: u64,
    },
    
    /// Cached Parquet retrieved
    CachedParquetLoaded {
        url: String,
        data: Vec<u8>,
        metadata: CachedParquet,
    },
    
    /// Cache entry evicted
    CacheEvicted {
        url: String,
        freed_bytes: u64,
    },
    
    /// Cache cleared
    CacheCleared {
        entries_removed: u32,
        bytes_freed: u64,
    },
    
    /// Cache statistics
    CacheStats(CacheStats),
    
    // === Notebook Events ===
    
    /// Notebook saved
    NotebookSaved {
        id: NotebookId,
        updated_at: i64,
    },
    
    /// Notebook loaded
    NotebookLoaded {
        notebook: Notebook,
    },
    
    /// Notebook deleted
    NotebookDeleted {
        id: NotebookId,
    },
    
    /// Notebook list
    NotebookList {
        notebooks: Vec<NotebookSummary>,
    },
    
    /// Notebook exported
    NotebookExported {
        id: NotebookId,
        json: String,
    },
    
    /// Notebook imported
    NotebookImported {
        notebook: Notebook,
    },
    
    // === Preference Events ===
    
    /// Preferences loaded
    PreferencesLoaded {
        preferences: UserPreferences,
    },
    
    /// Preferences updated
    PreferencesUpdated {
        preferences: UserPreferences,
    },
    
    // === Storage Events ===
    
    /// Storage quota info
    QuotaInfo(StorageQuota),
    
    /// Cleanup completed
    CleanupCompleted {
        entries_removed: u32,
        bytes_freed: u64,
    },
    
    /// Data exported
    DataExported {
        data: ExportedData,
    },
    
    /// Data imported
    DataImported {
        notebooks_count: u32,
        cache_entries_count: u32,
    },
    
    // === Error Events ===
    
    /// Storage error occurred
    Error {
        operation: String,
        error: StorageError,
    },
    
    /// Quota warning (approaching limit)
    QuotaWarning {
        used: u64,
        total: u64,
        percent: f32,
    },
}

/// Storage error types
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "details")]
pub enum StorageError {
    /// Storage quota exceeded
    QuotaExceeded {
        required: u64,
        available: u64,
    },
    /// Item not found
    NotFound {
        key: String,
    },
    /// Data corruption detected
    Corrupted {
        key: String,
        message: String,
    },
    /// IndexedDB error
    DatabaseError {
        message: String,
    },
    /// Serialization error
    SerializationError {
        message: String,
    },
    /// Browser doesn't support IndexedDB
    NotSupported,
}

/// Exported data for backup/restore
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExportedData {
    pub version: u32,
    pub exported_at: i64,
    pub notebooks: Vec<Notebook>,
    pub preferences: UserPreferences,
    /// Cache metadata only (not the actual Parquet bytes)
    pub cache_metadata: Vec<CachedParquet>,
}
```

---

## 5. Caching Strategy

### 5.1 Cache Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                       Cache Lifecycle                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Request URL                                                   │
│       │                                                         │
│       ▼                                                         │
│   ┌───────────┐     Miss      ┌─────────────┐                  │
│   │ Check     │──────────────▶│ Fetch from  │                  │
│   │ Cache     │               │ Network     │                  │
│   └───────────┘               └──────┬──────┘                  │
│       │ Hit                          │                          │
│       ▼                              ▼                          │
│   ┌───────────┐               ┌─────────────┐                  │
│   │ Validate  │               │ Store in    │                  │
│   │ ETag      │               │ Cache       │                  │
│   └───────────┘               └──────┬──────┘                  │
│       │                              │                          │
│       ├── Valid ──▶ Return cached    │                          │
│       │                              │                          │
│       └── Stale ──▶ Revalidate ──────┘                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Cache Validation Rules

```rust
impl StorageEngine {
    /// Determine cache validity
    fn validate_cache(&self, entry: &CachedParquet, etag: Option<&str>) -> CacheValidation {
        // If ETags match, cache is valid
        if let (Some(cached_etag), Some(request_etag)) = (&entry.etag, etag) {
            if cached_etag == request_etag {
                return CacheValidation::Valid;
            }
        }
        
        // Check age-based staleness
        let age_hours = (now_timestamp() - entry.fetched_at) / 3600;
        
        // VDOE data updates infrequently - 7 day cache
        if entry.url.contains("doe.virginia.gov") {
            if age_hours < 168 { // 7 days
                return CacheValidation::Valid;
            }
        }
        
        // Default: 24 hour cache
        if age_hours < 24 {
            return CacheValidation::Valid;
        }
        
        CacheValidation::Stale
    }
}
```

### 5.3 LRU Eviction Policy

```rust
/// LRU eviction configuration
pub struct EvictionConfig {
    /// Maximum cache size in bytes
    pub max_cache_size: u64,
    /// Target size after eviction (80% of max)
    pub target_size: u64,
    /// Minimum entries to keep
    pub min_entries: u32,
    /// Maximum age before forced eviction (30 days)
    pub max_age_seconds: i64,
}

impl Default for EvictionConfig {
    fn default() -> Self {
        Self {
            max_cache_size: 500 * 1024 * 1024,      // 500 MB
            target_size: 400 * 1024 * 1024,         // 400 MB
            min_entries: 5,
            max_age_seconds: 30 * 24 * 3600,        // 30 days
        }
    }
}

impl StorageEngine {
    /// Run LRU eviction to free space
    async fn evict_lru(&self, target_bytes: u64) -> Result<EvictionResult, StorageError> {
        let stats = self.get_cache_stats().await?;
        
        if stats.total_size <= self.config.target_size {
            return Ok(EvictionResult::default());
        }
        
        // Get entries sorted by last_accessed (oldest first)
        let entries = self.get_cache_entries_by_access().await?;
        
        let mut freed = 0u64;
        let mut removed = 0u32;
        
        for entry in entries {
            if freed >= target_bytes {
                break;
            }
            
            // Don't evict below minimum entries
            if stats.file_count - removed <= self.config.min_entries {
                break;
            }
            
            self.delete_cache_entry(&entry.url).await?;
            freed += entry.size;
            removed += 1;
        }
        
        Ok(EvictionResult {
            entries_removed: removed,
            bytes_freed: freed,
        })
    }
}
```

---

## 6. Quota Management

### 6.1 Quota Monitoring

```rust
impl StorageEngine {
    /// Check storage quota using StorageManager API
    pub async fn check_quota(&self) -> Result<StorageQuota, StorageError> {
        // Use navigator.storage.estimate() API
        let estimate = self.storage_manager.estimate().await?;
        
        let quota = StorageQuota {
            total: estimate.quota,
            used: estimate.usage.unwrap_or(0),
            available: estimate.quota.map(|q| q.saturating_sub(estimate.usage.unwrap_or(0))),
            usage_percent: match (estimate.usage, estimate.quota) {
                (Some(used), Some(total)) if total > 0 => {
                    Some((used as f32 / total as f32) * 100.0)
                }
                _ => None,
            },
        };
        
        // Emit warning if approaching limit
        if let Some(percent) = quota.usage_percent {
            if percent > 80.0 {
                self.emit(StorageEvent::QuotaWarning {
                    used: quota.used,
                    total: quota.total.unwrap_or(0),
                    percent,
                });
            }
        }
        
        Ok(quota)
    }
}
```

### 6.2 Quota Exceeded Handling

```rust
impl StorageEngine {
    /// Attempt to store data, handling quota errors
    async fn store_with_quota_handling<T: Serialize>(
        &self,
        store: &str,
        key: &str,
        value: &T,
        size_estimate: u64,
    ) -> Result<(), StorageError> {
        // Check available space first
        let quota = self.check_quota().await?;
        
        if let Some(available) = quota.available {
            if size_estimate > available {
                // Try to free space
                let needed = size_estimate - available + (1024 * 1024); // 1MB buffer
                let eviction = self.evict_lru(needed).await?;
                
                if eviction.bytes_freed < needed {
                    return Err(StorageError::QuotaExceeded {
                        required: size_estimate,
                        available: available + eviction.bytes_freed,
                    });
                }
            }
        }
        
        // Attempt storage
        match self.idb_put(store, key, value).await {
            Ok(_) => Ok(()),
            Err(e) if e.is_quota_error() => {
                // Quota error despite checks - browser enforcement
                // Try emergency eviction
                self.evict_lru(size_estimate * 2).await?;
                
                // Retry once
                self.idb_put(store, key, value).await.map_err(|_| {
                    StorageError::QuotaExceeded {
                        required: size_estimate,
                        available: 0,
                    }
                })
            }
            Err(e) => Err(e.into()),
        }
    }
}
```

### 6.3 Storage Persistence Request

```rust
impl StorageEngine {
    /// Request persistent storage (won't be auto-cleared by browser)
    pub async fn request_persistence(&self) -> Result<bool, StorageError> {
        // Use navigator.storage.persist() API
        match self.storage_manager.persist().await {
            Ok(granted) => {
                if granted {
                    log::info!("Persistent storage granted");
                } else {
                    log::warn!("Persistent storage denied - data may be cleared");
                }
                Ok(granted)
            }
            Err(e) => {
                log::error!("Failed to request persistence: {:?}", e);
                Err(StorageError::NotSupported)
            }
        }
    }
}
```

---

## 7. Implementation Details

### 7.1 IndexedDB Wrapper

```rust
use wasm_bindgen::prelude::*;
use wasm_bindgen_futures::JsFuture;
use web_sys::{IdbDatabase, IdbObjectStore, IdbRequest, IdbTransaction};

pub struct IndexedDbWrapper {
    db: IdbDatabase,
}

impl IndexedDbWrapper {
    /// Open database with schema migration
    pub async fn open(name: &str, version: u32) -> Result<Self, StorageError> {
        let window = web_sys::window().ok_or(StorageError::NotSupported)?;
        let idb_factory = window
            .indexed_db()
            .map_err(|_| StorageError::NotSupported)?
            .ok_or(StorageError::NotSupported)?;
        
        let open_request = idb_factory
            .open_with_u32(name, version)
            .map_err(|e| StorageError::DatabaseError {
                message: format!("{:?}", e),
            })?;
        
        // Handle upgrade needed
        let on_upgrade = Closure::wrap(Box::new(move |event: web_sys::IdbVersionChangeEvent| {
            let db: IdbDatabase = event
                .target()
                .unwrap()
                .unchecked_into::<IdbRequest>()
                .result()
                .unwrap()
                .unchecked_into();
            
            Self::create_schema(&db);
        }) as Box<dyn FnMut(_)>);
        
        open_request.set_onupgradeneeded(Some(on_upgrade.as_ref().unchecked_ref()));
        on_upgrade.forget();
        
        let db = JsFuture::from(open_request)
            .await
            .map_err(|e| StorageError::DatabaseError {
                message: format!("{:?}", e),
            })?
            .unchecked_into();
        
        Ok(Self { db })
    }
    
    fn create_schema(db: &IdbDatabase) {
        // Create parquet_cache store
        if !db.object_store_names().contains(&"parquet_cache".into()) {
            let store = db
                .create_object_store_with_optional_parameters(
                    "parquet_cache",
                    &IdbObjectStoreParameters::new().key_path(Some(&"url".into())),
                )
                .unwrap();
            store.create_index_with_str("size", "size").unwrap();
            store.create_index_with_str("fetched_at", "fetched_at").unwrap();
            store.create_index_with_str("last_accessed", "last_accessed").unwrap();
        }
        
        // Create notebooks store
        if !db.object_store_names().contains(&"notebooks".into()) {
            let store = db
                .create_object_store_with_optional_parameters(
                    "notebooks",
                    &IdbObjectStoreParameters::new().key_path(Some(&"id".into())),
                )
                .unwrap();
            store.create_index_with_str("title", "title").unwrap();
            store.create_index_with_str("created_at", "created_at").unwrap();
            store.create_index_with_str("updated_at", "updated_at").unwrap();
            store.create_index_with_str("nostr_event_id", "nostr_event_id").unwrap();
        }
        
        // Create preferences store
        if !db.object_store_names().contains(&"preferences".into()) {
            db.create_object_store_with_optional_parameters(
                "preferences",
                &IdbObjectStoreParameters::new().key_path(Some(&"key".into())),
            )
            .unwrap();
        }
        
        // Create metadata store
        if !db.object_store_names().contains(&"metadata".into()) {
            db.create_object_store_with_optional_parameters(
                "metadata",
                &IdbObjectStoreParameters::new().key_path(Some(&"key".into())),
            )
            .unwrap();
        }
    }
}
```

### 7.2 StorageEngine Component

```rust
use leptos::*;
use std::collections::HashMap;

/// StorageEngine component
#[component]
pub fn StorageEngine(
    /// Incoming commands
    commands: ReadSignal<Option<StorageCommand>>,
    /// Outgoing events
    #[prop(into)]
    on_event: Callback<StorageEvent>,
) -> impl IntoView {
    let db = create_local_resource(|| (), |_| async {
        IndexedDbWrapper::open("fcps_audit_db", 1).await
    });
    
    // Process commands
    create_effect(move |_| {
        if let Some(cmd) = commands.get() {
            if let Some(Ok(db)) = db.get() {
                spawn_local(async move {
                    let event = process_command(&db, cmd).await;
                    on_event.call(event);
                });
            }
        }
    });
    
    // Component renders nothing - it's a logic-only component
    view! {}
}

async fn process_command(db: &IndexedDbWrapper, cmd: StorageCommand) -> StorageEvent {
    match cmd {
        StorageCommand::CheckCache { url, etag } => {
            match db.get::<CachedParquet>("parquet_cache", &url).await {
                Ok(Some(entry)) => {
                    let status = validate_cache(&entry, etag.as_deref());
                    StorageEvent::CacheStatus {
                        url,
                        status,
                        metadata: Some(entry),
                    }
                }
                Ok(None) => StorageEvent::CacheStatus {
                    url,
                    status: CacheValidation::Missing,
                    metadata: None,
                },
                Err(e) => StorageEvent::Error {
                    operation: "CheckCache".into(),
                    error: e,
                },
            }
        }
        
        StorageCommand::SaveNotebook { notebook } => {
            let id = notebook.id.clone();
            let updated_at = now_timestamp();
            let mut notebook = notebook;
            notebook.updated_at = updated_at;
            
            match db.put("notebooks", &notebook).await {
                Ok(_) => StorageEvent::NotebookSaved { id, updated_at },
                Err(e) => StorageEvent::Error {
                    operation: "SaveNotebook".into(),
                    error: e,
                },
            }
        }
        
        // ... handle other commands
        _ => todo!()
    }
}
```

---

## 8. Example Usage

### 8.1 Caching a Parquet File

```rust
// In DataLoader component
async fn load_with_cache(url: &str, storage: &StorageCommandSender) -> Result<Vec<u8>, Error> {
    // Check cache first
    let (tx, rx) = oneshot::channel();
    storage.send(StorageCommand::CheckCache {
        url: url.to_string(),
        etag: None,
    });
    
    match rx.await? {
        StorageEvent::CacheStatus { status: CacheValidation::Valid, .. } => {
            // Get cached data
            storage.send(StorageCommand::GetCachedParquet {
                url: url.to_string(),
            });
            
            match rx.await? {
                StorageEvent::CachedParquetLoaded { data, .. } => {
                    return Ok(data);
                }
                _ => {}
            }
        }
        _ => {}
    }
    
    // Fetch from network
    let response = fetch(url).await?;
    let etag = response.headers().get("etag");
    let data = response.bytes().await?;
    
    // Cache for next time
    storage.send(StorageCommand::CacheParquet {
        url: url.to_string(),
        data: data.clone(),
        etag,
    });
    
    Ok(data)
}
```

### 8.2 Saving a Notebook

```rust
// In NotebookEditor component
fn save_notebook(notebook: &Notebook, storage: &StorageCommandSender) {
    storage.send(StorageCommand::SaveNotebook {
        notebook: notebook.clone(),
    });
}

// Handle save confirmation
create_effect(move |_| {
    if let Some(StorageEvent::NotebookSaved { id, updated_at }) = storage_events.get() {
        // Update UI to show saved status
        set_last_saved(Some(updated_at));
        set_is_dirty(false);
    }
});
```

### 8.3 Managing Preferences

```rust
// Load preferences on startup
create_effect(move |_| {
    storage.send(StorageCommand::GetPreferences);
});

// Handle preferences loaded
create_effect(move |_| {
    if let Some(StorageEvent::PreferencesLoaded { preferences }) = storage_events.get() {
        set_theme(preferences.theme);
        set_editor_config(preferences.editor);
        
        if let Some(npub) = &preferences.nostr.npub {
            set_nostr_identity(Some(npub.clone()));
        }
    }
});

// Update theme preference
fn on_theme_change(new_theme: Theme) {
    storage.send(StorageCommand::SetPreference {
        key: "theme".into(),
        value: serde_json::to_value(&new_theme).unwrap(),
    });
}
```

### 8.4 Handling Quota Errors

```rust
// In component handling storage events
create_effect(move |_| {
    match storage_events.get() {
        Some(StorageEvent::QuotaWarning { percent, .. }) => {
            show_notification(
                NotificationType::Warning,
                &format!("Storage is {}% full. Consider clearing cache.", percent as u32),
            );
        }
        
        Some(StorageEvent::Error {
            error: StorageError::QuotaExceeded { required, available },
            ..
        }) => {
            show_dialog(Dialog::QuotaExceeded {
                required,
                available,
                on_clear_cache: move || {
                    storage.send(StorageCommand::ClearCache);
                },
            });
        }
        
        _ => {}
    }
});
```

---

## 9. Security Considerations

### 9.1 Nostr Key Protection

```rust
/// Encrypt Nostr private key before storage
pub fn encrypt_nsec(nsec: &str, passphrase: &str) -> Result<EncryptedKey, CryptoError> {
    use aes_gcm::{Aes256Gcm, Key, Nonce};
    use aes_gcm::aead::{Aead, NewAead};
    use argon2::{Argon2, password_hash::SaltString};
    use rand::rngs::OsRng;
    
    // Generate salt
    let salt = SaltString::generate(&mut OsRng);
    
    // Derive key from passphrase
    let mut key_bytes = [0u8; 32];
    Argon2::default()
        .hash_password_into(
            passphrase.as_bytes(),
            salt.as_bytes(),
            &mut key_bytes,
        )?;
    
    let key = Key::from_slice(&key_bytes);
    let cipher = Aes256Gcm::new(key);
    
    // Generate nonce
    let nonce_bytes: [u8; 12] = rand::random();
    let nonce = Nonce::from_slice(&nonce_bytes);
    
    // Encrypt
    let ciphertext = cipher.encrypt(nonce, nsec.as_bytes())?;
    
    // Combine nonce + ciphertext
    let mut combined = nonce_bytes.to_vec();
    combined.extend(ciphertext);
    
    Ok(EncryptedKey {
        ciphertext: base64::encode(&combined),
        salt: salt.to_string(),
        algorithm: "argon2-aes256gcm".into(),
    })
}

/// Decrypt Nostr private key
pub fn decrypt_nsec(encrypted: &EncryptedKey, passphrase: &str) -> Result<String, CryptoError> {
    // Reverse of encrypt_nsec
    // ...
}
```

### 9.2 Data Validation

```rust
impl StorageEngine {
    /// Validate data integrity on load
    fn validate_cached_parquet(&self, entry: &CachedParquetWithData) -> bool {
        // Verify hash matches
        let computed_hash = sha256(&entry.data);
        if computed_hash != entry.metadata.content_hash {
            log::error!(
                "Cache corruption detected for {}: hash mismatch",
                entry.metadata.url
            );
            return false;
        }
        
        // Verify it's valid Parquet
        if !entry.data.starts_with(b"PAR1") {
            log::error!(
                "Cache corruption detected for {}: invalid Parquet magic bytes",
                entry.metadata.url
            );
            return false;
        }
        
        true
    }
}
```

---

## 10. Acceptance Criteria

### 10.1 Cache Operations

- [ ] Parquet files are cached after first download
- [ ] Cached files are returned on subsequent requests without network fetch
- [ ] Cache validation correctly identifies stale entries
- [ ] LRU eviction frees oldest-accessed entries first
- [ ] Cache can be manually cleared
- [ ] Cache statistics accurately reflect stored data

### 10.2 Notebook Operations

- [ ] Notebooks save with all cells and metadata preserved
- [ ] Notebooks load with identical content to what was saved
- [ ] Notebook list shows all saved notebooks with correct metadata
- [ ] Notebooks can be deleted
- [ ] Notebooks can be exported as valid JSON
- [ ] Exported JSON can be imported as valid notebook
- [ ] Nostr event ID is preserved when set

### 10.3 Preference Operations

- [ ] Preferences persist across page reloads
- [ ] Theme preference affects UI immediately
- [ ] Editor preferences apply to SQL editor
- [ ] Nostr keys are encrypted before storage
- [ ] Nostr keys can be decrypted with correct passphrase
- [ ] Invalid passphrase fails gracefully

### 10.4 Quota Management

- [ ] Storage quota is accurately reported
- [ ] Warning emitted when storage exceeds 80%
- [ ] Quota exceeded error includes required vs available
- [ ] Automatic eviction attempts to free space before failing
- [ ] Persistent storage can be requested

### 10.5 Error Handling

- [ ] Database errors don't crash application
- [ ] Corrupted data is detected and reported
- [ ] Missing entries return NotFound (not crash)
- [ ] Quota errors provide actionable information
- [ ] Browser without IndexedDB shows appropriate message

### 10.6 Data Integrity

- [ ] Cached Parquet hash is verified on retrieval
- [ ] Invalid cache entries are automatically evicted
- [ ] Notebook schema version enables future migrations
- [ ] Export/import preserves all data correctly

---

## 11. Performance Targets

| Operation | Target | Measurement |
|-----------|--------|-------------|
| Cache lookup | < 10ms | Time from command to status event |
| Cache retrieval (10MB) | < 100ms | Time to load cached Parquet |
| Notebook save | < 50ms | Time from command to saved event |
| Notebook list | < 20ms | Time to retrieve all summaries |
| Preference update | < 10ms | Time to persist change |
| Quota check | < 20ms | Time for StorageManager estimate |

---

## 12. Future Enhancements

1. **Sync Across Devices**: Use Nostr relays to sync notebooks between devices
2. **Compression**: Compress cached Parquet files to save space
3. **Selective Caching**: Allow users to pin important files (exempt from eviction)
4. **Cache Preloading**: Background fetch commonly-used datasets
5. **Conflict Resolution**: Handle concurrent edits to same notebook
6. **Audit Log**: Track all storage operations for debugging
