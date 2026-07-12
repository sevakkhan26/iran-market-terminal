import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// All dependencies are bundled locally at build time — no runtime CDN,
// so the built app works even when foreign CDNs are unreachable.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:4000',
      '/ws': { target: 'ws://127.0.0.1:4000', ws: true },
    },
  },
  build: { chunkSizeWarningLimit: 1200 },
});
