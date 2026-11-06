import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backend = process.env.ERP_BACKEND_URL || 'http://127.0.0.1:5050';

export default defineConfig({
  plugins: [react()],
  base: '/',
  server: {
    port: 5173,
    strictPort: true,
    // Im Dev-Modus /api an Flask weiterleiten -> gleiche Origin, kein CORS nötig.
    proxy: { '/api': { target: backend, changeOrigin: true } },
  },
  build: { outDir: 'dist', emptyOutDir: true },
  test: { environment: 'node', include: ['src/**/*.test.{js,jsx}'] },
});
