import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    // DEV-ONLY: The Vite dev server proxy uses unencrypted HTTP (not HTTPS).
    // This is acceptable for local development only. In production, Caddy
    // terminates TLS and forwards traffic to the backend over the internal
    // Docker network. Never expose the Vite dev server to untrusted networks.
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        ws: true,
      },
      "/health": {
        target: "http://localhost:8000",
      },
    },
  },
});
