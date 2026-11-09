import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api to Django, so the browser only ever talks to
// one origin. That sidesteps CORS entirely during development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    // Vite >=5.4.12 rejects unknown Host headers. Local development needs
    // nothing here; set VITE_ALLOWED_HOSTS=all only when serving through a
    // tunnel or a hosted preview domain.
    allowedHosts: process.env.VITE_ALLOWED_HOSTS === "all" ? true : undefined,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
