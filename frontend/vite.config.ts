import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 2026,
    strictPort: true,
    proxy: {
      // Voice-assistant bridge (ai-assisstent/evbridge.py, WSL side).
      // Same-origin for the browser, so Windows/mirrored networking just works.
      '/bridge': {
        target: 'http://localhost:2027',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/bridge/, ''),
      },
    },
  },
  build: {
    target: 'es2022',
  },
})
