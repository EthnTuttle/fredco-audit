//! StorageEngine types for IndexedDB persistence

use crate::editor::Notebook;
use crate::messages::Timestamp;
use serde::{Deserialize, Serialize};
use tsify::Tsify;

// ============================================================================
// Cache Types
// ============================================================================

/// Cached Parquet file metadata (without data bytes)
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct CachedParquet {
    /// Source URL (primary key)
    pub url: String,
    /// File size in bytes
    pub size: u64,
    /// HTTP ETag for cache validation
    #[serde(skip_serializing_if = "Option::is_none")]
    pub etag: Option<String>,
    /// Unix timestamp (ms) when fetched
    pub fetched_at: Timestamp,
    /// Unix timestamp (ms) of last access
    pub last_accessed: Timestamp,
    /// SHA-256 hash of content
    pub content_hash: String,
}

/// Cache validation result
#[derive(Tsify, Serialize, Deserialize, Clone, Debug, PartialEq)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub enum CacheValidation {
    /// Cache is valid, use stored data
    Valid,
    /// Cache is stale, revalidate with server
    Stale,
    /// No cache entry exists
    Missing,
}

/// Cache statistics
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct CacheStats {
    /// Total number of cached files
    pub file_count: u32,
    /// Total size in bytes
    pub total_size: u64,
    /// Oldest entry timestamp
    #[serde(skip_serializing_if = "Option::is_none")]
    pub oldest_entry: Option<Timestamp>,
    /// Newest entry timestamp
    #[serde(skip_serializing_if = "Option::is_none")]
    pub newest_entry: Option<Timestamp>,
}

// ============================================================================
// Notebook Storage Types
// ============================================================================

/// Notebook summary for list view (without full cell data)
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct NotebookSummary {
    /// Unique notebook ID
    pub id: String,
    /// Display title
    pub title: String,
    /// Creation timestamp
    pub created_at: Timestamp,
    /// Last modified timestamp
    pub updated_at: Timestamp,
    /// Number of cells
    pub cell_count: u32,
    /// Tags for organization
    #[serde(default)]
    pub tags: Vec<String>,
    /// Published Nostr event ID (if published)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub nostr_event_id: Option<String>,
}

// ============================================================================
// Preference Types
// ============================================================================

/// User preferences container
#[derive(Tsify, Serialize, Deserialize, Clone, Debug, Default)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct UserPreferences {
    /// UI theme
    #[serde(default)]
    pub theme: Theme,
    /// Nostr configuration
    #[serde(default)]
    pub nostr: NostrPreferences,
    /// Editor preferences
    #[serde(default)]
    pub editor: EditorPreferences,
    /// Query preferences
    #[serde(default)]
    pub query: QueryPreferences,
}

/// Theme setting
#[derive(Tsify, Serialize, Deserialize, Clone, Debug, PartialEq)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub enum Theme {
    Light,
    Dark,
    System,
}

impl Default for Theme {
    fn default() -> Self {
        Self::System
    }
}

/// Nostr-related preferences
#[derive(Tsify, Serialize, Deserialize, Clone, Debug, Default)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct NostrPreferences {
    /// Encrypted private key (nsec) - encrypted with user passphrase
    #[serde(skip_serializing_if = "Option::is_none")]
    pub encrypted_nsec: Option<EncryptedKey>,
    /// Public key (npub) - not sensitive
    #[serde(skip_serializing_if = "Option::is_none")]
    pub npub: Option<String>,
    /// Preferred relay URLs
    #[serde(default)]
    pub relays: Vec<String>,
    /// Auto-publish notebooks on save
    #[serde(default)]
    pub auto_publish: bool,
}

/// Encrypted key storage
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct EncryptedKey {
    /// Encrypted data (base64)
    pub ciphertext: String,
    /// Encryption salt (base64)
    pub salt: String,
    /// Encryption algorithm identifier
    pub algorithm: String,
}

/// Editor preferences
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
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

fn default_font_size() -> u32 {
    14
}
fn default_tab_size() -> u32 {
    2
}
fn default_true() -> bool {
    true
}

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
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct QueryPreferences {
    /// Maximum rows to return
    #[serde(default = "default_max_rows")]
    pub max_rows: u32,
    /// Query timeout in seconds
    #[serde(default = "default_timeout")]
    pub timeout_seconds: u32,
    /// Auto-run cells on notebook load
    #[serde(default)]
    pub auto_run: bool,
}

fn default_max_rows() -> u32 {
    10000
}
fn default_timeout() -> u32 {
    30
}

impl Default for QueryPreferences {
    fn default() -> Self {
        Self {
            max_rows: 10000,
            timeout_seconds: 30,
            auto_run: false,
        }
    }
}

// ============================================================================
// Storage Status Types
// ============================================================================

/// Storage quota information
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct StorageQuota {
    /// Total quota in bytes (if available)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub total: Option<u64>,
    /// Used storage in bytes
    pub used: u64,
    /// Available storage in bytes (if calculable)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub available: Option<u64>,
    /// Usage percentage (0-100)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub usage_percent: Option<f32>,
}

/// Exported data for backup/restore
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ExportedData {
    /// Export format version
    pub version: u32,
    /// Export timestamp
    pub exported_at: Timestamp,
    /// All notebooks
    pub notebooks: Vec<Notebook>,
    /// User preferences
    pub preferences: UserPreferences,
    /// Cache metadata only (not actual Parquet bytes)
    pub cache_metadata: Vec<CachedParquet>,
}

// ============================================================================
// Storage Commands (Inbound Messages)
// ============================================================================

/// Commands sent to the StorageEngine
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(tag = "type", content = "payload")]
pub enum StorageCommand {
    // === Cache Operations ===
    /// Check if URL is cached and valid
    #[serde(rename = "check_cache")]
    CheckCache {
        url: String,
        /// Optional ETag for validation
        #[serde(skip_serializing_if = "Option::is_none")]
        etag: Option<String>,
    },

    /// Store Parquet data in cache
    #[serde(rename = "cache_parquet")]
    CacheParquet {
        url: String,
        /// Base64-encoded Parquet data
        data_base64: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        etag: Option<String>,
    },

    /// Retrieve cached Parquet data
    #[serde(rename = "get_cached_parquet")]
    GetCachedParquet { url: String },

    /// Remove specific cache entry
    #[serde(rename = "evict_cache")]
    EvictCache { url: String },

    /// Clear all cached data
    #[serde(rename = "clear_cache")]
    ClearCache,

    /// Get cache statistics
    #[serde(rename = "get_cache_stats")]
    GetCacheStats,

    // === Notebook Operations ===
    /// Save notebook
    #[serde(rename = "save_notebook")]
    SaveNotebook { notebook: Notebook },

    /// Load notebook by ID
    #[serde(rename = "load_notebook")]
    LoadNotebook { id: String },

    /// Delete notebook
    #[serde(rename = "delete_notebook")]
    DeleteNotebook { id: String },

    /// List all notebooks
    #[serde(rename = "list_notebooks")]
    ListNotebooks,

    /// Export notebook as JSON string
    #[serde(rename = "export_notebook")]
    ExportNotebook { id: String },

    /// Import notebook from JSON string
    #[serde(rename = "import_notebook")]
    ImportNotebook { json: String },

    // === Preference Operations ===
    /// Get all preferences
    #[serde(rename = "get_preferences")]
    GetPreferences,

    /// Update preferences
    #[serde(rename = "update_preferences")]
    UpdatePreferences { preferences: UserPreferences },

    /// Clear all preferences
    #[serde(rename = "clear_preferences")]
    ClearPreferences,

    // === Storage Management ===
    /// Get storage quota information
    #[serde(rename = "get_quota")]
    GetQuota,

    /// Run storage cleanup (LRU eviction)
    #[serde(rename = "run_cleanup")]
    RunCleanup {
        /// Target bytes to free
        target_bytes: u64,
    },

    /// Export all data for backup
    #[serde(rename = "export_all")]
    ExportAll,

    /// Import backup data
    #[serde(rename = "import_all")]
    ImportAll { data: ExportedData },
}

// ============================================================================
// Storage Events (Outbound Messages)
// ============================================================================

/// Events emitted by the StorageEngine
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(tag = "type", content = "payload")]
pub enum StorageEvent {
    // === Cache Events ===
    /// Cache check result
    #[serde(rename = "cache_status")]
    CacheStatus {
        url: String,
        status: CacheValidation,
        #[serde(skip_serializing_if = "Option::is_none")]
        metadata: Option<CachedParquet>,
    },

    /// Parquet cached successfully
    #[serde(rename = "parquet_cached")]
    ParquetCached { url: String, size: u64 },

    /// Cached Parquet retrieved
    #[serde(rename = "cached_parquet_loaded")]
    CachedParquetLoaded {
        url: String,
        /// Base64-encoded Parquet data
        data_base64: String,
        metadata: CachedParquet,
    },

    /// Cache entry evicted
    #[serde(rename = "cache_evicted")]
    CacheEvicted { url: String, freed_bytes: u64 },

    /// Cache cleared
    #[serde(rename = "cache_cleared")]
    CacheCleared {
        entries_removed: u32,
        bytes_freed: u64,
    },

    /// Cache statistics
    #[serde(rename = "cache_stats")]
    CacheStats(CacheStats),

    // === Notebook Events ===
    /// Notebook saved
    #[serde(rename = "notebook_saved")]
    NotebookSaved { id: String, updated_at: Timestamp },

    /// Notebook loaded
    #[serde(rename = "notebook_loaded")]
    NotebookLoaded { notebook: Notebook },

    /// Notebook deleted
    #[serde(rename = "notebook_deleted")]
    NotebookDeleted { id: String },

    /// Notebook list
    #[serde(rename = "notebook_list")]
    NotebookList { notebooks: Vec<NotebookSummary> },

    /// Notebook exported
    #[serde(rename = "notebook_exported")]
    NotebookExported { id: String, json: String },

    /// Notebook imported
    #[serde(rename = "notebook_imported")]
    NotebookImported { notebook: Notebook },

    // === Preference Events ===
    /// Preferences loaded
    #[serde(rename = "preferences_loaded")]
    PreferencesLoaded { preferences: UserPreferences },

    /// Preferences updated
    #[serde(rename = "preferences_updated")]
    PreferencesUpdated { preferences: UserPreferences },

    /// Preferences cleared
    #[serde(rename = "preferences_cleared")]
    PreferencesCleared,

    // === Storage Events ===
    /// Storage quota info
    #[serde(rename = "quota_info")]
    QuotaInfo(StorageQuota),

    /// Cleanup completed
    #[serde(rename = "cleanup_completed")]
    CleanupCompleted {
        entries_removed: u32,
        bytes_freed: u64,
    },

    /// Data exported
    #[serde(rename = "data_exported")]
    DataExported { data: ExportedData },

    /// Data imported
    #[serde(rename = "data_imported")]
    DataImported {
        notebooks_count: u32,
        cache_entries_count: u32,
    },

    // === Error/Warning Events ===
    /// Storage error occurred
    #[serde(rename = "error")]
    Error {
        operation: String,
        error: StorageError,
    },

    /// Quota warning (approaching limit)
    #[serde(rename = "quota_warning")]
    QuotaWarning { used: u64, total: u64, percent: f32 },
}

/// Storage error types
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(tag = "type", content = "details")]
pub enum StorageError {
    /// Storage quota exceeded
    #[serde(rename = "quota_exceeded")]
    QuotaExceeded { required: u64, available: u64 },

    /// Item not found
    #[serde(rename = "not_found")]
    NotFound { key: String },

    /// Data corruption detected
    #[serde(rename = "corrupted")]
    Corrupted { key: String, message: String },

    /// IndexedDB error
    #[serde(rename = "database_error")]
    DatabaseError { message: String },

    /// Serialization error
    #[serde(rename = "serialization_error")]
    SerializationError { message: String },

    /// Browser doesn't support IndexedDB
    #[serde(rename = "not_supported")]
    NotSupported,
}

// ============================================================================
// Eviction Configuration
// ============================================================================

/// LRU eviction configuration
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct EvictionConfig {
    /// Maximum cache size in bytes (default: 500 MB)
    pub max_cache_size: u64,
    /// Target size after eviction (default: 400 MB = 80% of max)
    pub target_size: u64,
    /// Minimum entries to keep
    pub min_entries: u32,
    /// Maximum age before forced eviction in seconds (default: 30 days)
    pub max_age_seconds: i64,
}

impl Default for EvictionConfig {
    fn default() -> Self {
        Self {
            max_cache_size: 500 * 1024 * 1024, // 500 MB
            target_size: 400 * 1024 * 1024,    // 400 MB
            min_entries: 5,
            max_age_seconds: 30 * 24 * 3600, // 30 days
        }
    }
}

/// Eviction result
#[derive(Tsify, Serialize, Deserialize, Clone, Debug, Default)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct EvictionResult {
    /// Number of entries removed
    pub entries_removed: u32,
    /// Bytes freed
    pub bytes_freed: u64,
}
