# ui/ — UI demo độc lập

API JSON mỏng (`ui/api`, FastAPI) + frontend Vite/React/TypeScript (`ui/web`). Không sửa `vidbpedia/`, `data/`,
`ontology/`; logic của team chỉ được import và gọi, riêng hàm private nằm trong `ui/api/adapters.py`.
Kế hoạch và quyết định: `.agents/CORE.md`, `.agents/PLAN.md`.

## Chạy

Cần Node ≥ 20.19 (khuyên dùng 22 LTS, xem `ui/web/.nvmrc`); trên Windows nếu build báo "Cannot find native binding"
thì chạy `cd ui/web && npm install --no-save @rolldown/binding-win32-x64-msvc@1.2.13` rồi build lại.

Demo (một process, nên dùng khi trình bày):
```bash
cd ui/web && npm install && npm run build
.venv/bin/python -m ui.api                      # http://127.0.0.1:8000, phục vụ cả API lẫn frontend
```
`--port` và `--host` đổi cổng/địa chỉ. Graph (~131 nghìn triple) nạp trong vài giây ở thread nền; trong lúc đó
giao diện hiện màn "Đang nạp graph…" và tự mở khi xong.

Dev (hai terminal, frontend tự reload):
```bash
.venv/bin/python -m ui.api --port 8000          # API
cd ui/web && npm run dev                        # http://localhost:5173, proxy sang :8000
API_URL=http://127.0.0.1:8010 npm run dev       # nếu API chạy ở cổng khác
```

Server Gradio của team (`python -m vidbpedia serve`, :7860) vẫn chạy độc lập.

## Các màn hình

| Route | Câu hỏi nó trả lời |
|---|---|
| `/` Tổng quan | Graph chứa gì, lớn cỡ nào, suy luận thêm được bao nhiêu? |
| `/ontology` Ontology | Cây tài nguyên như tab cùng tên của Gradio (cùng `ResourceTree`): lớp `vio:` ⊑ `dbo:`, số thực thể, nhãn suy luận, thực thể trực tiếp, ba nhóm Thể loại / Đổi hướng / Chỉ có nhãn, ô lọc theo tên; bên dưới là mục thu gọn "Thuộc tính và tiên đề OWL" với số triple mỗi tiên đề sinh ra; bấm mã lớp mở `/ontology/{term}` (Turtle) |
| `/entity/:id` Thực thể | X là ai, sự nghiệp (timeline) và quan hệ (đồ thị mở rộng được), nối ra LOD thế nào? |
| `/ask?q=` Hỏi đáp | Hỏi tiếng Việt → SPARQL → kết quả (có/không suy luận) → câu trả lời → đồ thị bằng chứng; ô "SPARQL mode" (`&mode=sparql`) bỏ bước LLM viết câu trả lời, chỉ hiện truy vấn và bảng thô, bấm "Viết câu trả lời" khi cần |
| `/sparql?query=` SPARQL | Soạn và chạy truy vấn, tải JSON/CSV; endpoint chuẩn cũng ở `/sparql` |
| `/map` Bản đồ | Tỉnh hiện hành/cũ, mũi tên kế thừa (`vio:successor`), đại học, sân vận động |

Quy ước hiển thị xuyên suốt: **khai báo = nét liền, màu trung tính; suy luận = nét đứt, màu tím**. Công tắc
"Hiện suy luận" ở thanh trên ẩn phần suy luận ở mọi đồ thị.

## Hỏi đáp khi không có LLM

Không có `OPENAI_API_KEY` (`/api/health` báo `llm: false`) thì 5 câu hỏi mẫu (`ui/api/presets.py`) vẫn chạy:
SPARQL lấy từ `ui/api/demo_cache.json` nhưng **chạy thật** trên graph, nên kết quả luôn đúng dữ liệu hiện tại.
Bước "Câu trả lời" bằng chữ khi đó trống (bản commit do tay viết, `answer: null`). Có key thì:
```bash
echo 'OPENAI_API_KEY=...' >> .env
.venv/bin/python -m ui.api.cache_demo            # sinh lại demo_cache.json kèm câu trả lời; kiểm tra SPARQL trước khi commit
```
Có key, câu hỏi lạ được LLM sinh SPARQL và trả lời bình thường (`mode: "llm"` ép bỏ qua cache).

## API

Tài liệu OpenAPI: `/api/docs`.

| Endpoint | Việc |
|---|---|
| `GET /api/health` | `ready`, `asserted_ready`, `llm`, tiến độ nạp |
| `GET /api/overview` | số liệu tổng quan, lớp, suy luận theo thuộc tính, thực thể nổi bật, câu hỏi mẫu |
| `GET /api/tree?q=` | dữ liệu tab Cây tài nguyên: lớp (phẳng, cha trước con), thực thể trực tiếp (300 tên, 100 khi lọc), ba nhóm còn lại; lọc không cần dấu như Gradio |
| `GET /api/ontology` | cây lớp (kèm thuộc tính có domain là lớp đó), 54 thuộc tính, tiên đề OWL (chuỗi, nghịch đảo, ràng buộc, rời nhau) và số triple suy luận của từng tiên đề |
| `GET /api/search?q=` | tìm thực thể (không cần dấu) |
| `GET /api/entity/{id}` | dữ liệu màn Thực thể |
| `GET /api/neighbors/{id}` | lân cận một bước (đồ thị) |
| `GET /api/entity/{id}/tree` | tab Cây quan hệ: cây lồng nhau tối đa 3 bước (gốc → đội → sân → tỉnh), chỉ triple khai báo (trừ `vio:playedFor`), chặng thi đấu thay bằng đội kèm ghi chú năm/trận/bàn; cùng giới hạn với trang của team |
| `GET /api/subgraph?ids=a&ids=b` | cạnh giữa một tập thực thể; **lặp tham số `ids`**, không dùng dấu phẩy vì id có thể chứa `,` |
| `POST /api/ask`, `/api/ask/answer`, `/api/ask/asserted` | hỏi đáp (xem trên) |
| `GET /api/sparql/examples`, `POST /api/sparql` | SPARQL cho giao diện (`inference: false` chạy trên triple khai báo) |
| `GET/POST /sparql` | endpoint chuẩn SPARQL 1.1 Protocol, dùng lại `vidbpedia.web.endpoint` của team: JSON (mặc định), XML, CSV theo `Accept` hoặc `?format=`; CONSTRUCT trả Turtle, N-Triples, JSON-LD, RDF/XML; chặn `FROM` và `SERVICE`; `?inference=false` ngoài chuẩn |
| `GET /api/map` | điểm có toạ độ và quan hệ kế thừa |
| `/resource/…`, `/data/…`, `/ontology/{term}`, `/ontology.ttl` | Linked Data của team, gắn nguyên vẹn; `/ontology/{term}` trả định nghĩa Turtle đầy đủ (kể cả blank node của restriction và chuỗi thuộc tính), `/ontology.ttl` trả cả ontology |

Khi graph chưa nạp xong, các đường dẫn cần graph trả 503 (`/api/health` luôn trả lời và báo tiến độ).
Trình duyệt mở `/sparql?query=…` (Accept: text/html) thấy trang SPARQL của UI; `curl` mới gọi endpoint:
```bash
curl -G localhost:8000/sparql -H 'Accept: application/sparql-results+json' --data-urlencode 'query=ASK { ?s ?p ?o }'
curl -L -H 'Accept: text/turtle' localhost:8000/resource/Đặng_Quang_Huy       # Linked Data (dereference ra Turtle)
```

## Kiểm tra
```bash
.venv/bin/python -m pytest ui/tests             # dùng dataset thật, không gọi LLM (LLM giả trong test_ask.py)
.venv/bin/ruff check ui && .venv/bin/ruff format --check ui
cd ui/web && npm run build                      # kiểm kiểu TypeScript + build
```

## Lưu ý
- rdflib không có timeout cho truy vấn: truy vấn nặng không có `LIMIT` ở trang SPARQL có thể chạy rất lâu.
- Bản đồ cần Internet để tải nền OpenStreetMap; chấm và mũi tên vẫn hiện khi offline.
- Graph "chỉ khai báo" (để so sánh suy luận) nạp thêm ở thread nền sau graph chính; câu hỏi đến sớm hơn sẽ thấy
  "đang nạp" rồi tự cập nhật.
- `npm audit` báo 2 lỗ hổng mức vừa ở `react-router-dom` v6 (plan chốt v6; chỉ ảnh hưởng khi triển khai công khai).
