import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // The API (api_v2.py) only allows the origins http://localhost:5173 and http://127.0.0.1:5173. If 5173 is busy, stop with an
  // error instead of silently moving to another port (that would fail with a CORS error).
  server: { port: 5173, strictPort: true },
})
