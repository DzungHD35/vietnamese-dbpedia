import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: Vite (5173) chuyển các đường dẫn dữ liệu sang API FastAPI (8000).
const api = process.env.API_URL ?? "http://127.0.0.1:8000";
const proxy = Object.fromEntries(
  ["/api", "/sparql", "/resource", "/data", "/ontology", "/page"].map((p) => [
    p,
    {
      target: api,
      // trình duyệt mở /sparql?query=… (Accept: text/html) thì cho trang SPARQL của UI; curl mới tới endpoint
      bypass: (req: { url?: string; headers: { accept?: string } }) => {
        if (!req.headers.accept?.includes("text/html")) return undefined;
        if (p === "/sparql") return "/index.html";
        // /ontology (không có thuật ngữ) là trang Ontology của UI; /ontology/{term} vẫn là Linked Data của API
        if (p === "/ontology" && /^\/ontology(?:[?#]|$)/.test(req.url ?? "")) return "/index.html";
        return undefined;
      },
    },
  ]),
);

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy },
  // Cytoscape tự nó đã ~560 kB; chunk này chỉ tải khi mở trang có đồ thị
  build: { chunkSizeWarningLimit: 600 },
});
