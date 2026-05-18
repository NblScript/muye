import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const apiTarget = process.env.MUYE_API_TARGET || 'http://127.0.0.1:18000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return undefined
          }

          if (id.includes('/react/') || id.includes('/react-dom/')) {
            return 'vendor-react'
          }

          if (
            id.includes('/leaflet/') ||
            id.includes('/react-leaflet/')
          ) {
            return 'vendor-map'
          }

          return 'vendor-misc'
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
