# NotesEngine Component Specification

**Version**: 1.0  
**Status**: Draft  
**Last Updated**: 2026-01-31

## Table of Contents

1. [Purpose and Responsibilities](#purpose-and-responsibilities)
2. [Architecture Overview](#architecture-overview)
3. [Rust Type Definitions](#rust-type-definitions)
4. [Message Protocol](#message-protocol)
5. [Key Management Flow](#key-management-flow)
6. [NIP-05 Verification Flow](#nip-05-verification-flow)
7. [Relay Configuration](#relay-configuration)
8. [Example Usage](#example-usage)
9. [Acceptance Criteria](#acceptance-criteria)

---

## Purpose and Responsibilities

The NotesEngine is a Tauri-side component responsible for publishing and fetching notes via the Nostr protocol. It enables users to share insights, annotations, and findings from their data analysis with the broader community.

### Core Responsibilities

1. **Note Publishing**: Publish notes attached to datasets, queries, cells, or notebooks
2. **Community Fetching**: Retrieve and display notes from community members
3. **Key Management**: Support multiple signing strategies (NIP-07, NIP-46, manual, ephemeral)
4. **Identity Verification**: Handle NIP-05 verification for `virginiafreedom.tech` domain
5. **Relay Management**: Reuse relay configuration from the Feedback component

### Supported Event Kinds

| Kind | Name | Use Case |
|------|------|----------|
| 1 | Short Text Note | Quick annotations, comments, insights |
| 30023 | Long-form Article | Detailed analysis, reports, methodology |

### Required Hashtags

All published notes MUST include:
- `#fredco-data` - Primary community tag
- `#[dataset-name]` - Context-specific tag (e.g., `#vdoe-table15`, `#fcps-budget`)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
├─────────────────────────────────────────────────────────────┤
│  NoteComposer  │  NoteFeed  │  KeyManager  │  NIP05Badge    │
└───────┬────────────┬────────────┬──────────────┬────────────┘
        │            │            │              │
        ▼            ▼            ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Tauri IPC Bridge                          │
└───────┬────────────┬────────────┬──────────────┬────────────┘
        │            │            │              │
        ▼            ▼            ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│                      NotesEngine                             │
├─────────────────────────────────────────────────────────────┤
│  Publisher  │  Fetcher  │  KeyStore  │  NIP05Verifier       │
└───────┬────────────┬────────────┬──────────────┬────────────┘
        │            │            │              │
        ▼            ▼            ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│                    RelayPool (shared)                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Rust Type Definitions

### Key Management Types

```rust
use nostr_sdk::{Keys, PublicKey, SecretKey};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;

/// Supported key management strategies
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum KeyStrategy {
    /// NIP-07: Browser extension signing (Alby, nos2x, etc.)
    Nip07,
    
    /// NIP-46: Remote signer / Nostr Connect
    Nip46 {
        /// Connection URI (bunker://...)
        connection_uri: String,
        /// Optional relay for communication
        relay_url: Option<String>,
    },
    
    /// Manual: User-provided nsec
    Manual {
        /// Encrypted nsec (encrypted at rest)
        encrypted_nsec: String,
    },
    
    /// Ephemeral: Generated per-session, not persisted
    Ephemeral,
}

/// Current key state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KeyState {
    /// Active strategy
    pub strategy: KeyStrategy,
    /// Public key (npub) - always available once configured
    pub public_key: Option<String>,
    /// Whether the key is ready for signing
    pub is_ready: bool,
    /// NIP-05 verification status
    pub nip05_status: Nip05Status,
}

/// NIP-05 verification status
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum Nip05Status {
    /// Not checked yet
    Unknown,
    /// Verification in progress
    Checking,
    /// Verified with identifier
    Verified {
        identifier: String, // e.g., "alice@virginiafreedom.tech"
    },
    /// Not verified
    Unverified,
    /// Verification failed (network error, etc.)
    Failed {
        reason: String,
    },
}

/// Secure key storage handle
pub struct KeyStore {
    /// Current key strategy
    strategy: Arc<RwLock<Option<KeyStrategy>>>,
    /// Cached keys (for Manual/Ephemeral)
    keys: Arc<RwLock<Option<Keys>>>,
    /// NIP-46 signer connection
    nip46_client: Arc<RwLock<Option<Nip46Client>>>,
}
```

### Note Types

```rust
use chrono::{DateTime, Utc};
use nostr_sdk::{Event, EventId, Tag};

/// Attachment context for a note
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum NoteAttachment {
    /// Attached to a dataset
    Dataset {
        dataset_id: String,
        dataset_name: String,
    },
    /// Attached to a specific query
    Query {
        query_id: String,
        query_hash: String,
        sql_preview: String, // First 100 chars
    },
    /// Attached to a notebook cell
    Cell {
        notebook_id: String,
        cell_id: String,
        cell_type: String,
    },
    /// Attached to entire notebook
    Notebook {
        notebook_id: String,
        notebook_name: String,
    },
    /// Standalone note (no attachment)
    Standalone,
}

/// Request to publish a short note (kind 1)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PublishNoteRequest {
    /// Note content (plain text, may include markdown)
    pub content: String,
    /// Attachment context
    pub attachment: NoteAttachment,
    /// Additional hashtags (beyond required ones)
    pub extra_tags: Vec<String>,
    /// Reply to existing note (event ID)
    pub reply_to: Option<String>,
}

/// Request to publish long-form article (kind 30023)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PublishArticleRequest {
    /// Article title
    pub title: String,
    /// Article content (markdown)
    pub content: String,
    /// Summary/excerpt
    pub summary: Option<String>,
    /// Article identifier (d-tag, for replaceable events)
    pub identifier: String,
    /// Attachment context
    pub attachment: NoteAttachment,
    /// Additional hashtags
    pub extra_tags: Vec<String>,
    /// Published timestamp (defaults to now)
    pub published_at: Option<DateTime<Utc>>,
}

/// Published note result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PublishedNote {
    /// Event ID (hex)
    pub event_id: String,
    /// Event ID (bech32 note1...)
    pub event_id_bech32: String,
    /// Author public key
    pub author_pubkey: String,
    /// Created timestamp
    pub created_at: DateTime<Utc>,
    /// Relays where published
    pub published_to: Vec<RelayPublishResult>,
}

/// Result of publishing to a single relay
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RelayPublishResult {
    pub relay_url: String,
    pub success: bool,
    pub message: Option<String>,
}

/// A fetched community note
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommunityNote {
    /// Event ID
    pub event_id: String,
    /// Author public key (hex)
    pub author_pubkey: String,
    /// Author public key (npub)
    pub author_npub: String,
    /// Author NIP-05 identifier (if verified)
    pub author_nip05: Option<String>,
    /// Note content
    pub content: String,
    /// Event kind
    pub kind: u64,
    /// Created timestamp
    pub created_at: DateTime<Utc>,
    /// Tags
    pub tags: Vec<NoteTag>,
    /// Attachment context (parsed from tags)
    pub attachment: Option<NoteAttachment>,
    /// Reply count (if fetched)
    pub reply_count: Option<u32>,
}

/// Simplified tag representation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NoteTag {
    pub tag_type: String,
    pub values: Vec<String>,
}

/// Filter for fetching community notes
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct NotesFilter {
    /// Filter by hashtag
    pub hashtags: Vec<String>,
    /// Filter by author pubkeys
    pub authors: Vec<String>,
    /// Filter by attachment type
    pub attachment_type: Option<String>,
    /// Filter by dataset
    pub dataset_id: Option<String>,
    /// Limit results
    pub limit: Option<u32>,
    /// Since timestamp
    pub since: Option<DateTime<Utc>>,
    /// Until timestamp
    pub until: Option<DateTime<Utc>>,
}
```

### Engine State Types

```rust
/// NotesEngine configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotesEngineConfig {
    /// Relay URLs (reused from Feedback component)
    pub relays: Vec<RelayConfig>,
    /// Default hashtags for all notes
    pub default_hashtags: Vec<String>,
    /// NIP-05 domain for verification prompts
    pub nip05_domain: String,
    /// Contact info for NIP-05 registration
    pub nip05_contact: Nip05ContactInfo,
}

/// Relay configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RelayConfig {
    pub url: String,
    pub read: bool,
    pub write: bool,
}

/// NIP-05 registration contact info
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Nip05ContactInfo {
    /// Organization name
    pub organization: String,
    /// Contact URL
    pub url: String,
    /// Contact email (optional)
    pub email: Option<String>,
    /// Instructions for registration
    pub instructions: String,
}

/// NotesEngine state for frontend
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotesEngineState {
    /// Key management state
    pub key_state: KeyState,
    /// Connected relays
    pub connected_relays: Vec<RelayStatus>,
    /// Engine ready status
    pub is_ready: bool,
}

/// Relay connection status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RelayStatus {
    pub url: String,
    pub connected: bool,
    pub read_enabled: bool,
    pub write_enabled: bool,
}
```

### Error Types

```rust
use thiserror::Error;

#[derive(Debug, Error, Serialize, Deserialize)]
pub enum NotesEngineError {
    #[error("No signing key configured")]
    NoKeyConfigured,
    
    #[error("Key not ready for signing: {reason}")]
    KeyNotReady { reason: String },
    
    #[error("NIP-07 extension not available")]
    Nip07NotAvailable,
    
    #[error("NIP-46 connection failed: {reason}")]
    Nip46ConnectionFailed { reason: String },
    
    #[error("Invalid nsec format")]
    InvalidNsec,
    
    #[error("Signing failed: {reason}")]
    SigningFailed { reason: String },
    
    #[error("Relay error: {relay} - {reason}")]
    RelayError { relay: String, reason: String },
    
    #[error("No relays connected")]
    NoRelaysConnected,
    
    #[error("NIP-05 verification failed: {reason}")]
    Nip05VerificationFailed { reason: String },
    
    #[error("Event not found: {event_id}")]
    EventNotFound { event_id: String },
    
    #[error("Content too long: {length} > {max}")]
    ContentTooLong { length: usize, max: usize },
}
```

---

## Message Protocol

### Tauri Commands

```rust
/// Initialize the NotesEngine
#[tauri::command]
async fn notes_init(
    config: Option<NotesEngineConfig>,
    state: State<'_, NotesEngineState>,
) -> Result<NotesEngineState, NotesEngineError>;

/// Configure key management strategy
#[tauri::command]
async fn notes_configure_key(
    strategy: KeyStrategy,
    state: State<'_, NotesEngineState>,
) -> Result<KeyState, NotesEngineError>;

/// Get current key state
#[tauri::command]
async fn notes_get_key_state(
    state: State<'_, NotesEngineState>,
) -> Result<KeyState, NotesEngineError>;

/// Clear current key (logout)
#[tauri::command]
async fn notes_clear_key(
    state: State<'_, NotesEngineState>,
) -> Result<(), NotesEngineError>;

/// Verify NIP-05 for current key
#[tauri::command]
async fn notes_verify_nip05(
    state: State<'_, NotesEngineState>,
) -> Result<Nip05Status, NotesEngineError>;

/// Publish a short note (kind 1)
#[tauri::command]
async fn notes_publish(
    request: PublishNoteRequest,
    state: State<'_, NotesEngineState>,
) -> Result<PublishedNote, NotesEngineError>;

/// Publish a long-form article (kind 30023)
#[tauri::command]
async fn notes_publish_article(
    request: PublishArticleRequest,
    state: State<'_, NotesEngineState>,
) -> Result<PublishedNote, NotesEngineError>;

/// Fetch community notes
#[tauri::command]
async fn notes_fetch(
    filter: NotesFilter,
    state: State<'_, NotesEngineState>,
) -> Result<Vec<CommunityNote>, NotesEngineError>;

/// Fetch a single note by ID
#[tauri::command]
async fn notes_fetch_by_id(
    event_id: String,
    state: State<'_, NotesEngineState>,
) -> Result<CommunityNote, NotesEngineError>;

/// Get current engine state
#[tauri::command]
async fn notes_get_state(
    state: State<'_, NotesEngineState>,
) -> Result<NotesEngineState, NotesEngineError>;
```

### Frontend Events (Tauri -> Frontend)

```typescript
// Event types emitted to frontend
interface NotesEvents {
  // Key state changed
  'notes:key-state-changed': {
    keyState: KeyState;
  };
  
  // NIP-05 verification completed
  'notes:nip05-verified': {
    status: Nip05Status;
  };
  
  // Note published successfully
  'notes:published': {
    note: PublishedNote;
  };
  
  // New community note received (subscription)
  'notes:new-note': {
    note: CommunityNote;
  };
  
  // Relay connection status changed
  'notes:relay-status': {
    relays: RelayStatus[];
  };
}
```

---

## Key Management Flow

### Strategy Selection Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Key Configuration UI                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Choose how to sign notes:                                  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ [Browser Extension (NIP-07)]                        │   │
│  │ Use Alby, nos2x, or similar extension               │   │
│  │ ✓ Most secure - keys never leave extension          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ [Remote Signer (NIP-46)]                            │   │
│  │ Connect to Nostr Connect compatible signer          │   │
│  │ ✓ Secure - keys stay on your signer device          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ [Enter Secret Key]                                  │   │
│  │ Paste your nsec directly                            │   │
│  │ ⚠ Less secure - key stored locally                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ [Generate Temporary Key]                            │   │
│  │ Create ephemeral identity for this session          │   │
│  │ ⚠ Not persistent - identity lost on close           │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### NIP-07 Flow (Browser Extension)

```
User                    Frontend                 Backend              Extension
  │                        │                        │                     │
  │  Select NIP-07         │                        │                     │
  │───────────────────────>│                        │                     │
  │                        │                        │                     │
  │                        │  Check window.nostr    │                     │
  │                        │───────────────────────>│                     │
  │                        │                        │                     │
  │                        │  Request getPublicKey()│                     │
  │                        │<──────────────────────────────────────────-->│
  │                        │                        │                     │
  │                        │  notes_configure_key   │                     │
  │                        │  (Nip07)               │                     │
  │                        │───────────────────────>│                     │
  │                        │                        │                     │
  │                        │  KeyState { ready }    │                     │
  │                        │<───────────────────────│                     │
  │                        │                        │                     │
  │  [On Sign Request]     │                        │                     │
  │                        │  signEvent(event)      │                     │
  │                        │<──────────────────────────────────────────-->│
  │                        │                        │  User approves      │
  │                        │                        │<────────────────────│
  │                        │  Signed event          │                     │
  │                        │<──────────────────────────────────────────────
```

### NIP-46 Flow (Remote Signer)

```
User                    Frontend                 Backend               Signer
  │                        │                        │                     │
  │  Enter bunker:// URI   │                        │                     │
  │───────────────────────>│                        │                     │
  │                        │                        │                     │
  │                        │  notes_configure_key   │                     │
  │                        │  (Nip46 { uri })       │                     │
  │                        │───────────────────────>│                     │
  │                        │                        │                     │
  │                        │                        │  Connect to signer  │
  │                        │                        │────────────────────>│
  │                        │                        │                     │
  │                        │                        │  get_public_key     │
  │                        │                        │────────────────────>│
  │                        │                        │                     │
  │                        │                        │  Public key         │
  │                        │                        │<────────────────────│
  │                        │                        │                     │
  │                        │  KeyState { ready }    │                     │
  │                        │<───────────────────────│                     │
  │                        │                        │                     │
  │  [On Sign Request]     │                        │                     │
  │                        │  notes_publish         │                     │
  │                        │───────────────────────>│                     │
  │                        │                        │  sign_event         │
  │                        │                        │────────────────────>│
  │                        │                        │                     │
  │                        │                        │  Signed event       │
  │                        │                        │<────────────────────│
  │                        │                        │                     │
  │                        │  PublishedNote         │                     │
  │                        │<───────────────────────│                     │
```

### Manual nsec Flow

```
User                    Frontend                 Backend
  │                        │                        │
  │  Enter nsec            │                        │
  │───────────────────────>│                        │
  │                        │                        │
  │                        │  Validate nsec format  │
  │                        │  (client-side)         │
  │                        │                        │
  │                        │  notes_configure_key   │
  │                        │  (Manual { nsec })     │
  │                        │───────────────────────>│
  │                        │                        │
  │                        │                        │  Encrypt nsec
  │                        │                        │  Store in keyring
  │                        │                        │
  │                        │  KeyState { ready }    │
  │                        │<───────────────────────│
```

### Ephemeral Key Flow

```
User                    Frontend                 Backend
  │                        │                        │
  │  Select Ephemeral      │                        │
  │───────────────────────>│                        │
  │                        │                        │
  │                        │  notes_configure_key   │
  │                        │  (Ephemeral)           │
  │                        │───────────────────────>│
  │                        │                        │
  │                        │                        │  Generate new Keys
  │                        │                        │  Store in memory only
  │                        │                        │
  │                        │  KeyState {            │
  │                        │    ready,              │
  │                        │    public_key,         │
  │                        │    ⚠ ephemeral warning │
  │                        │  }                     │
  │                        │<───────────────────────│
  │                        │                        │
  │  ⚠ Warning displayed:  │                        │
  │  "This identity will   │                        │
  │   be lost when you     │                        │
  │   close the app"       │                        │
```

---

## NIP-05 Verification Flow

### Verification Process

```
User                    Frontend                 Backend              DNS/HTTP
  │                        │                        │                     │
  │  [Key configured]      │                        │                     │
  │                        │                        │                     │
  │                        │  notes_verify_nip05    │                     │
  │                        │───────────────────────>│                     │
  │                        │                        │                     │
  │                        │                        │  GET /.well-known/  │
  │                        │                        │  nostr.json?name=*  │
  │                        │                        │────────────────────>│
  │                        │                        │                     │
  │                        │                        │  { names: {...} }   │
  │                        │                        │<────────────────────│
  │                        │                        │                     │
  │                        │                        │  Match pubkey?
  │                        │                        │
  │                        │  Nip05Status           │
  │                        │<───────────────────────│
  │                        │                        │
  │  [If Unverified]       │                        │
  │                        │                        │
  │  ┌────────────────────────────────────────┐    │
  │  │ Your identity is not verified.         │    │
  │  │                                         │    │
  │  │ Get a verified @virginiafreedom.tech   │    │
  │  │ identity from Shenandoah Bitcoin Club! │    │
  │  │                                         │    │
  │  │ Contact: shenandoahbitcoin.club         │    │
  │  │                                         │    │
  │  │ [Learn More]  [Dismiss]  [Don't Ask]   │    │
  │  └────────────────────────────────────────┘    │
```

### NIP-05 Badge Component

```typescript
interface Nip05BadgeProps {
  status: Nip05Status;
  showPrompt?: boolean;
}

// Display states:
// - Unknown: Gray "?" icon
// - Checking: Spinning indicator
// - Verified: Green checkmark + identifier
// - Unverified: Yellow warning + "Get Verified" link
// - Failed: Red X + retry option
```

### Verification Prompt Content

```typescript
const NIP05_PROMPT = {
  organization: "Shenandoah Bitcoin Club",
  domain: "virginiafreedom.tech",
  url: "https://shenandoahbitcoin.club",
  instructions: `
    Get your verified Nostr identity!
    
    A @virginiafreedom.tech NIP-05 identifier:
    - Proves you're part of the VA freedom community
    - Makes your notes more trustworthy
    - Helps others find and verify you
    
    Contact Shenandoah Bitcoin Club to register:
    https://shenandoahbitcoin.club
  `,
};
```

---

## Relay Configuration

### Shared Relay Pool

The NotesEngine reuses the relay configuration from the Feedback component to maintain consistency and reduce connection overhead.

```rust
/// Default relay configuration
pub fn default_relays() -> Vec<RelayConfig> {
    vec![
        RelayConfig {
            url: "wss://relay.damus.io".into(),
            read: true,
            write: true,
        },
        RelayConfig {
            url: "wss://nos.lol".into(),
            read: true,
            write: true,
        },
        RelayConfig {
            url: "wss://relay.nostr.band".into(),
            read: true,
            write: true,
        },
        RelayConfig {
            url: "wss://relay.primal.net".into(),
            read: true,
            write: true,
        },
        // Virginia-focused relay (if available)
        RelayConfig {
            url: "wss://relay.virginiafreedom.tech".into(),
            read: true,
            write: true,
        },
    ]
}
```

### Relay Selection Logic

```rust
impl NotesEngine {
    /// Get relays for publishing (write-enabled)
    fn write_relays(&self) -> Vec<&RelayConfig> {
        self.config.relays.iter()
            .filter(|r| r.write)
            .collect()
    }
    
    /// Get relays for fetching (read-enabled)
    fn read_relays(&self) -> Vec<&RelayConfig> {
        self.config.relays.iter()
            .filter(|r| r.read)
            .collect()
    }
    
    /// Publish to all write relays, return mixed results
    async fn publish_to_relays(&self, event: Event) -> Vec<RelayPublishResult> {
        let futures = self.write_relays().iter().map(|relay| {
            self.publish_to_relay(relay, event.clone())
        });
        
        futures::future::join_all(futures).await
    }
}
```

---

## Example Usage

### Frontend: Configure Key (NIP-07)

```typescript
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';

// Check for NIP-07 extension
async function setupNip07() {
  if (!window.nostr) {
    throw new Error('No NIP-07 extension found. Install Alby or nos2x.');
  }
  
  // Get public key from extension
  const pubkey = await window.nostr.getPublicKey();
  
  // Configure backend
  const keyState = await invoke<KeyState>('notes_configure_key', {
    strategy: { type: 'nip07' }
  });
  
  console.log('Key configured:', keyState.public_key);
  
  // Verify NIP-05
  const nip05Status = await invoke<Nip05Status>('notes_verify_nip05');
  
  if (nip05Status.status === 'unverified') {
    showNip05Prompt();
  }
  
  return keyState;
}
```

### Frontend: Publish Note

```typescript
async function publishDatasetNote(
  content: string,
  datasetId: string,
  datasetName: string
) {
  const request: PublishNoteRequest = {
    content,
    attachment: {
      type: 'dataset',
      dataset_id: datasetId,
      dataset_name: datasetName,
    },
    extra_tags: ['virginia-schools', 'fiscal-audit'],
    reply_to: null,
  };
  
  try {
    const result = await invoke<PublishedNote>('notes_publish', { request });
    
    console.log('Published:', result.event_id_bech32);
    console.log('To relays:', result.published_to
      .filter(r => r.success)
      .map(r => r.relay_url)
    );
    
    return result;
  } catch (error) {
    if (error.code === 'NoKeyConfigured') {
      showKeySetupDialog();
    }
    throw error;
  }
}
```

### Frontend: Fetch Community Notes

```typescript
async function fetchDatasetNotes(datasetId: string) {
  const filter: NotesFilter = {
    hashtags: ['fredco-data'],
    dataset_id: datasetId,
    limit: 50,
  };
  
  const notes = await invoke<CommunityNote[]>('notes_fetch', { filter });
  
  // Group by author verification status
  const verified = notes.filter(n => n.author_nip05);
  const unverified = notes.filter(n => !n.author_nip05);
  
  return { verified, unverified, all: notes };
}
```

### Frontend: Subscribe to New Notes

```typescript
import { listen } from '@tauri-apps/api/event';

async function subscribeToNotes() {
  const unlisten = await listen<{ note: CommunityNote }>(
    'notes:new-note',
    (event) => {
      const note = event.payload.note;
      
      // Add to feed
      addNoteToFeed(note);
      
      // Show notification for verified users
      if (note.author_nip05?.endsWith('@virginiafreedom.tech')) {
        showNotification(`New note from ${note.author_nip05}`);
      }
    }
  );
  
  return unlisten;
}
```

### Backend: Event Construction

```rust
impl NotesEngine {
    /// Build a kind 1 note event
    fn build_note_event(&self, request: &PublishNoteRequest) -> Result<UnsignedEvent> {
        let mut tags = vec![
            // Required hashtags
            Tag::hashtag("fredco-data"),
        ];
        
        // Add attachment-specific tags
        match &request.attachment {
            NoteAttachment::Dataset { dataset_id, dataset_name } => {
                tags.push(Tag::hashtag(dataset_name.to_lowercase().replace(' ', '-')));
                tags.push(Tag::custom(
                    TagKind::Custom("dataset".into()),
                    vec![dataset_id.clone()]
                ));
            }
            NoteAttachment::Query { query_id, query_hash, .. } => {
                tags.push(Tag::custom(
                    TagKind::Custom("query".into()),
                    vec![query_id.clone(), query_hash.clone()]
                ));
            }
            // ... other attachment types
            _ => {}
        }
        
        // Add extra hashtags
        for tag in &request.extra_tags {
            tags.push(Tag::hashtag(tag));
        }
        
        // Add reply reference
        if let Some(reply_to) = &request.reply_to {
            let event_id = EventId::from_hex(reply_to)?;
            tags.push(Tag::event(event_id));
        }
        
        Ok(UnsignedEvent::new(
            Kind::TextNote,
            request.content.clone(),
            tags,
        ))
    }
    
    /// Build a kind 30023 article event
    fn build_article_event(&self, request: &PublishArticleRequest) -> Result<UnsignedEvent> {
        let mut tags = vec![
            Tag::identifier(&request.identifier),
            Tag::title(&request.title),
            Tag::hashtag("fredco-data"),
        ];
        
        if let Some(summary) = &request.summary {
            tags.push(Tag::custom(
                TagKind::Custom("summary".into()),
                vec![summary.clone()]
            ));
        }
        
        if let Some(published_at) = &request.published_at {
            tags.push(Tag::custom(
                TagKind::Custom("published_at".into()),
                vec![published_at.timestamp().to_string()]
            ));
        }
        
        // Add attachment and extra tags...
        
        Ok(UnsignedEvent::new(
            Kind::LongFormContent,
            request.content.clone(),
            tags,
        ))
    }
}
```

---

## Acceptance Criteria

### Key Management

- [ ] **NIP-07**: Users can sign notes using browser extensions (Alby, nos2x)
- [ ] **NIP-07**: Graceful error when no extension is available
- [ ] **NIP-46**: Users can connect to remote signers via bunker:// URI
- [ ] **NIP-46**: Connection persists across app restarts (stored URI)
- [ ] **Manual**: Users can enter nsec directly
- [ ] **Manual**: nsec is encrypted at rest using system keyring
- [ ] **Ephemeral**: Users can generate temporary keys
- [ ] **Ephemeral**: Clear warning displayed about identity loss
- [ ] **All**: Public key (npub) displayed after configuration
- [ ] **All**: Key can be cleared/changed at any time

### Note Publishing

- [ ] Short notes (kind 1) publish successfully to configured relays
- [ ] Long-form articles (kind 30023) publish with proper metadata
- [ ] All notes include required `#fredco-data` hashtag
- [ ] Dataset-attached notes include dataset-specific hashtag
- [ ] Reply threading works correctly (e-tag references)
- [ ] Publish results show success/failure per relay
- [ ] Content length validation (kind 1: 64KB, kind 30023: 100KB)

### Note Fetching

- [ ] Fetch notes by hashtag filter
- [ ] Fetch notes by author pubkey
- [ ] Fetch notes by dataset attachment
- [ ] Pagination via limit/since/until
- [ ] Real-time subscription to new notes
- [ ] Author NIP-05 status included in fetched notes

### NIP-05 Verification

- [ ] Automatic verification check on key configuration
- [ ] Verified status displayed with identifier badge
- [ ] Unverified users see prompt for virginiafreedom.tech
- [ ] Prompt links to Shenandoah Bitcoin Club
- [ ] Users can dismiss/permanently hide verification prompt
- [ ] Manual re-verification available

### Relay Management

- [ ] Reuses relay pool from Feedback component
- [ ] Connection status visible in UI
- [ ] Graceful handling of relay disconnections
- [ ] At least one successful relay publish = success

### Error Handling

- [ ] Clear error messages for all failure modes
- [ ] Retry option for transient failures
- [ ] Offline mode: queue notes for later publishing
- [ ] Invalid nsec format detected before storage

### Security

- [ ] Manual nsec encrypted using OS keyring
- [ ] No plaintext secrets in logs
- [ ] NIP-46 connections validated
- [ ] Ephemeral keys never persisted

---

## Dependencies

### Rust Crates

```toml
[dependencies]
nostr-sdk = "0.35"
tokio = { version = "1", features = ["full"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
thiserror = "1"
keyring = "2"  # OS keyring for secret storage
```

### Frontend

```json
{
  "dependencies": {
    "@tauri-apps/api": "^2.0",
    "nostr-tools": "^2.0"  // For NIP-07 interaction
  }
}
```

---

## Future Enhancements

1. **NIP-57 Zaps**: Allow zapping notes with Lightning
2. **NIP-51 Lists**: Curated lists of fredco-data notes
3. **NIP-65 Relay Lists**: Dynamic relay discovery from user profiles
4. **Encrypted DMs**: Private note sharing between verified users
5. **Note Reactions**: Like/boost community notes
