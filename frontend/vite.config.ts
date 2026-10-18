/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// Para onde o proxy de /api aponta. No Docker Compose é o serviço `api`; rodando
// o Vite direto no host, a API publicada em localhost:8000.
const alvoDaApi = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: true,
    port: 5173,
    // Front e API na MESMA origem (padrão do ArkoHub): o navegador fala só com o
    // Vite, que repassa /api. Sem CORS para configurar, e em produção basta um
    // reverse proxy fazer o mesmo papel.
    proxy: {
      '/api': { target: alvoDaApi, changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.spec.ts'],
  },
})
