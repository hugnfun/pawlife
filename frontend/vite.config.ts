import { defineConfig } from 'vite'
import uniPlugin from '@dcloudio/vite-plugin-uni'

// @ts-ignore
export default defineConfig({
  plugins: [uniPlugin.default()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        // 全局自动注入 SCSS 变量和工具样式，所有 .vue 文件无需手动 import
        additionalData: `@use "@/styles/variables.scss" as *;`,
      },
    },
  },
})
