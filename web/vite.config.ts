import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// GitHub Pages: https://90meclis.github.io/ (kök)
export default defineConfig({
  base: process.env.VITE_BASE ?? "/",
  plugins: [react()],
  build: { target: "es2020", sourcemap: false, chunkSizeWarningLimit: 700 },
});
