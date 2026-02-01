//! Base message types for inter-component communication

use serde::{Deserialize, Serialize};
use tsify::Tsify;

/// Unique identifier for message correlation
pub type MessageId = String;

/// Timestamp in milliseconds since Unix epoch
pub type Timestamp = u64;

/// Base message envelope for all requests
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct Request<T> {
    /// Unique message ID for request/response matching
    pub id: MessageId,
    /// Request timestamp
    pub timestamp: Timestamp,
    /// Request payload
    pub payload: T,
}

/// Base message envelope for all responses
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct Response<T> {
    /// Matches the request ID
    pub id: MessageId,
    /// Response timestamp
    pub timestamp: Timestamp,
    /// Execution time in milliseconds
    pub execution_time_ms: u32,
    /// Response result
    pub result: MessageResult<T>,
}

/// Result wrapper for all responses
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(tag = "status")]
pub enum MessageResult<T> {
    #[serde(rename = "ok")]
    Ok { data: T },
    #[serde(rename = "error")]
    Error { error: ErrorInfo },
}

/// Error information
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ErrorInfo {
    /// Error code for programmatic handling
    pub code: ErrorCode,
    /// Human-readable error message
    pub message: String,
    /// Optional additional details
    #[serde(skip_serializing_if = "Option::is_none")]
    pub details: Option<String>,
}

/// Standard error codes
#[derive(Tsify, Serialize, Deserialize, Clone, Debug, PartialEq)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub enum ErrorCode {
    /// Resource not found
    NotFound,
    /// Invalid query syntax
    InvalidQuery,
    /// Failed to parse data
    ParseError,
    /// Network request failed
    NetworkError,
    /// Storage operation failed
    StorageError,
    /// Authentication/authorization failed
    AuthError,
    /// Operation cancelled
    Cancelled,
    /// Resource limit exceeded
    LimitExceeded,
    /// Unknown error
    Unknown,
}

impl<T> MessageResult<T> {
    /// Create a success result
    pub fn ok(data: T) -> Self {
        MessageResult::Ok { data }
    }

    /// Create an error result
    pub fn error(code: ErrorCode, message: impl Into<String>) -> Self {
        MessageResult::Error {
            error: ErrorInfo {
                code,
                message: message.into(),
                details: None,
            },
        }
    }

    /// Create an error result with details
    pub fn error_with_details(
        code: ErrorCode,
        message: impl Into<String>,
        details: impl Into<String>,
    ) -> Self {
        MessageResult::Error {
            error: ErrorInfo {
                code,
                message: message.into(),
                details: Some(details.into()),
            },
        }
    }

    /// Check if result is ok
    pub fn is_ok(&self) -> bool {
        matches!(self, MessageResult::Ok { .. })
    }

    /// Check if result is error
    pub fn is_error(&self) -> bool {
        matches!(self, MessageResult::Error { .. })
    }
}

/// Generate a new message ID
pub fn generate_id() -> MessageId {
    use std::time::{SystemTime, UNIX_EPOCH};
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    format!("{:x}", now)
}

/// Get current timestamp
pub fn now() -> Timestamp {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_millis() as u64
}
