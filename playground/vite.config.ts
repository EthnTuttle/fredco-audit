import { defineConfig } from 'vite';
import wasm from 'vite-plugin-wasm';
import topLevelAwait from 'vite-plugin-top-level-await';
import { resolve } from 'path';

export default defineConfig({
  plugins: [
    wasm(),
    topLevelAwait(),
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
      output: {
        // Keep WASM files with recognizable names
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.endsWith('.wasm')) {
            return 'assets/[name]-[hash][extname]';
          }
          return 'assets/[name]-[hash][extname]';
        },
        // Manual chunks for Monaco editor workers
        manualChunks: {
          'monaco-editor': ['monaco-editor'],
        },
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
