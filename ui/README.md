# ui/ — UI demo độc lập

API JSON mỏng (`ui/api`, FastAPI) + frontend Vite/React/TypeScript (`ui/web`). Không sửa `vidbpedia/`, `data/`,
`ontology/`; logic của team chỉ được import và gọi, riêng hàm private nằm trong `ui/api/adapters.py`.
Kế hoạch và quyết định: `.agents/CORE.md`, `.agents/PLAN.md`.

## Chạy

Dev (hai terminal):
```bash
.venv/bin/python -m ui.api --port 8000          # API, nạp graph vài giây
cd ui/web && npm install && npm run dev         # http://localhost:5173, proxy sang :8000
```

Demo (một process):
```bash
cd ui/web && npm install && npm run build
.venv/bin/python -m ui.api                      # http://127.0.0.1:8000 phục vụ cả frontend
```

Server Gradio của team (`python -m vidbpedia serve`, :7860) vẫn chạy độc lập.

## Kiểm tra
```bash
.venv/bin/python -m pytest ui/tests             # dùng dataset thật, không gọi LLM
.venv/bin/ruff check ui && .venv/bin/ruff format --check ui
cd ui/web && npm run build                      # kiểm kiểu TypeScript + build
```

## API hiện có
`/api/health`, `/api/overview`, `/api/search`, `/api/entity/{id}`, `/api/neighbors/{id}`, `/api/subgraph`;
Linked Data của team (`/resource/…`, `/data/…`, `/ontology/…`) gắn nguyên vẹn. Tài liệu OpenAPI: `/api/docs`.

Khi graph chưa nạp xong, các đường dẫn cần graph trả 503 (`/api/health` luôn trả lời và báo tiến độ).
