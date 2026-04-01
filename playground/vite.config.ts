import { defineConfig } from 'vite';
import wasm from 'vite-plugin-wasm';
import topLevelAwait from 'vite-plugin-top-level-await';
import monacoEditorPlugin from 'vite-plugin-monaco-editor';
import { resolve } from 'path';

// The plugin exports default as an object with .default property in some versions
const monacoEditor = (monacoEditorPlugin as any).default || monacoEditorPlugin;

export default defineConfig({
  plugins: [
    wasm(),
    topLevelAwait(),
    monacoEditor({
      // Languages to include
      languageWorkers: ['editorWorkerService', 'json', 'typescript'],
      // Custom languages (SQL is included via customWorkers or as a feature)
      customWorkers: [],
    }),
  ],
  
  // Deployment base path for audit.virginiafreedom.tech/playground/
  base: '/playground/',
  
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@wasm': resolve(__dirname, 'src/wasm'),
    },
  },
  
  build: {
    target: 'esnext',
    outDir: 'dist',
    
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        transcripts: resolve(__dirname, 'transcripts.html'),
      },
      output: {
        // Keep WASM files with recognizable names
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.endsWith('.wasm')) {
            return 'assets/[name]-[hash][extname]';
          }
          return 'assets/[name]-[hash][extname]';
        },
        // Monaco workers are handled by vite-plugin-monaco-editor
      },
    },
  },
  
  // Development server configuration
  server: {
    port: 3001,
    headers: {
      // Required for SharedArrayBuffer (DuckDB may need this)
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
    },
  },
  
  // Handle WASM MIME type and Monaco editor
  optimizeDeps: {
    exclude: ['@duckdb/duckdb-wasm'],
    include: ['monaco-editor'],
  },
  
  // Worker configuration for WASM
  worker: {
    format: 'es',
    plugins: () => [wasm(), topLevelAwait()],
  },
});
