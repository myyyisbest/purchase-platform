import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 后端服务地址：开发模式下由 Vite proxy 把 /api 转发到后端，
// 避免 axios 跨域；同时与子路径部署模式（nginx 反代 /api）路径一致。
const BACKEND_TARGET = process.env.VITE_BACKEND_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue()],
  // 子路径部署：Vite 自带 /purchase-platform/ 前缀，Nginx 保留前缀反代，无需 sub_filter
  base: '/purchase-platform/',
  server: {
    host: '0.0.0.0',
    port: 3001,
    strictPort: true,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: BACKEND_TARGET,
        changeOrigin: true,
      },
    },
  },
})
