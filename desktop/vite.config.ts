import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Port 1420 is Tauri's convention and is repeated in tauri.conf.json and in the
// server's development CORS list. `strictPort` matters: a dev server that
// silently moves to 1421 would be a window loading nothing, with no error.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: { port: 1420, strictPort: true },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
});
