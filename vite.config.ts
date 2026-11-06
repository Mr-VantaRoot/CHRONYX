import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
// The API only trusts its own origin, so the dev proxy presents it instead of the Vite page's origin.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {'/api': {target: 'http://127.0.0.1:8765', changeOrigin: true, headers: {Origin: 'http://127.0.0.1:8765'}}},
  },
});
