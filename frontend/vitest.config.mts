import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}", "features/**/*.test.{ts,tsx}", "lib/**/*.test.ts"],
  },
  resolve: { alias: { "@": path.resolve(import.meta.dirname, ".") } },
});
