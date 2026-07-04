import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  root: '.',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/videos': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/music': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/output': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
});
