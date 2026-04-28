import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws/live': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
        configure: (proxy) => {
          // Suppress all proxy error noise from stale WS reconnect attempts.
          // The React useWebSocket hook handles reconnection gracefully.
          proxy.on('error', (err, req, res) => {
            if (res && typeof res.writeHead === 'function') {
              res.writeHead(502);
              res.end();
            }
          });
          proxy.on('proxyReqWs', (proxyReq, req, socket) => {
            socket.on('error', () => {});
          });
        },
      },
    },
  },
})
