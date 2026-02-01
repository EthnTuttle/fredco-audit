# Specification 07: Integration

**Status:** Draft  
**Created:** 2026-01-31  
**Depends On:** 01-data-model, 02-wasm-core, 03-llm-interface, 04-ui-layout, 05-visualization, 06-prompt-system

---

## 1. Overview

This specification defines how all components of the FCPS Audit Explorer integrate into a single, deployable web application. The system combines Rust WebAssembly modules with TypeScript/React UI components, bundled via Vite for static deployment to GitHub Pages.

### 1.1 Design Goals

1. **Single Bundle Deployment** - All assets served from one directory
2. **Zero Backend** - Fully client-side execution
3. **Fast Initial Load** - Progressive loading of data and WASM
4. **Reproducible Builds** - Deterministic output from source

### 1.2 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub Pages                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                      /dist                                 │  │
│  │  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌─────────────┐ │  │
│  │  │index.html│  │main.js   │  │*.wasm   │  │data/*.json  │ │  │
│  │  └─────────┘  └──────────┘  └─────────┘  └─────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Build Pipeline

### 2.1 Pipeline Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           BUILD PIPELINE                                 │
└─────────────────────────────────────────────────────────────────────────┘

 Source Files                    Build Steps                    Output
 ────────────                    ───────────                    ──────

 ┌─────────────┐
 │ crates/     │
 │  core/      │───┐
 │  wasm/      │   │
 └─────────────┘   │
                   ▼
              ┌─────────────┐      ┌─────────────┐
              │  wasm-pack  │─────▶│ pkg/*.wasm  │
              │   build     │      │ pkg/*.js    │
              └─────────────┘      │ pkg/*.d.ts  │
                                   └──────┬──────┘
                                          │
 ┌─────────────┐                          │
 │ src/        │                          │
 │  components/│───┐                      │
 │  hooks/     │   │                      │
 │  utils/     │   │                      ▼
 └─────────────┘   │              ┌─────────────┐      ┌─────────────┐
                   ├─────────────▶│    Vite     │─────▶│   dist/     │
 ┌─────────────┐   │              │   bundle    │      │  index.html │
 │ index.html  │───┤              └─────────────┘      │  assets/    │
 │ styles/     │───┘                      ▲            │   main.js   │
 └─────────────┘                          │            │   *.wasm    │
                                          │            │  data/      │
 ┌─────────────┐                          │            └─────────────┘
 │ data/       │                          │
 │ processed/  │──────────────────────────┘
 └─────────────┘
```

### 2.2 Build Stages

#### Stage 1: WASM Compilation

```bash
# Executed by: npm run build:wasm
wasm-pack build crates/wasm \
  --target web \
  --out-dir ../../src/wasm/pkg \
  --release
```

**Inputs:**
- `crates/core/src/**/*.rs` - Core Rust library
- `crates/wasm/src/**/*.rs` - WASM bindings

**Outputs:**
- `src/wasm/pkg/fcps_wasm.js` - JavaScript glue code
- `src/wasm/pkg/fcps_wasm_bg.wasm` - WebAssembly binary
- `src/wasm/pkg/fcps_wasm.d.ts` - TypeScript definitions

#### Stage 2: TypeScript Bundling

```bash
# Executed by: npm run build:ts
vite build
```

**Inputs:**
- `src/**/*.ts` - TypeScript source
- `src/**/*.tsx` - React components
- `src/wasm/pkg/*` - WASM artifacts from Stage 1
- `index.html` - Entry point

**Outputs:**
- `dist/index.html` - Processed HTML
- `dist/assets/main-[hash].js` - Bundled JavaScript
- `dist/assets/main-[hash].css` - Bundled CSS
- `dist/assets/fcps_wasm_bg-[hash].wasm` - Copied WASM

#### Stage 3: Data Preparation

```bash
# Executed by: npm run build:data
node scripts/prepare-data.js
```

**Inputs:**
- `data/processed/**/*.json` - Processed audit data

**Outputs:**
- `dist/data/audit-bundle.json` - Combined data bundle
- `dist/data/manifest.json` - Data file manifest

---

## 3. Project Structure

### 3.1 Directory Layout

```
fredco-audit/
├── crates/
│   ├── core/                    # Pure Rust library
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── data/            # Data structures
│   │       ├── query/           # Query engine
│   │       ├── metrics/         # Metric calculations
│   │       └── format/          # Output formatting
│   │
│   └── wasm/                    # WASM bindings
│       ├── Cargo.toml
│       └── src/
│           ├── lib.rs           # wasm-bindgen exports
│           └── bridge.rs        # JS interop helpers
│
├── src/
│   ├── wasm/
│   │   └── pkg/                 # wasm-pack output (gitignored)
│   │
│   ├── components/
│   │   ├── App.tsx
│   │   ├── QueryPanel/
│   │   ├── ResultsPanel/
│   │   ├── VisualizationPanel/
│   │   └── SourcePanel/
│   │
│   ├── hooks/
│   │   ├── useWasm.ts           # WASM initialization
│   │   ├── useQuery.ts          # Query state management
│   │   └── useLLM.ts            # LLM integration
│   │
│   ├── services/
│   │   ├── wasmBridge.ts        # WASM interface
│   │   ├── llmClient.ts         # LLM API client
│   │   └── dataLoader.ts        # Data fetching
│   │
│   ├── types/
│   │   └── index.ts             # TypeScript types
│   │
│   ├── styles/
│   │   └── main.css             # Global styles
│   │
│   └── main.tsx                 # Application entry
│
├── data/
│   └── processed/               # Audit data (JSON)
│
├── scripts/
│   └── prepare-data.js          # Data bundling script
│
├── index.html                   # HTML entry point
├── vite.config.ts               # Vite configuration
├── Cargo.toml                   # Workspace root
├── package.json                 # NPM configuration
└── tsconfig.json                # TypeScript config
```

### 3.2 Cargo Workspace Configuration

```toml
# Cargo.toml (workspace root)
[workspace]
resolver = "2"
members = [
    "crates/core",
    "crates/wasm",
]

[workspace.package]
version = "0.1.0"
edition = "2021"
authors = ["FCPS Audit Project"]
license = "MIT"

[workspace.dependencies]
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
thiserror = "1.0"
```

```toml
# crates/core/Cargo.toml
[package]
name = "fcps-core"
version.workspace = true
edition.workspace = true

[dependencies]
serde.workspace = true
serde_json.workspace = true
thiserror.workspace = true

[features]
default = []
wasm = []  # Feature flag for WASM-specific code
```

```toml
# crates/wasm/Cargo.toml
[package]
name = "fcps-wasm"
version.workspace = true
edition.workspace = true

[lib]
crate-type = ["cdylib", "rlib"]

[dependencies]
fcps-core = { path = "../core", features = ["wasm"] }
wasm-bindgen = "0.2"
serde-wasm-bindgen = "0.6"
console_error_panic_hook = "0.1"
js-sys = "0.3"
web-sys = { version = "0.3", features = ["console"] }

[dependencies.serde]
workspace = true

[dependencies.serde_json]
workspace = true

[profile.release]
opt-level = "s"      # Optimize for size
lto = true           # Link-time optimization
codegen-units = 1    # Better optimization
```

### 3.3 Package.json Scripts

```json
{
  "name": "fcps-audit-explorer",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "npm run build:wasm && vite",
    "dev:watch": "concurrently \"npm run watch:wasm\" \"vite\"",
    
    "build": "npm run build:wasm && npm run build:ts && npm run build:data",
    "build:wasm": "wasm-pack build crates/wasm --target web --out-dir ../../src/wasm/pkg",
    "build:wasm:dev": "wasm-pack build crates/wasm --target web --out-dir ../../src/wasm/pkg --dev",
    "build:ts": "tsc && vite build",
    "build:data": "node scripts/prepare-data.js",
    
    "watch:wasm": "cargo watch -w crates -s 'npm run build:wasm:dev'",
    
    "test": "npm run test:rust && npm run test:ts",
    "test:rust": "cargo test --workspace",
    "test:ts": "vitest run",
    "test:e2e": "playwright test",
    
    "lint": "npm run lint:rust && npm run lint:ts",
    "lint:rust": "cargo clippy --workspace -- -D warnings",
    "lint:ts": "eslint src --ext .ts,.tsx",
    
    "typecheck": "tsc --noEmit",
    
    "preview": "vite preview",
    "deploy": "npm run build && gh-pages -d dist"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@playwright/test": "^1.40.0",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "concurrently": "^8.2.0",
    "eslint": "^8.55.0",
    "gh-pages": "^6.1.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "vite-plugin-wasm": "^3.3.0",
    "vitest": "^1.0.0"
  }
}
```

### 3.4 Vite Configuration

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import wasm from 'vite-plugin-wasm';
import { resolve } from 'path';

export default defineConfig({
  plugins: [
    react(),
    wasm(),
  ],
  
  // GitHub Pages deployment base path
  base: '/fcps-audit/',
  
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@wasm': resolve(__dirname, 'src/wasm/pkg'),
    },
  },
  
  build: {
    target: 'esnext',
    outDir: 'dist',
    
    rollupOptions: {
      output: {
        // Keep WASM files with recognizable names
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.endsWith('.wasm')) {
            return 'assets/[name]-[hash][extname]';
          }
          return 'assets/[name]-[hash][extname]';
        },
      },
    },
    
    // Copy data files to dist
    copyPublicDir: true,
  },
  
  // Development server configuration
  server: {
    port: 3000,
    headers: {
      // Required for SharedArrayBuffer (if used)
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
    },
  },
  
  // Handle WASM MIME type
  optimizeDeps: {
    exclude: ['@wasm'],
  },
  
  // Worker configuration for WASM
  worker: {
    format: 'es',
    plugins: () => [wasm()],
  },
});
```

### 3.5 TypeScript Configuration

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    
    "paths": {
      "@/*": ["./src/*"],
      "@wasm/*": ["./src/wasm/pkg/*"]
    },
    
    "types": ["vite/client"]
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

---

## 4. Component Initialization

### 4.1 Initialization Sequence Diagram

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Browser │     │  React  │     │  WASM   │     │  Data   │     │   LLM   │
│         │     │   App   │     │ Module  │     │ Loader  │     │ Client  │
└────┬────┘     └────┬────┘     └────┬────┘     └────┬────┘     └────┬────┘
     │               │               │               │               │
     │  Load HTML    │               │               │               │
     │──────────────▶│               │               │               │
     │               │               │               │               │
     │  Load JS      │               │               │               │
     │──────────────▶│               │               │               │
     │               │               │               │               │
     │               │ Initialize    │               │               │
     │               │──────────────▶│               │               │
     │               │               │               │               │
     │               │               │ Fetch WASM    │               │
     │               │               │──────────────▶│               │
     │               │               │◀──────────────│               │
     │               │               │               │               │
     │               │               │ Compile &     │               │
     │               │               │ Instantiate   │               │
     │               │               │───────┐       │               │
     │               │               │       │       │               │
     │               │               │◀──────┘       │               │
     │               │               │               │               │
     │               │ WASM Ready    │               │               │
     │               │◀──────────────│               │               │
     │               │               │               │               │
     │               │ Load Data     │               │               │
     │               │──────────────────────────────▶│               │
     │               │               │               │               │
     │               │               │               │ Fetch JSON    │
     │               │               │               │───────┐       │
     │               │               │               │       │       │
     │               │               │               │◀──────┘       │
     │               │               │               │               │
     │               │ Data Ready    │               │               │
     │               │◀──────────────────────────────│               │
     │               │               │               │               │
     │               │ Initialize    │               │               │
     │               │ WASM Store    │               │               │
     │               │──────────────▶│               │               │
     │               │               │ Parse &       │               │
     │               │               │ Validate      │               │
     │               │               │───────┐       │               │
     │               │               │       │       │               │
     │               │               │◀──────┘       │               │
     │               │               │               │               │
     │               │ Store Ready   │               │               │
     │               │◀──────────────│               │               │
     │               │               │               │               │
     │  Render UI    │               │               │               │
     │◀──────────────│               │               │               │
     │               │               │               │               │
     │               │ Check API Key │               │               │
     │               │──────────────────────────────────────────────▶│
     │               │               │               │               │
     │               │ LLM Status    │               │               │
     │               │◀──────────────────────────────────────────────│
     │               │               │               │               │
     ▼               ▼               ▼               ▼               ▼
                        APPLICATION READY
```

### 4.2 Initialization Code

```typescript
// src/main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './components/App';
import { WasmProvider } from './contexts/WasmContext';
import { DataProvider } from './contexts/DataContext';
import { LLMProvider } from './contexts/LLMContext';
import './styles/main.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <WasmProvider>
      <DataProvider>
        <LLMProvider>
          <App />
        </LLMProvider>
      </DataProvider>
    </WasmProvider>
  </React.StrictMode>
);
```

```typescript
// src/contexts/WasmContext.tsx
import React, { createContext, useContext, useEffect, useState } from 'react';
import type { InitOutput } from '@wasm/fcps_wasm';

interface WasmState {
  status: 'loading' | 'ready' | 'error';
  module: InitOutput | null;
  error: Error | null;
}

const WasmContext = createContext<WasmState | null>(null);

export function WasmProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<WasmState>({
    status: 'loading',
    module: null,
    error: null,
  });

  useEffect(() => {
    async function initWasm() {
      try {
        // Dynamic import triggers Vite's WASM handling
        const wasm = await import('@wasm/fcps_wasm');
        
        // Initialize the WASM module
        await wasm.default();
        
        // Set up panic hook for better error messages
        wasm.init_panic_hook();
        
        setState({
          status: 'ready',
          module: wasm,
          error: null,
        });
      } catch (error) {
        console.error('WASM initialization failed:', error);
        setState({
          status: 'error',
          module: null,
          error: error instanceof Error ? error : new Error(String(error)),
        });
      }
    }

    initWasm();
  }, []);

  return (
    <WasmContext.Provider value={state}>
      {children}
    </WasmContext.Provider>
  );
}

export function useWasm() {
  const context = useContext(WasmContext);
  if (!context) {
    throw new Error('useWasm must be used within WasmProvider');
  }
  return context;
}
```

```typescript
// src/contexts/DataContext.tsx
import React, { createContext, useContext, useEffect, useState } from 'react';
import { useWasm } from './WasmContext';

interface DataState {
  status: 'waiting' | 'loading' | 'ready' | 'error';
  storeId: number | null;
  error: Error | null;
}

const DataContext = createContext<DataState | null>(null);

export function DataProvider({ children }: { children: React.ReactNode }) {
  const { status: wasmStatus, module } = useWasm();
  const [state, setState] = useState<DataState>({
    status: 'waiting',
    storeId: null,
    error: null,
  });

  useEffect(() => {
    if (wasmStatus !== 'ready' || !module) {
      return;
    }

    async function loadData() {
      setState(prev => ({ ...prev, status: 'loading' }));

      try {
        // Fetch the data bundle
        const response = await fetch('./data/audit-bundle.json');
        if (!response.ok) {
          throw new Error(`Failed to fetch data: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Initialize the WASM data store
        const storeId = module.create_data_store(JSON.stringify(data));
        
        setState({
          status: 'ready',
          storeId,
          error: null,
        });
      } catch (error) {
        console.error('Data loading failed:', error);
        setState({
          status: 'error',
          storeId: null,
          error: error instanceof Error ? error : new Error(String(error)),
        });
      }
    }

    loadData();
  }, [wasmStatus, module]);

  return (
    <DataContext.Provider value={state}>
      {children}
    </DataContext.Provider>
  );
}

export function useData() {
  const context = useContext(DataContext);
  if (!context) {
    throw new Error('useData must be used within DataProvider');
  }
  return context;
}
```

### 4.3 Loading States

```typescript
// src/components/App.tsx
import React from 'react';
import { useWasm } from '@/contexts/WasmContext';
import { useData } from '@/contexts/DataContext';
import { useLLM } from '@/contexts/LLMContext';
import LoadingScreen from './LoadingScreen';
import ErrorScreen from './ErrorScreen';
import MainLayout from './MainLayout';

export default function App() {
  const wasm = useWasm();
  const data = useData();
  const llm = useLLM();

  // WASM loading/error
  if (wasm.status === 'loading') {
    return <LoadingScreen stage="wasm" message="Loading WebAssembly module..." />;
  }
  
  if (wasm.status === 'error') {
    return <ErrorScreen error={wasm.error!} stage="wasm" />;
  }

  // Data loading/error
  if (data.status === 'loading' || data.status === 'waiting') {
    return <LoadingScreen stage="data" message="Loading audit data..." />;
  }
  
  if (data.status === 'error') {
    return <ErrorScreen error={data.error!} stage="data" />;
  }

  // LLM status is non-blocking (can work without LLM)
  return (
    <MainLayout 
      llmAvailable={llm.status === 'ready'}
      llmError={llm.error}
    />
  );
}
```

---

## 5. Message Flow Examples

### 5.1 Simple Query Flow

```
User Query: "What is Frederick County's per-pupil spending?"

┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│   UI    │     │ LLM API │     │  WASM   │     │  Store  │
└────┬────┘     └────┬────┘     └────┬────┘     └────┬────┘
     │               │               │               │
     │ Submit Query  │               │               │
     │──────────────▶│               │               │
     │               │               │               │
     │               │ Parse NL to   │               │
     │               │ Structured    │               │
     │               │ Query         │               │
     │               │───────┐       │               │
     │               │       │       │               │
     │               │◀──────┘       │               │
     │               │               │               │
     │ Query Plan    │               │               │
     │◀──────────────│               │               │
     │               │               │               │
     │ Execute Query │               │               │
     │──────────────────────────────▶│               │
     │               │               │               │
     │               │               │ fetch_metric  │
     │               │               │──────────────▶│
     │               │               │               │
     │               │               │ Data          │
     │               │               │◀──────────────│
     │               │               │               │
     │               │               │ Calculate &   │
     │               │               │ Format        │
     │               │               │───────┐       │
     │               │               │       │       │
     │               │               │◀──────┘       │
     │               │               │               │
     │ Results JSON  │               │               │
     │◀──────────────────────────────│               │
     │               │               │               │
     │ Format for    │               │               │
     │ Display       │               │               │
     │──────────────▶│               │               │
     │               │               │               │
     │ Narrative     │               │               │
     │◀──────────────│               │               │
     │               │               │               │
     │ Render Results│               │               │
     │───────┐       │               │               │
     │       │       │               │               │
     │◀──────┘       │               │               │
     ▼               ▼               ▼               ▼
```

### 5.2 Comparative Analysis Flow

```
User Query: "Compare Frederick to peer districts on admin spending"

Step 1: Parse Query
────────────────────
LLM Input:
{
  "type": "parse",
  "query": "Compare Frederick to peer districts on admin spending",
  "context": { "divisions": ["069", "043", "061", "171", "187"] }
}

LLM Output:
{
  "query_type": "comparison",
  "metric": "admin_spending",
  "divisions": ["069", "043", "061", "171", "187"],
  "years": ["2023-24"],
  "aggregation": "per_pupil"
}

Step 2: Execute WASM Queries
────────────────────────────
// TypeScript calls
const results = wasm.execute_comparison_query({
  metric: "admin_expenditures",
  divisions: ["069", "043", "061", "171", "187"],
  fiscal_year: "2023-24",
  normalize: "per_pupil"
});

// WASM returns
{
  "query_id": "cmp_001",
  "results": [
    {
      "division_code": "069",
      "division_name": "Frederick County",
      "value": 1523.45,
      "rank": 3,
      "sources": [...]
    },
    // ... other divisions
  ],
  "statistics": {
    "mean": 1456.78,
    "median": 1489.00,
    "std_dev": 234.56
  }
}

Step 3: Generate Narrative
──────────────────────────
LLM Input:
{
  "type": "narrate",
  "results": { /* query results */ },
  "style": "audit_finding"
}

LLM Output:
"Frederick County's administrative spending of $1,523 per pupil 
ranks 3rd among peer districts, 4.5% above the peer average of 
$1,457. This represents an increase of 8.2% from FY2020 levels..."

Step 4: Render UI
─────────────────
- Display narrative in ResultsPanel
- Generate bar chart in VisualizationPanel
- Show source citations in SourcePanel
```

### 5.3 Time Series Analysis Flow

```typescript
// User: "Show spending trends for Frederick County 2020-2024"

// Step 1: Query parsed to structured request
const query = {
  type: 'time_series',
  division: '069',
  metrics: ['total_expenditures', 'enrollment'],
  years: ['2019-20', '2020-21', '2021-22', '2022-23', '2023-24'],
  derived: ['per_pupil_spending', 'yoy_change']
};

// Step 2: WASM executes
const response = wasm.execute_time_series(JSON.stringify(query));
const results = JSON.parse(response);

// Step 3: Results structure
{
  "query_id": "ts_002",
  "series": [
    {
      "year": "2019-20",
      "total_expenditures": 198234567,
      "enrollment": 13456,
      "per_pupil": 14733,
      "yoy_change": null
    },
    {
      "year": "2020-21",
      "total_expenditures": 205678901,
      "enrollment": 13589,
      "per_pupil": 15137,
      "yoy_change": 2.74
    },
    // ... more years
  ],
  "trend": {
    "cagr": 3.2,
    "direction": "increasing",
    "acceleration": 0.5
  },
  "sources": [
    { "file": "table15_2019-20.xlsm", "row": 42 },
    // ... per data point
  ]
}

// Step 4: Visualization renders line chart
// Step 5: LLM generates trend analysis narrative
```

---

## 6. Deployment

### 6.1 GitHub Pages Deployment

```yaml
# .github/workflows/deploy.yml
name: Deploy to GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Rust
        uses: dtolnay/rust-action@stable
        with:
          targets: wasm32-unknown-unknown

      - name: Install wasm-pack
        run: curl https://rustwasm.github.io/wasm-pack/installer/init.sh -sSf | sh

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Build WASM
        run: npm run build:wasm

      - name: Build TypeScript
        run: npm run build:ts

      - name: Prepare data
        run: npm run build:data

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: dist

  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build
    
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

### 6.2 Build Output Structure

```
dist/
├── index.html                           # Entry point
├── assets/
│   ├── main-[hash].js                   # Bundled application (~150KB gzip)
│   ├── main-[hash].css                  # Styles (~10KB gzip)
│   ├── fcps_wasm_bg-[hash].wasm         # WASM binary (~80KB)
│   └── vendor-[hash].js                 # React + deps (~45KB gzip)
├── data/
│   ├── audit-bundle.json                # Combined data (~120KB gzip)
│   └── manifest.json                    # Data manifest
└── favicon.ico
```

### 6.3 Deployment Checklist

```markdown
## Pre-Deployment Checklist

- [ ] All tests pass (`npm test`)
- [ ] TypeScript compiles without errors (`npm run typecheck`)
- [ ] Rust compiles without warnings (`npm run lint:rust`)
- [ ] Build completes successfully (`npm run build`)
- [ ] Local preview works (`npm run preview`)
- [ ] WASM loads correctly in preview
- [ ] Data loads correctly in preview
- [ ] All visualizations render
- [ ] LLM integration works (with API key)
- [ ] Source citations are accurate
- [ ] No console errors in browser

## Post-Deployment Verification

- [ ] Site loads at GitHub Pages URL
- [ ] WASM module initializes
- [ ] Data loads successfully
- [ ] Sample queries work
- [ ] Charts render correctly
- [ ] Mobile layout is usable
```

---

## 7. Testing Strategy

### 7.1 Test Pyramid

```
                    ┌─────────┐
                    │   E2E   │  (Few, slow, high confidence)
                   ─┴─────────┴─
                  ┌─────────────┐
                  │ Integration │  (Some, medium speed)
                 ─┴─────────────┴─
                ┌─────────────────┐
                │      Unit       │  (Many, fast, focused)
               ─┴─────────────────┴─
```

### 7.2 Rust Unit Tests

```rust
// crates/core/src/query/tests.rs
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_metric_calculation() {
        let data = TestData::sample();
        let result = calculate_per_pupil(&data, "069", "2023-24");
        
        assert!(result.is_ok());
        let value = result.unwrap();
        assert!((value - 15734.0).abs() < 0.01);
    }

    #[test]
    fn test_comparison_query() {
        let store = DataStore::from_json(SAMPLE_JSON).unwrap();
        let query = ComparisonQuery {
            metric: "admin_expenditures".into(),
            divisions: vec!["069", "043", "061"],
            fiscal_year: "2023-24".into(),
        };
        
        let results = store.execute_comparison(query).unwrap();
        assert_eq!(results.len(), 3);
        assert!(results.iter().all(|r| r.value > 0.0));
    }
}
```

### 7.3 TypeScript Unit Tests

```typescript
// src/services/__tests__/wasmBridge.test.ts
import { describe, it, expect, beforeAll } from 'vitest';
import { WasmBridge } from '../wasmBridge';

describe('WasmBridge', () => {
  let bridge: WasmBridge;

  beforeAll(async () => {
    bridge = await WasmBridge.initialize();
  });

  it('should execute metric queries', async () => {
    const result = await bridge.queryMetric({
      metric: 'per_pupil_spending',
      division: '069',
      year: '2023-24',
    });

    expect(result.value).toBeGreaterThan(0);
    expect(result.sources).toHaveLength.greaterThan(0);
  });

  it('should handle invalid division codes', async () => {
    await expect(
      bridge.queryMetric({
        metric: 'per_pupil_spending',
        division: 'INVALID',
        year: '2023-24',
      })
    ).rejects.toThrow('Unknown division');
  });
});
```

### 7.4 Integration Tests

```typescript
// src/__tests__/integration/queryFlow.test.ts
import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useQuery } from '@/hooks/useQuery';
import { TestProviders } from '../testUtils';

describe('Query Flow Integration', () => {
  it('should process natural language query end-to-end', async () => {
    const { result } = renderHook(() => useQuery(), {
      wrapper: TestProviders,
    });

    await act(async () => {
      await result.current.submitQuery(
        "What is Frederick County's per-pupil spending?"
      );
    });

    expect(result.current.status).toBe('complete');
    expect(result.current.results).toBeDefined();
    expect(result.current.results.value).toBeCloseTo(15734, 0);
  });
});
```

### 7.5 E2E Tests

```typescript
// e2e/queryExecution.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Query Execution', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Wait for initialization
    await page.waitForSelector('[data-testid="app-ready"]');
  });

  test('should execute spending query and show results', async ({ page }) => {
    // Enter query
    await page.fill(
      '[data-testid="query-input"]',
      "What is Frederick County's per-pupil spending?"
    );
    await page.click('[data-testid="submit-query"]');

    // Wait for results
    await page.waitForSelector('[data-testid="results-panel"]');

    // Verify results contain expected data
    const resultsText = await page.textContent('[data-testid="results-panel"]');
    expect(resultsText).toContain('Frederick County');
    expect(resultsText).toContain('$15,');

    // Verify source citations appear
    await expect(page.locator('[data-testid="source-citation"]')).toBeVisible();
  });

  test('should render comparison chart', async ({ page }) => {
    await page.fill(
      '[data-testid="query-input"]',
      'Compare Frederick to peer districts on spending'
    );
    await page.click('[data-testid="submit-query"]');

    // Wait for chart
    await page.waitForSelector('[data-testid="chart-container"] svg');

    // Verify chart has data
    const bars = await page.locator('[data-testid="chart-bar"]').count();
    expect(bars).toBeGreaterThanOrEqual(5); // Frederick + 4 peers minimum
  });
});
```

### 7.6 Data Validation Tests

```typescript
// scripts/validate-data.ts
import Ajv from 'ajv';
import { readFileSync } from 'fs';

const ajv = new Ajv();

// Load schemas
const schemas = {
  enrollment: JSON.parse(readFileSync('schemas/enrollment.json', 'utf-8')),
  expenditures: JSON.parse(readFileSync('schemas/expenditures.json', 'utf-8')),
};

// Validate processed data
function validateData() {
  const errors: string[] = [];

  // Validate enrollment data
  const enrollment = JSON.parse(
    readFileSync('data/processed/vdoe/table8_enrollment.json', 'utf-8')
  );
  
  if (!ajv.validate(schemas.enrollment, enrollment)) {
    errors.push(`Enrollment validation failed: ${ajv.errorsText()}`);
  }

  // Validate expenditure data
  const expenditures = JSON.parse(
    readFileSync('data/processed/vdoe/table15_expenditures.json', 'utf-8')
  );
  
  if (!ajv.validate(schemas.expenditures, expenditures)) {
    errors.push(`Expenditures validation failed: ${ajv.errorsText()}`);
  }

  // Cross-validate: enrollment should match expenditure ADM
  // ... additional validation logic

  if (errors.length > 0) {
    console.error('Data validation failed:');
    errors.forEach(e => console.error(`  - ${e}`));
    process.exit(1);
  }

  console.log('All data validation passed');
}

validateData();
```

---

## 8. Acceptance Criteria

### 8.1 Build System

| Criterion | Requirement | Verification |
|-----------|-------------|--------------|
| WASM builds | `npm run build:wasm` succeeds | CI pipeline |
| TypeScript builds | `npm run build:ts` succeeds with no errors | CI pipeline |
| Full build | `npm run build` produces dist/ | CI pipeline |
| Build time | Full build < 3 minutes | CI metrics |
| Bundle size | main.js < 200KB gzipped | Bundle analysis |
| WASM size | .wasm < 100KB | Bundle analysis |

### 8.2 Initialization

| Criterion | Requirement | Verification |
|-----------|-------------|--------------|
| WASM loads | Module initializes without error | E2E test |
| Data loads | Audit data parsed successfully | E2E test |
| Load time | App interactive < 3s on 4G | Lighthouse |
| Error handling | Graceful errors for load failures | E2E test |
| Progress feedback | Loading states shown to user | Manual test |

### 8.3 Query Execution

| Criterion | Requirement | Verification |
|-----------|-------------|--------------|
| Simple queries | Return results < 500ms | Performance test |
| Complex queries | Return results < 2s | Performance test |
| Data accuracy | Results match source data | Validation test |
| Source tracking | All results cite sources | Integration test |
| Error handling | Invalid queries show helpful errors | E2E test |

### 8.4 Deployment

| Criterion | Requirement | Verification |
|-----------|-------------|--------------|
| GitHub Pages | Site deploys successfully | CD pipeline |
| HTTPS | Site served over HTTPS | Manual check |
| No 404s | All assets load correctly | E2E test |
| Cross-browser | Works in Chrome, Firefox, Safari | E2E matrix |
| Mobile | Usable on mobile devices | Manual test |

### 8.5 Integration Points

| Criterion | Requirement | Verification |
|-----------|-------------|--------------|
| WASM ↔ TS | Data passes correctly | Integration test |
| TS ↔ LLM | API calls succeed | Integration test |
| UI ↔ State | Components update on state change | Unit test |
| Data ↔ Charts | Visualizations reflect data | E2E test |

---

## 9. Error Handling

### 9.1 Error Categories

```typescript
// src/types/errors.ts
export enum ErrorCategory {
  WASM_INIT = 'WASM_INIT',
  DATA_LOAD = 'DATA_LOAD',
  QUERY_PARSE = 'QUERY_PARSE',
  QUERY_EXECUTE = 'QUERY_EXECUTE',
  LLM_API = 'LLM_API',
  RENDER = 'RENDER',
}

export interface AppError {
  category: ErrorCategory;
  code: string;
  message: string;
  details?: unknown;
  recoverable: boolean;
  userMessage: string;
}
```

### 9.2 Recovery Strategies

| Error Type | Strategy | User Feedback |
|------------|----------|---------------|
| WASM init failure | Show fallback, suggest refresh | "Unable to load computation engine" |
| Data load failure | Retry 3x, then error screen | "Unable to load audit data" |
| Query parse failure | Show suggestions | "Could not understand query" |
| Query execute failure | Show partial results if available | "Query partially completed" |
| LLM API failure | Fallback to structured results | "AI summary unavailable" |
| Render failure | Error boundary, isolate component | "Unable to display [component]" |

---

## 10. Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| First Contentful Paint | < 1.5s | Lighthouse |
| Time to Interactive | < 3.0s | Lighthouse |
| WASM initialization | < 500ms | Performance API |
| Data load | < 1.0s | Performance API |
| Simple query response | < 500ms | Performance API |
| Chart render | < 200ms | Performance API |
| Memory usage | < 100MB | DevTools |

---

## Appendix A: Environment Variables

```bash
# .env.example (for local development)

# LLM API Configuration
VITE_LLM_PROVIDER=anthropic
VITE_LLM_MODEL=claude-sonnet-4-20250514

# Feature Flags
VITE_ENABLE_DEBUG=false
VITE_ENABLE_MOCK_LLM=false

# Build Configuration
VITE_BASE_PATH=/fcps-audit/
```

---

## Appendix B: Browser Support

| Browser | Minimum Version | Notes |
|---------|-----------------|-------|
| Chrome | 89+ | Full support |
| Firefox | 89+ | Full support |
| Safari | 15+ | Full support |
| Edge | 89+ | Full support |
| Mobile Chrome | 89+ | Full support |
| Mobile Safari | 15+ | Full support |

**Required Features:**
- WebAssembly
- ES2022 (async/await, optional chaining)
- CSS Grid/Flexbox
- Fetch API
- Web Crypto API (for LLM key storage)
