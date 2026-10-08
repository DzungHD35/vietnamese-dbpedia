import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: Vite (5173) chuyển các đường dẫn dữ liệu sang API FastAPI (8000).
const api = "http://127.0.0.1:8000";
const proxy = Object.fromEntries(
  ["/api", "/sparql", "/resource", "/data", "/ontology", "/page"].map((p) => [p, { target: api }]),
);

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy },
});
