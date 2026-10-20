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
    // No Docker Desktop do Windows, o container não recebe aviso de arquivo alterado
    // no código montado do host: sem polling, o Vite serve a versão antiga até
    // reiniciar. O compose liga; rodando no host não precisa.
    watch: process.env.VITE_POLLING === '1' ? { usePolling: true, interval: 300 } : undefined,
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
