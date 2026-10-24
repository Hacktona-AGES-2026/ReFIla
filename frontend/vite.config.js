import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = {
  "/api": {
    target: process.env.API_URL ?? "http://localhost:8000",
    rewrite: (path) => path.replace(/^\/api/, ""),
  },
};

export default defineConfig({ plugins: [react()], server: { proxy: api }, preview: { proxy: api }, test: { environment: "jsdom" } });
