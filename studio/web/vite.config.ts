import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// `vite build --mode pages` writes the static console into docs/studio/ for GitHub Pages.
// The default build goes to dist/ and is served by the Python API.
export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  base: mode === "pages" ? "./" : "/",
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  define: { __PAGES__: JSON.stringify(mode === "pages") },
  build: {
    outDir: mode === "pages" ? path.resolve(__dirname, "../../docs/studio") : "dist",
    emptyOutDir: true,
    chunkSizeWarningLimit: 1600,
    rollupOptions: {
      output: { manualChunks: { echarts: ["echarts"], react: ["react", "react-dom", "react-router-dom"] } },
    },
  },
  worker: { format: "es" },
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8765", ws: true } },
  },
  test: { environment: "node" },
}));
