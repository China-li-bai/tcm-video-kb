import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      // Page route is /graph; only the JSON endpoints go to FastAPI.
      "/graph/subgraph": "http://127.0.0.1:8000",
      "/graph/paths": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
});
