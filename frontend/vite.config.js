import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,
    // Proxy API calls to the local backend (local_backend.py).
    // This avoids CORS issues and works regardless of VITE_API_BASE_URL.
    // When VITE_API_BASE_URL is set (e.g. for a deployed build), api.js uses
    // that absolute URL instead and these proxy rules are not used.
    proxy: {
      '/api': {
        target: 'http://localhost:3001',
        changeOrigin: true,
        secure: false,
      },
      '/demo': {
        target: 'http://localhost:3002',
        changeOrigin: true,
        secure: false,
      },
      '/health': {
        target: 'http://localhost:3001',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  preview: {
    port: 4173,  // changed from 3001 to avoid conflicting with local backend
    host: true
  }
})