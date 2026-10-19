import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// GitHub Pages: https://<kullanıcı>.github.io/90-meclis/
export default defineConfig({
  base: process.env.VITE_BASE ?? "/90-meclis/",
  plugins: [react()],
  build: { target: "es2020", sourcemap: false, chunkSizeWarningLimit: 700 },
});
