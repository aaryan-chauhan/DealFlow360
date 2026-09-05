import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // host: true binds 0.0.0.0 so phones/tablets on the same Wi-Fi can load the dev
  // server. Loopback-only is the Vite default and is what makes it unreachable.
  server: { host: true, port: 5173 },
})
