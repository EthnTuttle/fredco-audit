# UI Shell Component Specification

**Version**: 1.0  
**Status**: Draft  
**Last Updated**: 2026-01-31

---

## 1. Purpose

The UI Shell is the thin orchestration layer for the FCPS Audit application. It manages the overall application layout, routes messages between components, and maintains minimal global state. The shell contains **no business logic**—it exists solely to coordinate the display and communication of domain-specific components.

### 1.1 Core Responsibilities

| Responsibility | Description |
|----------------|-------------|
| Layout Management | Render sidebar, tab bar, and content panels |
| Message Routing | Pass messages between components via the Message Bus |
| Global State | Track loaded files, active tab, and panel visibility |
| UI Chrome | Provide minimal application frame (title bar, status bar) |
| Keyboard Shortcuts | Handle global hotkeys for navigation and actions |

### 1.2 Non-Responsibilities

The UI Shell does **NOT**:
- Parse or analyze audit data
- Render charts or visualizations
- Make decisions about data presentation
- Contain domain-specific validation logic
- Directly call Tauri commands (delegates to components)

---

## 2. Layout Structure

```
+------------------------------------------------------------------+
|                         Title Bar                                 |
+------------------------------------------------------------------+
|        |                    Tab Bar                               |
|        +----------------------------------------------------------+
|        |                                                          |
|  Side  |                                                          |
|  bar   |                   Content Panel                          |
|        |                                                          |
|        |                                                          |
|        +----------------------------------------------------------+
|        |                   Status Bar                             |
+------------------------------------------------------------------+
```

### 2.1 Sidebar

- **Width**: 240px (collapsible to 48px icons-only mode)
- **Sections**:
  - File Browser (data sources)
  - Navigation (audit sections)
  - Quick Actions

### 2.2 Tab Bar

- **Height**: 36px
- **Features**:
  - Closable tabs with middle-click
  - Tab overflow menu when > 8 tabs
  - Drag-to-reorder support
  - Active tab indicator

### 2.3 Content Panel

- **Behavior**: Renders the active tab's component
- **Supports**: Split views (horizontal/vertical)
- **Default**: Welcome/Dashboard view when no tabs open

### 2.4 Status Bar

- **Height**: 24px
- **Displays**: Current file, sync status, notifications

---

## 3. Message Bus Implementation

The Message Bus enables decoupled communication between components using a publish-subscribe pattern with typed messages.

### 3.1 TypeScript Types

```typescript
// message-bus.ts

/**
 * All possible message types in the application.
 * Each message has a discriminated union type for type safety.
 */
export type Message =
  | FileMessage
  | TabMessage
  | NavigationMessage
  | DataMessage
  | UIMessage;

// --- File Messages ---
export interface FileLoadRequest {
  type: "file:load:request";
  payload: {
    path: string;
    fileType: "json" | "csv" | "xlsx";
  };
}

export interface FileLoadSuccess {
  type: "file:load:success";
  payload: {
    path: string;
    data: unknown;
    metadata: FileMetadata;
  };
}

export interface FileLoadError {
  type: "file:load:error";
  payload: {
    path: string;
    error: string;
  };
}

export type FileMessage = FileLoadRequest | FileLoadSuccess | FileLoadError;

// --- Tab Messages ---
export interface TabOpen {
  type: "tab:open";
  payload: {
    id: string;
    title: string;
    component: ComponentType;
    props?: Record<string, unknown>;
  };
}

export interface TabClose {
  type: "tab:close";
  payload: {
    id: string;
  };
}

export interface TabActivate {
  type: "tab:activate";
  payload: {
    id: string;
  };
}

export type TabMessage = TabOpen | TabClose | TabActivate;

// --- Navigation Messages ---
export interface NavigateTo {
  type: "nav:goto";
  payload: {
    section: AuditSection;
    params?: Record<string, string>;
  };
}

export type NavigationMessage = NavigateTo;

// --- Data Messages ---
export interface DataQuery {
  type: "data:query";
  payload: {
    queryId: string;
    source: DataSource;
    filters?: QueryFilter[];
  };
}

export interface DataResult {
  type: "data:result";
  payload: {
    queryId: string;
    rows: unknown[];
    totalCount: number;
  };
}

export type DataMessage = DataQuery | DataResult;

// --- UI Messages ---
export interface UINotification {
  type: "ui:notify";
  payload: {
    level: "info" | "warn" | "error";
    message: string;
    duration?: number;
  };
}

export interface UISidebarToggle {
  type: "ui:sidebar:toggle";
  payload?: {
    collapsed?: boolean;
  };
}

export type UIMessage = UINotification | UISidebarToggle;

// --- Supporting Types ---
export type ComponentType =
  | "dashboard"
  | "enrollment"
  | "expenditures"
  | "staffing"
  | "comparison"
  | "raw-data";

export type AuditSection =
  | "overview"
  | "enrollment"
  | "spending"
  | "administration"
  | "peer-comparison"
  | "findings";

export type DataSource =
  | "vdoe-table8"
  | "vdoe-table15"
  | "vdoe-table17"
  | "vdoe-table18"
  | "vdoe-table19"
  | "county-budget"
  | "fcps-budget";

export interface FileMetadata {
  size: number;
  lastModified: Date;
  rowCount?: number;
}

export interface QueryFilter {
  field: string;
  operator: "eq" | "gt" | "lt" | "contains" | "in";
  value: unknown;
}
```

### 3.2 Message Bus Class

```typescript
// message-bus.ts (continued)

type MessageHandler<T extends Message = Message> = (message: T) => void;
type Unsubscribe = () => void;

/**
 * Central message bus for component communication.
 * Implements a type-safe pub/sub pattern.
 */
export class MessageBus {
  private handlers: Map<string, Set<MessageHandler>> = new Map();
  private history: Message[] = [];
  private readonly maxHistory = 100;

  /**
   * Subscribe to messages of a specific type.
   * Returns an unsubscribe function.
   */
  subscribe<T extends Message>(
    messageType: T["type"],
    handler: MessageHandler<T>
  ): Unsubscribe {
    if (!this.handlers.has(messageType)) {
      this.handlers.set(messageType, new Set());
    }

    const handlers = this.handlers.get(messageType)!;
    handlers.add(handler as MessageHandler);

    return () => {
      handlers.delete(handler as MessageHandler);
      if (handlers.size === 0) {
        this.handlers.delete(messageType);
      }
    };
  }

  /**
   * Subscribe to all messages matching a prefix.
   * Example: subscribePrefix("file:") receives all file messages.
   */
  subscribePrefix(
    prefix: string,
    handler: MessageHandler
  ): Unsubscribe {
    const wrappedHandler = (message: Message) => {
      if (message.type.startsWith(prefix)) {
        handler(message);
      }
    };

    // Store reference for cleanup
    const unsubscribes: Unsubscribe[] = [];

    // Subscribe to all current matching types
    for (const type of this.handlers.keys()) {
      if (type.startsWith(prefix)) {
        unsubscribes.push(this.subscribe(type as Message["type"], wrappedHandler));
      }
    }

    return () => {
      unsubscribes.forEach((unsub) => unsub());
    };
  }

  /**
   * Publish a message to all subscribers.
   */
  publish<T extends Message>(message: T): void {
    // Add to history
    this.history.push(message);
    if (this.history.length > this.maxHistory) {
      this.history.shift();
    }

    // Notify handlers
    const handlers = this.handlers.get(message.type);
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(message);
        } catch (error) {
          console.error(`Error in message handler for ${message.type}:`, error);
        }
      });
    }
  }

  /**
   * Get recent message history (for debugging).
   */
  getHistory(): readonly Message[] {
    return Object.freeze([...this.history]);
  }

  /**
   * Clear all subscriptions (for testing/cleanup).
   */
  clear(): void {
    this.handlers.clear();
    this.history = [];
  }
}

// Singleton instance
export const messageBus = new MessageBus();
```

### 3.3 React Hook

```typescript
// use-message-bus.ts

import { useEffect, useCallback } from "react";
import { messageBus, Message, MessageHandler } from "./message-bus";

/**
 * React hook for subscribing to messages.
 */
export function useMessageBus<T extends Message>(
  messageType: T["type"],
  handler: MessageHandler<T>,
  deps: React.DependencyList = []
): void {
  useEffect(() => {
    return messageBus.subscribe(messageType, handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messageType, ...deps]);
}

/**
 * React hook for publishing messages.
 */
export function usePublish(): <T extends Message>(message: T) => void {
  return useCallback((message) => {
    messageBus.publish(message);
  }, []);
}
```

---

## 4. Rust Type Definitions

The Rust backend maintains authoritative state that syncs with the TypeScript frontend.

### 4.1 UI State Types

```rust
// src-tauri/src/ui_state.rs

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Represents the complete UI state of the application.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UIState {
    pub tabs: TabState,
    pub sidebar: SidebarState,
    pub loaded_files: Vec<LoadedFile>,
    pub notifications: Vec<Notification>,
}

impl Default for UIState {
    fn default() -> Self {
        Self {
            tabs: TabState::default(),
            sidebar: SidebarState::default(),
            loaded_files: Vec::new(),
            notifications: Vec::new(),
        }
    }
}

/// Tab management state.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TabState {
    pub tabs: Vec<Tab>,
    pub active_tab_id: Option<String>,
    pub tab_order: Vec<String>,
}

impl Default for TabState {
    fn default() -> Self {
        Self {
            tabs: Vec::new(),
            active_tab_id: None,
            tab_order: Vec::new(),
        }
    }
}

/// Individual tab representation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Tab {
    pub id: String,
    pub title: String,
    pub component: ComponentType,
    pub props: HashMap<String, serde_json::Value>,
    pub dirty: bool,
    pub closable: bool,
}

/// Supported component types for tabs.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ComponentType {
    Dashboard,
    Enrollment,
    Expenditures,
    Staffing,
    Comparison,
    RawData,
}

/// Sidebar state.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SidebarState {
    pub collapsed: bool,
    pub width: u32,
    pub active_section: SidebarSection,
}

impl Default for SidebarState {
    fn default() -> Self {
        Self {
            collapsed: false,
            width: 240,
            active_section: SidebarSection::Files,
        }
    }
}

/// Sidebar sections.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SidebarSection {
    Files,
    Navigation,
    Actions,
}

/// Represents a loaded data file.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LoadedFile {
    pub path: String,
    pub file_type: FileType,
    pub loaded_at: chrono::DateTime<chrono::Utc>,
    pub row_count: Option<usize>,
    pub size_bytes: u64,
}

/// Supported file types.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum FileType {
    Json,
    Csv,
    Xlsx,
}

/// UI notification.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Notification {
    pub id: String,
    pub level: NotificationLevel,
    pub message: String,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub read: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum NotificationLevel {
    Info,
    Warn,
    Error,
}
```

### 4.2 Tauri Commands

```rust
// src-tauri/src/commands/ui.rs

use crate::ui_state::{Tab, UIState};
use tauri::State;
use std::sync::Mutex;

/// Get current UI state.
#[tauri::command]
pub fn get_ui_state(state: State<'_, Mutex<UIState>>) -> Result<UIState, String> {
    let state = state.lock().map_err(|e| e.to_string())?;
    Ok(state.clone())
}

/// Open a new tab.
#[tauri::command]
pub fn open_tab(
    tab: Tab,
    state: State<'_, Mutex<UIState>>,
) -> Result<(), String> {
    let mut state = state.lock().map_err(|e| e.to_string())?;
    
    // Check if tab already exists
    if state.tabs.tabs.iter().any(|t| t.id == tab.id) {
        // Activate existing tab
        state.tabs.active_tab_id = Some(tab.id);
        return Ok(());
    }
    
    let tab_id = tab.id.clone();
    state.tabs.tabs.push(tab);
    state.tabs.tab_order.push(tab_id.clone());
    state.tabs.active_tab_id = Some(tab_id);
    
    Ok(())
}

/// Close a tab.
#[tauri::command]
pub fn close_tab(
    tab_id: String,
    state: State<'_, Mutex<UIState>>,
) -> Result<(), String> {
    let mut state = state.lock().map_err(|e| e.to_string())?;
    
    // Remove tab
    state.tabs.tabs.retain(|t| t.id != tab_id);
    state.tabs.tab_order.retain(|id| id != &tab_id);
    
    // Update active tab if needed
    if state.tabs.active_tab_id.as_ref() == Some(&tab_id) {
        state.tabs.active_tab_id = state.tabs.tab_order.last().cloned();
    }
    
    Ok(())
}

/// Toggle sidebar collapsed state.
#[tauri::command]
pub fn toggle_sidebar(
    collapsed: Option<bool>,
    state: State<'_, Mutex<UIState>>,
) -> Result<bool, String> {
    let mut state = state.lock().map_err(|e| e.to_string())?;
    
    state.sidebar.collapsed = collapsed.unwrap_or(!state.sidebar.collapsed);
    
    Ok(state.sidebar.collapsed)
}
```

---

## 5. Tab Management

### 5.1 Tab Lifecycle

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   CREATED   │────>│   ACTIVE    │────>│   CLOSED    │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │
       │                   v
       │            ┌─────────────┐
       └───────────>│  INACTIVE   │
                    └─────────────┘
```

### 5.2 Tab Operations

| Operation | Trigger | Message Type | Behavior |
|-----------|---------|--------------|----------|
| Open | User action | `tab:open` | Create new tab, activate it |
| Close | Click X, Ctrl+W | `tab:close` | Remove tab, activate previous |
| Activate | Click tab | `tab:activate` | Switch active tab |
| Reorder | Drag & drop | `tab:reorder` | Update tab order array |

### 5.3 Tab Component

```typescript
// Tab.tsx

interface TabProps {
  tab: Tab;
  isActive: boolean;
  onActivate: () => void;
  onClose: () => void;
}

export function Tab({ tab, isActive, onActivate, onClose }: TabProps) {
  const handleClose = (e: React.MouseEvent) => {
    e.stopPropagation();
    onClose();
  };

  const handleMiddleClick = (e: React.MouseEvent) => {
    if (e.button === 1 && tab.closable) {
      onClose();
    }
  };

  return (
    <div
      className={`tab ${isActive ? "tab--active" : ""}`}
      onClick={onActivate}
      onMouseDown={handleMiddleClick}
      role="tab"
      aria-selected={isActive}
    >
      <span className="tab__title">{tab.title}</span>
      {tab.dirty && <span className="tab__dirty-indicator" />}
      {tab.closable && (
        <button
          className="tab__close"
          onClick={handleClose}
          aria-label={`Close ${tab.title}`}
        >
          ×
        </button>
      )}
    </div>
  );
}
```

---

## 6. Global Keyboard Shortcuts

### 6.1 Shortcut Map

| Shortcut | Action | Message |
|----------|--------|---------|
| `Ctrl+Tab` | Next tab | `tab:activate` (next) |
| `Ctrl+Shift+Tab` | Previous tab | `tab:activate` (prev) |
| `Ctrl+W` | Close current tab | `tab:close` |
| `Ctrl+1..9` | Activate tab N | `tab:activate` (by index) |
| `Ctrl+B` | Toggle sidebar | `ui:sidebar:toggle` |
| `Ctrl+K` | Command palette | `ui:command-palette:open` |
| `Ctrl+O` | Open file | `file:open-dialog` |
| `Ctrl+R` | Reload data | `data:reload` |
| `Escape` | Close modal/panel | `ui:dismiss` |

### 6.2 Shortcut Handler

```typescript
// keyboard-shortcuts.ts

import { messageBus } from "./message-bus";

interface Shortcut {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  action: () => void;
}

const shortcuts: Shortcut[] = [
  {
    key: "Tab",
    ctrl: true,
    action: () => messageBus.publish({ type: "tab:next", payload: {} }),
  },
  {
    key: "Tab",
    ctrl: true,
    shift: true,
    action: () => messageBus.publish({ type: "tab:prev", payload: {} }),
  },
  {
    key: "w",
    ctrl: true,
    action: () => messageBus.publish({ type: "tab:close-current", payload: {} }),
  },
  {
    key: "b",
    ctrl: true,
    action: () => messageBus.publish({ type: "ui:sidebar:toggle", payload: {} }),
  },
  {
    key: "k",
    ctrl: true,
    action: () => messageBus.publish({ type: "ui:command-palette:open", payload: {} }),
  },
];

export function initKeyboardShortcuts(): () => void {
  const handler = (e: KeyboardEvent) => {
    for (const shortcut of shortcuts) {
      if (
        e.key === shortcut.key &&
        !!e.ctrlKey === !!shortcut.ctrl &&
        !!e.shiftKey === !!shortcut.shift &&
        !!e.altKey === !!shortcut.alt
      ) {
        e.preventDefault();
        shortcut.action();
        return;
      }
    }

    // Handle Ctrl+1..9 for tab switching
    if (e.ctrlKey && /^[1-9]$/.test(e.key)) {
      e.preventDefault();
      const index = parseInt(e.key, 10) - 1;
      messageBus.publish({
        type: "tab:activate-index",
        payload: { index },
      });
    }
  };

  document.addEventListener("keydown", handler);
  return () => document.removeEventListener("keydown", handler);
}
```

---

## 7. Example Message Flows

### 7.1 Opening a Data File

```
User clicks file in sidebar
           │
           v
┌─────────────────────┐
│  Sidebar Component  │
│  publish: file:load:request
└─────────────────────┘
           │
           v
┌─────────────────────┐
│  Data Service       │
│  (subscribes to file:load:*)
│  - Calls Tauri command
│  - Receives data
│  publish: file:load:success
└─────────────────────┘
           │
           v
┌─────────────────────┐
│  UI Shell           │
│  (subscribes to file:load:success)
│  - Updates loaded_files state
│  publish: tab:open
└─────────────────────┘
           │
           v
┌─────────────────────┐
│  Tab Bar            │
│  (subscribes to tab:*)
│  - Creates new tab
│  - Renders component
└─────────────────────┘
```

### 7.2 Navigating to Audit Section

```
User clicks "Spending" in navigation
           │
           v
┌─────────────────────┐
│  Navigation         │
│  publish: nav:goto { section: "spending" }
└─────────────────────┘
           │
           v
┌─────────────────────┐
│  UI Shell           │
│  (subscribes to nav:*)
│  - Checks if tab exists
│  publish: tab:open OR tab:activate
└─────────────────────┘
           │
           v
┌─────────────────────┐
│  Spending Component │
│  - Loads required data
│  publish: data:query
└─────────────────────┘
```

### 7.3 Error Notification Flow

```
Data parsing fails
           │
           v
┌─────────────────────┐
│  Data Service       │
│  publish: file:load:error
└─────────────────────┘
           │
           v
┌─────────────────────┐
│  Error Handler      │
│  (subscribes to *:error)
│  publish: ui:notify { level: "error", ... }
└─────────────────────┘
           │
           v
┌─────────────────────┐
│  Status Bar         │
│  (subscribes to ui:notify)
│  - Shows toast notification
└─────────────────────┘
```

---

## 8. Acceptance Criteria

### 8.1 Layout

- [ ] Application renders with sidebar, tab bar, content panel, and status bar
- [ ] Sidebar collapses to 48px width when toggled
- [ ] Tab bar shows all open tabs with active indicator
- [ ] Tab overflow menu appears when more than 8 tabs are open
- [ ] Content panel fills remaining space and scrolls appropriately
- [ ] Status bar shows current file and notification count

### 8.2 Message Bus

- [ ] Messages are delivered to all subscribers of that type
- [ ] Subscribers receive only messages they subscribed to
- [ ] Unsubscribe function removes the handler
- [ ] Message history is maintained (max 100 messages)
- [ ] Handler errors are caught and logged, don't break other handlers
- [ ] TypeScript compilation catches invalid message types

### 8.3 Tab Management

- [ ] Opening a tab that already exists activates it instead of duplicating
- [ ] Closing the active tab activates the previous tab
- [ ] Closing the last tab shows the welcome/dashboard view
- [ ] Tabs can be reordered via drag and drop
- [ ] Tab state persists across page refreshes
- [ ] Dirty indicator shows when tab has unsaved changes

### 8.4 Keyboard Shortcuts

- [ ] All documented shortcuts work correctly
- [ ] Shortcuts are disabled when input fields are focused
- [ ] Ctrl+1..9 switches to tab at that index
- [ ] Shortcuts don't conflict with browser defaults

### 8.5 State Synchronization

- [ ] Frontend state syncs with Rust backend
- [ ] State survives application restart (persisted)
- [ ] Concurrent state changes are handled safely (Mutex)
- [ ] Invalid state transitions are rejected with errors

### 8.6 Performance

- [ ] Tab switching is instantaneous (<16ms)
- [ ] Message routing adds <1ms overhead
- [ ] Sidebar toggle animation is smooth (60fps)
- [ ] No memory leaks from unsubscribed handlers

---

## 9. Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| React | 18.x | UI rendering |
| Tauri | 2.x | Desktop application framework |
| Zustand | 4.x | Lightweight state management (optional) |
| TypeScript | 5.x | Type safety |

---

## 10. Future Considerations

- **Plugin System**: Allow third-party components to register via message bus
- **Multi-window Support**: Spawn tabs as separate windows
- **Theming**: Dark/light mode support via CSS variables
- **Undo/Redo**: Track message history for global undo
