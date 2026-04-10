import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

const env = loadEnv(process.env.NODE_ENV || 'development', process.cwd(), '')
const appTitle = env.VITE_TITLE?.trim() || 'OpenAgent'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    {
      name: 'inject-app-title',
      transformIndexHtml(html) {
        return html.replace(/%APP_TITLE%/g, appTitle)
      },
    },
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    modulePreload: {
      resolveDependencies(_filename, dependencies) {
        return dependencies.filter((dependency) => !dependency.includes('vendor-monaco'))
      },
    },
    rollupOptions: {
      output: {
        onlyExplicitManualChunks: true,
        manualChunks(id) {
          if (!id.includes('node_modules')) return

          if (
            id.includes('/node_modules/vue/') ||
            id.includes('/node_modules/@vue/') ||
            id.includes('/node_modules/vue-router/') ||
            id.includes('/node_modules/pinia/')
          ) {
            return 'vendor-vue'
          }

          if (id.includes('@arco-design/web-vue')) {
            return 'vendor-arco'
          }

          if (id.includes('/node_modules/lodash/')) {
            return 'vendor-lodash'
          }

          if (id.includes('/node_modules/moment/')) {
            return 'vendor-moment'
          }

          if (id.includes('@vue-flow/')) {
            return 'vendor-vueflow'
          }

          if (id.includes('monaco-editor') || id.includes('@guolao/vue-monaco-editor')) {
            return 'vendor-monaco'
          }

          if (id.includes('echarts') || id.includes('vue-echarts')) {
            return 'vendor-echarts'
          }

          if (
            id.includes('markdown-it') ||
            id.includes('highlight.js') ||
            id.includes('github-markdown-css')
          ) {
            return 'vendor-markdown'
          }

          return 'vendor'
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      // 开发环境代理 API 请求到后端
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
