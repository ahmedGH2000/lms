import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
export default defineConfig({
  plugins: [vue()],
  base: "/assets/nightjar_learning/ui/",
  build: {
    manifest: true,
    outDir: "../nightjar_learning/public/ui",
    emptyOutDir: true,
    rollupOptions: {
      output: { entryFileNames: "app-[hash].js", assetFileNames: "[name][extname]" },
    },
  },
});
