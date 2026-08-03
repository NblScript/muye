/// <reference types="vitest/config" />
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

          if (
            id.includes('/react/') ||
            id.includes('/react-dom/') ||
            id.includes('/scheduler/')
          ) {
            return 'vendor-react'
          }

          if (
            id.includes('/@react-three/fiber/')
          ) {
            return 'vendor-three-fiber'
          }

          if (id.includes('/three/')) {
            return 'vendor-three'
          }

          if (
            id.includes('/styled-components/') ||
            id.includes('/gsap/') ||
            id.includes('/zustand/') ||
            id.includes('/autofit.js/') ||
            id.includes('/keli-heatmap.js/')
          ) {
            return 'vendor-screen'
          }

          return 'vendor-app'
        },
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './tests/setup.ts',
    css: true,
    exclude: ['tests/commandPoint.test.mjs', 'node_modules/**'],
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
