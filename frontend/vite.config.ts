import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      // gl-bench's "browser" field points to a non-ESM UMD bundle with no
      // `export default`, which breaks cosmos.gl v3's static import of it
      // (used by the optional showFPSMonitor feature we don't enable).
      // Force resolution to its real ESM build instead.
      'gl-bench': 'gl-bench/dist/gl-bench.module.js',
    },
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  preview: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
