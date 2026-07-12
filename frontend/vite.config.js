import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/predict': 'http://localhost:8000',
      '/history': 'http://localhost:8000',
      '/stats': 'http://localhost:8000',
      '/kelas-info': 'http://localhost:8000',
      '/uploads': 'http://localhost:8000',
    },
  },
});
