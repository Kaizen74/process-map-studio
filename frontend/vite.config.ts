import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Owner mode: the built app in dist/ is served by the backend on 127.0.0.1:8000.
// Developer mode (scripts/dev.py): this dev server on 127.0.0.1:5173 proxies /api to the backend.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
