import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    host: true, // Allow external connections
    proxy: {
      // API routes
      '/api': {
        target: 'http://localhost:8866',
        changeOrigin: true,
        secure: false,
        ws: true,
        configure: (proxy, options) => {
          proxy.on('proxyReq', (proxyReq, req, res) => {
            console.log(`[PROXY] ${req.method} ${req.url} → ${options.target}${req.url}`)
          })
        }
      },
      // Static files
      '/images': {
        target: 'http://localhost:8866',
        changeOrigin: true,
        secure: false
      },
      // Health and system endpoints
      '/health': {
        target: 'http://localhost:8866',
        changeOrigin: true,
        secure: false
      },
      // API documentation
      '/docs': {
        target: 'http://localhost:8866',
        changeOrigin: true,
        secure: false
      },
      '/redoc': {
        target: 'http://localhost:8866',
        changeOrigin: true,
        secure: false
      },
      '/openapi.json': {
        target: 'http://localhost:8866',
        changeOrigin: true,
        secure: false
      }
    },
    // Auto-open browser on start
    open: true,
    // CORS for development
    cors: true
  },
  // Build optimizations
  build: {
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          router: ['react-router-dom'],
          api: ['axios', '@tanstack/react-query']
        }
      }
    }
  },
  // Better dev experience
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-router-dom']
  }
})
