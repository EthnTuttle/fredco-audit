import { defineConfig } from 'vite';
import wasm from 'vite-plugin-wasm';
import topLevelAwait from 'vite-plugin-top-level-await';
import { resolve } from 'path';

export default defineConfig({
  plugins: [
    wasm(),
    topLevelAwait(),
  ],
  
  // GitHub Pages deployment base path
  base: '/fredco-audit/playground/',
  
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
  
  // Handle WASM MIME type
  optimizeDeps: {
    exclude: ['@duckdb/duckdb-wasm'],
  },
  
  // Worker configuration for WASM
  worker: {
    format: 'es',
    plugins: () => [wasm(), topLevelAwait()],
  },
});
