import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5176,
    proxy: {
      "/api": {
        target: "http://localhost:8000", // uvicorn app.main:app
        changeOrigin: true,
      },
    },
  },
});
