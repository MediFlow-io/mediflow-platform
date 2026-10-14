import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// The dashboard calls /api/... on its own origin. In development Vite forwards auth calls to the
// Go gateway and everything else to Django, so no CORS setup is needed.
const GATEWAY = process.env.MEDIFLOW_GATEWAY ?? 'http://localhost:8080'
const API = process.env.MEDIFLOW_API ?? 'http://localhost:8000'
const FLOW = process.env.MEDIFLOW_FLOW ?? 'http://localhost:8090' // Go patient-flow service

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5174,
    proxy: {
      '/api/auth': { target: GATEWAY, changeOrigin: true },
      '/api/visits': { target: FLOW, changeOrigin: true },
      '/api/queue': { target: FLOW, changeOrigin: true },
      '/api/dashboard': { target: FLOW, changeOrigin: true },
      '/api/reports': { target: FLOW, changeOrigin: true },
      '/api': { target: API, changeOrigin: true },
    },
  },
})
