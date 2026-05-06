import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api/p1': { target: 'http://localhost:8000', rewrite: path => path.replace(/^\/api\/p1/, '') },
      '/api/p2': { target: 'http://localhost:8001', rewrite: path => path.replace(/^\/api\/p2/, '') },
      '/api/p3': { target: 'http://localhost:8002', rewrite: path => path.replace(/^\/api\/p3/, '') },
    }
  }
})
