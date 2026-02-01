//! NotesEngine types for Nostr integration

use crate::messages::Timestamp;
use serde::{Deserialize, Serialize};
use tsify::Tsify;

/// Nostr key management strategy
#[derive(Tsify, Serialize, Deserialize, Clone, Debug, PartialEq)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(tag = "type")]
pub enum KeyStrategy {
    /// Use browser extension (NIP-07)
    #[serde(rename = "nip07")]
    Nip07,
    /// Use remote signer (NIP-46)
    #[serde(rename = "nip46")]
    Nip46 { relay_url: String, pubkey: String },
    /// Manual nsec entry
    #[serde(rename = "manual")]
    Manual { nsec: String },
    /// Ephemeral (generated per session)
    #[serde(rename = "ephemeral")]
    Ephemeral,
}

/// Note attachment type
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(tag = "type")]
pub enum NoteAttachment {
    /// Attached to a dataset
    #[serde(rename = "dataset")]
    Dataset { name: String },
    /// Attached to a specific query
    #[serde(rename = "query")]
    Query {
        sql: String,
        cell_id: Option<String>,
    },
    /// Attached to a cell
    #[serde(rename = "cell")]
    Cell { cell_id: String },
    /// Attached to a notebook
    #[serde(rename = "notebook")]
    Notebook { notebook_id: String },
    /// General note (no specific attachment)
    #[serde(rename = "general")]
    General,
}

/// Request to publish a note
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct PublishNoteRequest {
    /// Note content (plain text or markdown)
    pub content: String,
    /// Optional title (for long-form)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title: Option<String>,
    /// What the note is attached to
    pub attachment: NoteAttachment,
    /// Additional tags
    #[serde(default)]
    pub tags: Vec<String>,
    /// Whether to publish as long-form article (kind 30023)
    #[serde(default)]
    pub long_form: bool,
}

/// Result of publishing a note
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct PublishNoteResult {
    /// Event ID
    pub event_id: String,
    /// Author pubkey
    pub pubkey: String,
    /// Relays published to
    pub relays: Vec<String>,
    /// Note URL (for sharing)
    pub url: String,
}

/// Request to fetch community notes
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct FetchNotesRequest {
    /// Filter by hashtag
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hashtag: Option<String>,
    /// Filter by author pubkey
    #[serde(skip_serializing_if = "Option::is_none")]
    pub author: Option<String>,
    /// Filter by attachment type
    #[serde(skip_serializing_if = "Option::is_none")]
    pub attachment_type: Option<String>,
    /// Maximum notes to fetch
    #[serde(default = "default_limit")]
    pub limit: u32,
    /// Fetch notes since timestamp
    #[serde(skip_serializing_if = "Option::is_none")]
    pub since: Option<Timestamp>,
}

fn default_limit() -> u32 {
    50
}

/// A community note
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct CommunityNote {
    /// Event ID
    pub id: String,
    /// Author pubkey
    pub pubkey: String,
    /// Author display name (from profile)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub author_name: Option<String>,
    /// Author NIP-05 identifier
    #[serde(skip_serializing_if = "Option::is_none")]
    pub author_nip05: Option<String>,
    /// Whether author is verified
    pub author_verified: bool,
    /// Note content
    pub content: String,
    /// Title (for long-form)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title: Option<String>,
    /// Creation timestamp
    pub created_at: Timestamp,
    /// Hashtags
    pub tags: Vec<String>,
    /// Attachment info
    #[serde(skip_serializing_if = "Option::is_none")]
    pub attachment: Option<NoteAttachment>,
    /// Reaction count
    #[serde(default)]
    pub reactions: u32,
    /// Reply count
    #[serde(default)]
    pub replies: u32,
}

/// Fetch notes result
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct FetchNotesResult {
    /// Notes
    pub notes: Vec<CommunityNote>,
    /// Whether more notes are available
    pub has_more: bool,
}

/// NIP-05 verification request
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct VerifyNip05Request {
    /// NIP-05 identifier (e.g., "user@virginiafreedom.tech")
    pub identifier: String,
    /// Expected pubkey
    pub pubkey: String,
}

/// NIP-05 verification result
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct VerifyNip05Result {
    /// Whether verified
    pub verified: bool,
    /// Relays associated with the identifier
    #[serde(default)]
    pub relays: Vec<String>,
}

/// Nostr relay configuration
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct RelayConfig {
    /// Relay URL
    pub url: String,
    /// Whether to read from this relay
    pub read: bool,
    /// Whether to write to this relay
    pub write: bool,
}

/// Nostr configuration
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct NostrConfig {
    /// Key strategy
    pub key_strategy: KeyStrategy,
    /// Configured relays
    pub relays: Vec<RelayConfig>,
    /// Default hashtags to include
    #[serde(default)]
    pub default_tags: Vec<String>,
}

impl Default for NostrConfig {
    fn default() -> Self {
        Self {
            key_strategy: KeyStrategy::Ephemeral,
            relays: vec![
                RelayConfig {
                    url: "wss://relay.damus.io".to_string(),
                    read: true,
                    write: true,
                },
                RelayConfig {
                    url: "wss://nos.lol".to_string(),
                    read: true,
                    write: true,
                },
                RelayConfig {
                    url: "wss://relay.nostr.band".to_string(),
                    read: true,
                    write: false,
                },
            ],
            default_tags: vec!["fredco-data".to_string()],
        }
    }
}

/// User profile from Nostr
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct NostrProfile {
    /// Pubkey
    pub pubkey: String,
    /// Display name
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    /// About text
    #[serde(skip_serializing_if = "Option::is_none")]
    pub about: Option<String>,
    /// Profile picture URL
    #[serde(skip_serializing_if = "Option::is_none")]
    pub picture: Option<String>,
    /// NIP-05 identifier
    #[serde(skip_serializing_if = "Option::is_none")]
    pub nip05: Option<String>,
    /// Whether NIP-05 is verified
    pub nip05_verified: bool,
}

/// Current authentication state
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(tag = "status")]
pub enum AuthState {
    /// Not authenticated
    #[serde(rename = "unauthenticated")]
    Unauthenticated,
    /// Authenticated with profile
    #[serde(rename = "authenticated")]
    Authenticated {
        profile: NostrProfile,
        key_strategy: KeyStrategy,
    },
    /// Authentication in progress
    #[serde(rename = "pending")]
    Pending,
    /// Authentication failed
    #[serde(rename = "error")]
    Error { message: String },
}
