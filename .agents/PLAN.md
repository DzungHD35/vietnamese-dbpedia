# PLAN — UI demo độc lập (`ui/`)

> Kế hoạch code chi tiết để giao cho agent thực thi. Đọc kèm `CORE.md` (vì sao chọn các màn này).
> Trạng thái: **đã duyệt, sẵn sàng thực thi** (2026-10-08). Làm theo thứ tự phase; mỗi phase có tiêu chí xong.
> Quyết định đã chốt (CORE.md D4–D6): stack Vite + React + TS + Cytoscape; hỏi đáp chạy được không cần LLM nhờ
> `demo_cache.json`; câu chuyện demo Đặng Quang Huy → Than Quảng Ninh. **Không tự đổi các quyết định này.**
>
> Cách làm việc: mỗi lượt làm 1–2 phase được giao, chạy đủ tiêu chí "xong khi" của phase đó, commit, rồi
> **dừng lại báo cáo** (đã làm gì, lệnh kiểm tra đã chạy và kết quả, chỗ nào lệch khỏi plan và vì sao).
> Gặp chỗ plan sai so với code thật (tên hàm, id thực thể, số liệu) thì làm theo code thật và ghi vào báo cáo.

## 0. Luật bắt buộc (đọc trước khi code)

1. **Không sửa** `vidbpedia/`, `data/`, `ontology/`, `tests/`, `requirements.txt`. Chỉ thêm file trong `ui/` (và
   `.agents/`). Logic có sẵn thì **import và gọi**, không copy nguyên khối.
2. Mọi chỗ gọi hàm/thuộc tính **private** của team (`ResourceView._neighbors`, `SparqlBasedKGRAG._complete`, …)
   chỉ được nằm trong **một file** `ui/api/adapters.py`. Team đổi code thì chỉ phải sửa một chỗ.
3. Code, comment, chuỗi UI bằng **tiếng Việt**. Python: ruff, line-length 110 (theo `pyproject.toml`).
4. `.gitignore` của repo bỏ qua các thư mục tên `lib/`, `build/`, `dist/`, `parts/`. **Không đặt tên thư mục
   như vậy** trong `ui/` (dùng `utils/`, không dùng `src/lib/`). `ui/web/dist/` bị bỏ qua là đúng ý.
5. Không thêm dependency Python: `fastapi`, `uvicorn`, `rdflib`, `openai`, `python-dotenv` đã có qua
   `requirements.txt`. Frontend chỉ dùng dependency liệt kê ở §3.1.
6. Không hard-code danh sách lớp nếu đọc được từ ontology. Danh sách preset cho demo (câu hỏi, thực thể nổi
   bật) thì được hard-code, đặt trong **một file** `ui/api/presets.py`.
7. Commit message tiếng Anh, không thêm trailer Co-Authored-By.

## 1. Kiến trúc

```
ui/
├── __init__.py
├── README.md                 # cách chạy dev / prod
├── api/                      # FastAPI riêng, chỉ trả JSON (+ phục vụ build frontend ở prod)
│   ├── __init__.py
│   ├── __main__.py           # python -m ui.api [--port 8000] [--host 127.0.0.1]
│   ├── app.py                # create_app(): lifespan nạp graph, gắn router, static
│   ├── state.py              # class KG: giữ graph, view, tree, rag, asserted graph (singleton)
│   ├── adapters.py           # NƠI DUY NHẤT gọi API private của vidbpedia; trả dict thuần
│   ├── serialize.py          # term → JSON (node, literal, edge), hàm dùng chung
│   ├── presets.py            # thực thể nổi bật, câu hỏi demo
│   ├── demo_cache.json       # cache câu hỏi demo (SPARQL + câu trả lời), commit vào repo
│   ├── cache_demo.py         # python -m ui.api.cache_demo: gọi LLM để sinh demo_cache.json
│   └── routes/
│       ├── __init__.py
│       ├── overview.py       # /api/overview
│       ├── entity.py         # /api/search, /api/entity, /api/neighbors, /api/subgraph
│       ├── ask.py            # /api/ask, /api/ask/answer
│       ├── sparql.py         # /api/sparql, /api/sparql/examples, /sparql (chuẩn W3C)
│       └── geo.py            # /api/map (phase tuỳ chọn)
├── tests/
│   ├── conftest.py           # TestClient dùng chung cả phiên (nạp graph 1 lần)
│   └── test_api.py
└── web/                      # Vite + React + TypeScript
    ├── package.json, vite.config.ts, tsconfig.json, index.html
    └── src/
        ├── main.tsx, App.tsx
        ├── api/{client.ts, types.ts}
        ├── styles/{tokens.css, global.css}
        ├── utils/{format.ts, kinds.ts}
        ├── components/…      # xem §3.3
        └── pages/{OverviewPage, EntityPage, AskPage, SparqlPage, MapPage}.tsx
```

**Chạy:**
- Dev: `.venv/bin/python -m ui.api --port 8000` + `cd ui/web && npm run dev` (Vite :5173, proxy sang :8000).
- Prod/demo: `cd ui/web && npm run build`, rồi `.venv/bin/python -m ui.api` phục vụ cả `ui/web/dist` tại `/`.
- Server Gradio của team (`python -m vidbpedia serve`, :7860) vẫn chạy độc lập như cũ, không bị ảnh hưởng.

## 2. Backend `ui/api`

### 2.1 Nạp dữ liệu (`state.py`)

```python
class KG:
    graph: Graph            # SparqlService(DATASET + ".nt").graph — đầy đủ: khai báo + suy luận + ontology
    service: SparqlService
    view: ResourceView      # ResourceView.from_files(graph, dataset_file) → có view.inferred (set triple)
    tree: ResourceTree      # ResourceTree(view)
    rag: SparqlBasedKGRAG   # SparqlBasedKGRAG(graph); chưa có OPENAI_API_KEY thì rag.client báo lỗi khi gọi
    stats: dict             # service.stats (đọc data/vietnamese_dbpedia_stats.json)
    asserted: Graph | None  # data/parts/asserted.nt + data/parts/ontology.ttl, nạp ở THREAD NỀN
    asserted_ready: threading.Event
```

- Dùng `lifespan` của FastAPI để nạp `KG` một lần (~1 phút), gọi `load_dotenv()` và `setup_logging()` của
  `vidbpedia.common`. Đường dẫn lấy từ `vidbpedia.common` (`DATASET`, `PARTS_DIR`), không viết cứng.
- Graph "chỉ khai báo" nạp trong `threading.Thread(daemon=True)` sau khi graph chính sẵn sàng. Endpoint nào cần
  nó mà chưa nạp xong thì trả `asserted_rows: null` kèm `"asserted_status": "loading"`, **không** chặn request.
- Endpoint viết bằng `def` (không `async def`) để FastAPI đẩy sang threadpool: rdflib và lời gọi LLM đều blocking.
- Đọc graph đồng thời từ nhiều thread là an toàn; API **không bao giờ ghi** vào graph.

### 2.2 Quy ước JSON chung (`serialize.py`)

- **id thực thể** = local name trong `vres:` (`view.local(iri)`), ví dụ `"Đặng_Quang_Huy"`. Frontend luôn
  `encodeURIComponent(id)` khi đặt vào URL. Route nhận id dùng `{name:path}`; tra lại bằng `view.resolve(name)`
  (hàm này đã xử lý ký tự được mã hoá %).
- Node:
  ```ts
  { id: string, iri: string, label: string, cls: string /* view.class_name */, kind: Kind, external?: boolean }
  // Kind = "player"|"club"|"stadium"|"uni"|"prov"|"station"|"other"|"lod"   (view.kind; "lod" cho IRI ngoài)
  ```
- Giá trị (literal hoặc IRI):
  ```ts
  { type: "literal", value: string, lang?: string, datatype?: string /* qname */, inferred: boolean }
  { type: "iri", node: Node, inferred: boolean }
  ```
- Edge: `{ source: id, target: id, prop: string /* qname */, propLabel: string, inferred: boolean }`.
  Triple nào có trong `view.inferred` thì `inferred: true`. Đây là **thông tin quan trọng nhất của toàn bộ UI**.
- Năm (`xsd:gYear`): đổi sang `int` bằng `int(str(lit)[:5].rstrip("-"))` trong `try`; lỗi thì để `null`
  (dataset có năm âm, trước Công nguyên).
- Số lượng giới hạn (để trang của tỉnh lớn vẫn nhẹ): hằng số đặt ở đầu mỗi file route, ví dụ `MAX_VALUES = 40`.

### 2.3 Endpoint

| Method & path | Mô tả | Gọi lại |
|---|---|---|
| `GET /api/health` | `{ready, asserted_ready, llm: bool}`; `llm` = có `OPENAI_API_KEY` | — |
| `GET /api/overview` | Số liệu cho màn Tổng quan | `stats`, `ResourceTree`, `view.inferred` |
| `GET /api/search?q=&limit=10` | `[{id, label, cls, kind}]` | `view.search` (trả `(display, local)`) |
| `GET /api/entity/{name}` | Toàn bộ dữ liệu màn Thực thể | `view.*`, `adapters` |
| `GET /api/neighbors/{name}?limit=24` | `{center: Node, nodes, edges, hidden}` | `adapters.neighbors` (bọc `_neighbors`) |
| `GET /api/subgraph?ids=a,b,c` | Cạnh giữa một tập thực thể (bằng chứng hỏi đáp) | `graph` |
| `POST /api/ask` | Sinh + chạy SPARQL, so sánh có/không suy luận | `rag.generate_and_run` |
| `POST /api/ask/answer` | LLM viết câu trả lời từ kết quả | `adapters.answer` |
| `GET /api/sparql/examples` | `EXAMPLE_QUERIES` | `vidbpedia.web.examples` |
| `POST /api/sparql` | Chạy truy vấn tuỳ ý (UI) | `graph.query(q, initNs=PREFIXES)` |
| `GET/POST /sparql` | Endpoint SPARQL chuẩn (SPARQL 1.1 Protocol, kết quả JSON/XML/CSV) | `graph.query` |
| `/resource/…`, `/data/…`, `/ontology/…` | Linked Data | `add_routes(app, view)` của team, **gọi lại nguyên hàm** |
| `GET /api/map` | (tuỳ chọn) điểm toạ độ + quan hệ sáp nhập | `graph` |

#### `GET /api/overview`
```ts
{
  stats: { total, asserted, inferred, ontology, entities, careerStations, sameAsDbpedia, sameAsWikidata,
           validationErrors, validationWarnings, built, reasoner, reasoningSeconds },
  byClass: [{ id: qname, label, parent: qname|null, dbo: qname[], total, asserted, direct }],
      // từ ResourceTree: classes, parent, dbo, members (len → total), asserted, direct (len)
  inferredByPredicate: [{ prop: qname, label, count }],   // đếm p trong view.inferred, top 12
  featured: Node[]                                         // từ presets.FEATURED, bỏ id không resolve được
}
```
`inferredByPredicate` trả lời câu "suy luận thêm được gì": ví dụ `rdf:type` (lớp cha `dbo:`), `vio:playedFor`
(2.772, property chain), `vio:hasPlayer` (inverseOf), các thuộc tính `dbo:` tương đương.

#### `GET /api/entity/{name}` → 404 nếu `view.resolve` trả `None`
```ts
{
  node: Node,
  abstract: string|null,          // dbo:abstract @vi, nếu không có thì rdfs:comment
  thumbnail: string|null,         // dbo:thumbnail
  altLabels: string[],            // skos:altLabel
  classes: [{ id: qname, label, inferred, parent: qname|null, also: qname[] }],
      // làm lại logic của ResourceView._class_tree dưới dạng dữ liệu (lớp vio:/dbo:, cha chính ưu tiên vio:)
  lod: { wikipedia: string|null, dbpedia: string[], wikidata: string[], derivedFrom: string|null,
         lat: number|null, lon: number|null, linkedData: string /* "/resource/<id>" */ },
  career: [{ station: id, kind: "youth"|"club"|"national", team: Node|null, start: int|null, end: int|null,
             apps: int|null, goals: int|null, onLoan: boolean }],
      // từ vio:careerStation; kind theo rdf:type YouthStation/ClubStation/NationalTeamStation
      // sắp theo (start, kind) — KHÁC thứ tự cây của team, timeline cần thứ tự thời gian
  facts: [{ prop: qname, label, ns: "vio"|"dbo"|"other"|"vip", values: Value[], more: int }],
      // mọi (p, o) đi ra, nhóm theo p, thứ tự theo ResourceView._prop_key; bỏ vio:careerStation (đã ở career)
  incoming: [{ prop: qname, label, count, items: (Node & {inferred})[] }],   // tối đa MAX_VALUES mỗi nhóm
  counts: { asserted: int, inferred: int }   // số triple có thực thể này làm chủ ngữ, theo từng loại
}
```
Lưu ý dữ liệu: mỗi `CareerStation` có thêm triple suy luận (`rdf:type vio:CareerStation`, `dbo:TimePeriod`,
`dbo:team`, `dbo:numberOfMatches`…). Chỉ đọc thuộc tính `vio:` khi dựng `career`.

#### `GET /api/neighbors/{name}?limit=24`
- Bọc `view._neighbors(iri)` → `(out, inc)`, mỗi phần tử là `(node, [props])`. Mỗi cặp (node, prop) thành **một
  edge** (cờ `inferred` tính theo từng triple). Thêm node `lod` cho `owl:sameAs` và `foaf:isPrimaryTopicOf`
  (`external: true`, id = IRI đầy đủ).
- Cắt bớt theo `limit`, xoay vòng giữa các prop (bọc `ResourceView._round_robin`) để prop nào cũng có mặt.
  `hidden` = số node bị cắt.
- `_neighbors` không đi qua `vio:careerStation`; quan hệ cầu thủ → CLB hiện ra nhờ `vio:playedFor` (suy luận).
  Đây là điều muốn khoe: cạnh nét đứt.

#### `GET /api/subgraph?ids=a,b,c` (tối đa 60 id)
Với mỗi cặp trong tập: lấy triple `(s, p, o)` có `p` thuộc `LINK_PROPS` (import từ `resource_page`) hoặc
`p` bắt đầu bằng `vio:` và `o` là IRI. Trả `{nodes, edges}` như neighbors. Dùng cho đồ thị bằng chứng.

#### `POST /api/ask`
```ts
// body
{ question: string, mode?: "auto"|"cache"|"llm" }   // auto: có trong cache thì dùng cache, không thì LLM
// response
{
  question, source: "cache"|"llm", sparql: string, attempts: int, error: string|null,
  columns: string[], rows: Record<string,string>[],      // tối đa 200 dòng; rowsTotal: int
  rowsTotal: int,
  links: Record<string, Node>,   // giá trị ô → Node, để frontend biến ô thành link (xem dưới)
  evidence: Node[],               // các Node khác nhau trong links, tối đa 60
  asserted: { rows: int|null, status: "ok"|"loading"|"error", error?: string }
}
```
- `mode=auto`: so khớp câu hỏi với `demo_cache.json` bằng `fold()` (import từ `resource_page`). Khớp thì lấy
  SPARQL trong cache và **vẫn chạy thật** trên graph (rẻ, kết quả luôn đúng dữ liệu hiện tại). Không khớp: gọi
  `rag.generate_and_run(question)`. Không có key và không khớp cache: trả 503 kèm thông báo tiếng Việt.
- **Liên kết ô kết quả** (`links`): `rag.run_sparql` đã `unquote` IRI, và truy vấn LLM sinh ra thường chọn nhãn
  thay vì IRI. Với mỗi ô: (a) bắt đầu bằng `http://vi.dbpedia.org/resource/` → `view.resolve`; (b) ngược lại,
  nếu `fold(ô)` trùng **nguyên văn** một nhãn trong chỉ mục tên → Node đó. Chỉ mục tên dựng từ
  `view._entries` (list `(fold(tên), iri)`), bọc trong `adapters.label_index()`. Ô khớp nhiều thực thể thì bỏ qua.
- **So sánh suy luận** (`asserted`): chạy lại đúng câu SPARQL trên `KG.asserted` và đếm số dòng.
  Ví dụ "Cầu thủ nào từng chơi cho Than Quảng Ninh?" dùng `vio:playedFor`: có suy luận 39 dòng, chỉ khai báo
  0 dòng. Chạy câu SPARQL đã qua `rag._validate` (bọc trong adapters) để có đủ PREFIX.

#### `POST /api/ask/answer`
Body `{question, sparql, rows}` → `{answer, reasoning, source}`. `mode` khớp cache và cache có `answer` thì trả
cache. Ngược lại `adapters.answer(rag, question, sparql, rows)` dựng lại nửa sau của `SparqlBasedKGRAG.query`
(format `ANSWER_TEMPLATE`, `rag._complete`, `rag._parse_answer`). Tách hai bước để UI hiện SPARQL + bảng ngay,
câu trả lời đến sau (không cần stream).

#### `POST /api/sparql` và `/sparql`
- `/api/sparql` body `{query, inference: bool = true}` → `{type: "SELECT"|"ASK"|"CONSTRUCT", columns, rows,
  links, total, ms, error}`. `inference=false` chạy trên `KG.asserted`. Lỗi cú pháp trả 200 với `error` (UI hiện).
  Giới hạn 1.000 dòng trả về.
- `/sparql`: `GET ?query=` hoặc `POST` form/`application/sparql-query`; chọn định dạng theo `Accept`
  (`application/sparql-results+json` mặc định, `…+xml`, `text/csv`; CONSTRUCT thì `text/turtle`). Dùng
  `result.serialize(format=…)`. Thêm header `Access-Control-Allow-Origin: *`. Đây là bằng chứng "SPARQL
  endpoint chuẩn" cho yêu cầu 5 của đề.

#### Linked Data
Gọi `add_routes(app, view)` **trước** khi mount static. Route `/resource/{x}` của team redirect trình duyệt tới
`/?resource=<x>`; frontend bắt query này và chuyển sang `/entity/<x>` (xem §3.2). Không cần viết lại gì.

#### Static (prod)
Nếu có `ui/web/dist`: mount `/assets` bằng `StaticFiles`, và route catch-all `GET /{path:path}` (đăng ký
**cuối cùng**, bỏ qua tiền tố `api/`, `sparql`, `resource/`, `data/`, `ontology/`, `page/`) trả `index.html`.

### 2.4 `presets.py` và `demo_cache.json`

```python
FEATURED = ["Đặng_Quang_Huy", "Nguyễn_Công_Phượng", "Câu_lạc_bộ_bóng_đá_Than_Quảng_Ninh",
            "Sân_vận_động_Mỹ_Đình", "Hà_Nội", "Đại_học_Cần_Thơ"]   # kiểm tra từng id resolve được; sai thì sửa
DEMO_QUESTIONS = [
    "Cầu thủ nào từng chơi cho Than Quảng Ninh?",          # khoe property chain: 39 vs 0 dòng
    "Quá trình thi đấu ở câu lạc bộ của Công Phượng?",
    "Câu lạc bộ nào có sân nhà ở Hà Nội?",                # nhiều bước CLB → sân → tỉnh
    "Tỉnh nào có nhiều cầu thủ quê quán nhất?",
    "Đại học Cần Thơ tương ứng với tài nguyên nào trên DBpedia?",  # owl:sameAs
]
```
Id trong `FEATURED` là phỏng đoán: **phải** kiểm tra bằng `view.resolve` hoặc `view.search` rồi sửa cho đúng.

`demo_cache.json`: `[{question, sparql, answer, reasoning, generated_at}]`. `python -m ui.api.cache_demo` nạp
graph, gọi `rag.query(q)` cho từng câu trong `DEMO_QUESTIONS` và ghi file (cần key). Nếu chưa có key: tự viết
SPARQL cho 5 câu (dựa theo ví dụ trong `SPARQL_GENERATION_TEMPLATE` của `kg_rag.py`), để `answer: null`; khi đó
UI chỉ hiện bảng và đồ thị bằng chứng, không có đoạn trả lời.

### 2.5 Test (`ui/tests`)
`conftest.py`: fixture `client` scope `session`, tạo `TestClient(create_app())` trong `with` để chạy lifespan.
Chạy: `.venv/bin/python -m pytest ui/tests` (`pyproject` chỉ khai báo `tests/`, nên phải truyền đường dẫn).
Các ca tối thiểu:
- `/api/overview`: `stats.total == 131233` (đọc từ stats json, đừng hard-code; so `asserted + inferred + ontology`).
- `/api/search?q=dang quang huy` (không dấu) có `Đặng_Quang_Huy`.
- `/api/entity/Đặng_Quang_Huy`: `career` không rỗng, có station `kind == "national"`, `start == 2016`.
- `/api/entity/Không_có` → 404.
- `/api/neighbors/<CLB Than Quảng Ninh>`: có ít nhất một edge `prop == "vio:playedFor"` và `inferred == true`.
- `/api/ask` với `mode="cache"` cho câu Than Quảng Ninh: `rowsTotal > 0`, `asserted.rows == 0` (chờ
  `asserted_ready` tối đa 120s trong test).
- `/api/sparql` `inference=false` với `SELECT (COUNT(*) AS ?n) WHERE { ?s vio:playedFor ?o }` → 0.
- `/sparql?query=ASK{?s ?p ?o}` với `Accept: application/sparql-results+json` → `{"boolean": true}`.
- Không test nào gọi LLM thật.

## 3. Frontend `ui/web`

### 3.1 Stack
- Vite + React 18 + TypeScript (strict). `react-router-dom` v6.
- `cytoscape` + `cytoscape-fcose` cho đồ thị. Timeline và biểu đồ cột **tự vẽ bằng SVG/CSS** (dữ liệu nhỏ, không
  cần thư viện).
- (Tuỳ chọn, phase 6) `leaflet` + `react-leaflet` cho bản đồ.
- CSS thuần với biến CSS (`tokens.css`), không Tailwind, không UI kit. Font: `Be Vietnam Pro` (Google Fonts)
  để hiển thị dấu tiếng Việt đẹp.
- Không có state library: dùng `useState`/`useEffect` + một hook `useApi(url)` nhỏ (loading/error/data, huỷ
  request bằng `AbortController`).
- `vite.config.ts`: proxy `/api`, `/sparql`, `/resource`, `/data`, `/ontology` → `http://127.0.0.1:8000`.

### 3.2 Điều hướng
Thanh trên cùng cố định: logo "Vietnamese DBpedia" · **Tổng quan** · **Hỏi đáp** · SPARQL · (Bản đồ) · ô tìm
kiếm thực thể (luôn hiện). Một công tắc toàn cục **"Hiện suy luận"** (mặc định bật), lưu trong React context
`InferenceContext` và `localStorage` (bọc try/catch).

| Route | Trang |
|---|---|
| `/` | OverviewPage. Nếu URL có `?resource=X` (do `/resource/X` redirect tới) thì `navigate("/entity/X")` |
| `/entity/:id` | EntityPage |
| `/ask?q=` | AskPage (có `q` thì tự chạy) |
| `/sparql?query=` | SparqlPage |
| `/map` | MapPage (tuỳ chọn) |

### 3.3 Hệ thống hiển thị dùng chung (quan trọng hơn chi tiết thẩm mỹ)
- **Khai báo vs suy luận** phải nhìn ra giống nhau ở mọi màn: khai báo = nét liền, màu trung tính; suy luận =
  **nét đứt + màu nhấn `--inferred`** (một màu duy nhất, ví dụ tím). Áp cho: cạnh đồ thị, badge giá trị, đoạn
  cột trong biểu đồ, lớp trong cây phân lớp. Tắt "Hiện suy luận" thì ẩn hết phần suy luận.
- **Màu theo loại thực thể** (`utils/kinds.ts`): player, club, stadium, uni, prov, station, lod, other.
  Dùng chung cho node đồ thị, chip, chấm màu trong kết quả tìm kiếm.
- Số định dạng kiểu Việt: `131.233` (`Intl.NumberFormat("vi-VN")`).

Component:
| Component | Việc |
|---|---|
| `SearchBox` | debounce 200ms → `/api/search`; dropdown có chấm màu theo kind + lớp; Enter/bấm → `/entity/:id`; điều khiển được bằng phím ↑↓ |
| `EntityLink` | link nội bộ tới `/entity/:id` kèm chấm màu; IRI ngoài thì mở tab mới với ↗ |
| `InferredBadge` | nhãn nhỏ "suy luận" |
| `StatTile` | số lớn + nhãn + chú thích nhỏ; có thể bấm |
| `ClassBars` | cây lớp `vio:` dạng thanh ngang thụt lề: độ dài ∝ `total`, chia 2 đoạn khai báo/suy luận, bên cạnh ghi `⊑ dbo:X` |
| `GraphView` | cytoscape; props `{nodes, edges, centerId?, expandable, onOpen(id)}`; xem §3.5 |
| `CareerTimeline` | SVG; xem §3.4 |
| `SparqlBlock` | `<pre>` có tô màu từ khoá/prefix đơn giản bằng regex; nút Sao chép, nút "Mở trong SPARQL" |
| `ResultTable` | bảng; ô nào có trong `links` thì hiện `EntityLink`; IRI dài cắt gọn |
| `InferenceContrast` | "Có suy luận: **39** dòng · Chỉ khai báo: **0** dòng" và một câu giải thích ngắn |
| `Loading`, `ErrorState`, `Empty` | trạng thái chung; lần nạp đầu có thể ~1 phút, `/api/health` báo "Đang nạp graph…" |

### 3.4 Màn 1: Tổng quan (`/`)
Câu hỏi 10 giây: *Graph chứa gì, lớn cỡ nào, suy luận thêm được bao nhiêu?*
1. Hàng `StatTile`: tổng triple; khai báo; **suy luận (+47%)**; thực thể; `owl:sameAs` → DBpedia EN; → Wikidata;
   lỗi kiểm tra = 0. Bên dưới là một thanh ngang 100% chia khai báo / suy luận / ontology.
2. Hai cột:
   - Trái: `ClassBars` (cây lớp, dữ liệu `byClass`).
   - Phải: "Suy luận thêm được gì": danh sách `inferredByPredicate` dạng thanh ngang (prop, số lượng); dòng
     `vio:playedFor` kèm chú thích "property chain `careerStation ∘ team`".
3. Dải pipeline tĩnh một dòng: Wikipedia tiếng Việt + Wikidata → infobox mapping → RDF → OWL 2 RL → `owl:sameAs`
   → SPARQL / Linked Data.
4. Thẻ "Bắt đầu khám phá": các `featured` → `/entity/:id`; các `DEMO_QUESTIONS` → `/ask?q=`.

### 3.5 Màn 2: Thực thể (`/entity/:id`), màn quan trọng nhất
Câu hỏi 10 giây: *X là ai/cái gì, cuộc đời và quan hệ ra sao, nối ra thế giới LOD thế nào?*

Bố cục (màn 1366×768 trở lên phải thấy phần 1–2 mà không cần cuộn):
1. **Header**: ảnh nhỏ (thumbnail), tên, chip lớp chính (`cls`), dãy chip LOD: Wikipedia ↗, DBpedia EN ↗,
   Wikidata Qxx ↗, "Linked Data" (`/resource/<id>`, mở tab mới), Bản đồ (nếu có lat/lon). Abstract cắt 3 dòng,
   bấm để xem hết. Dòng phụ nhỏ: "N triple khai báo · M triple suy luận".
2. **Hai cột**:
   - Trái (khoảng 45%): nếu `career` không rỗng thì `CareerTimeline`; không có thì "Thông tin chính" (5–8 fact
     `vio:` quan trọng nhất: năm thành lập, dân số, diện tích, tỉnh, sân nhà…).
   - Phải (khoảng 55%): `GraphView` với `/api/neighbors/:id`.
3. **Tab bên dưới**: "Thuộc tính" (`facts`, nhóm theo namespace; nhóm `dbo:`/suy luận ẩn khi tắt suy luận) ·
   "Được tham chiếu bởi" (`incoming`) · "Cây phân lớp" (`classes`, dạng cây thụt lề, lớp suy luận có badge) ·
   "Truy vấn" (nút mở SparqlPage với `DESCRIBE <iri>` hoặc SELECT ?p ?o).

`CareerTimeline`:
- Trục X theo năm từ `min(start)` đến `max(end ?? năm hiện tại)`; vạch mỗi năm, nhãn mỗi 2–5 năm tuỳ độ dài.
- 3 làn: Trẻ / CLB / Đội tuyển (chỉ hiện làn có dữ liệu). Mỗi station là một thanh: nhãn tên đội (cắt gọn),
  màu theo làn; `onLoan` thì sọc chéo; `end` null thì thanh mờ dần về bên phải ("đến nay").
- Hover: tooltip "Đội · 2016–2019 · 45 trận, 3 bàn · cho mượn". Bấm → `/entity/<team.id>`.
- Station thiếu `start` thì gom vào dòng "Không rõ năm" phía dưới (không bỏ mất).

`GraphView`:
- Layout `fcose`, node màu theo kind, node trung tâm to hơn, viền đậm. Node `lod` hình thoi, viền đứt.
- Cạnh: nhãn là phần sau dấu `:` của prop (`playedFor`), mũi tên; `inferred` thì nét đứt + màu `--inferred`.
- **Bấm 1 lần** vào node: mở rộng, gọi `/api/neighbors/<id>`, thêm node/cạnh mới (bỏ trùng theo id và theo
  `source|prop|target`), chạy layout cho phần mới với `fit: false`, các node cũ giữ nguyên chỗ. Node đã mở rộng
  có dấu nhỏ.
- **Bấm đúp** hoặc nút "Mở trang" trong tooltip: `onOpen(id)` → điều hướng. Node `lod`: mở IRI ở tab mới.
- Thanh công cụ nhỏ: Thu gọn về ban đầu · Vừa khung · chú giải màu.
- Giới hạn 150 node trên canvas; vượt thì không mở rộng nữa và báo.
- Công tắc suy luận toàn cục tắt thì ẩn cạnh `inferred` (`display: none`) và node chỉ còn nối bằng cạnh suy luận.

### 3.6 Màn 3: Hỏi đáp có bằng chứng (`/ask`)
Câu hỏi 10 giây: *Hỏi tiếng Việt, graph trả lời được không, và trả lời từ đâu?*
1. Ô nhập lớn + chip các câu demo. Chưa có LLM (`/api/health.llm == false`) thì ghi "Chế độ demo: chỉ các câu
   hỏi mẫu" và vẫn cho gõ (gõ câu lạ thì báo lỗi 503 bằng chữ dễ hiểu).
2. Gửi → `POST /api/ask`. Hiện theo thứ tự, mỗi khối có tiêu đề bước:
   - **① SPARQL sinh ra** (`SparqlBlock`, số lần thử `attempts`, nguồn cache/LLM).
   - **② Kết quả**: `InferenceContrast` + `ResultTable`.
   - **③ Câu trả lời**: gọi `POST /api/ask/answer` song song ngay khi có bước ①②; trong lúc chờ hiện skeleton;
     có `reasoning` thì để trong `<details>`.
   - **④ Bằng chứng trên graph**: `GraphView` với `/api/subgraph?ids=<evidence>`; bấm đúp → màn Thực thể.
3. Lưu 5 câu hỏi gần nhất trong session (state, không cần persist).

### 3.7 SPARQL (`/sparql`), phần râu ria nhưng phải chạy được
Textarea (monospace, Ctrl+Enter để chạy) + dropdown `EXAMPLE_QUERIES` + công tắc suy luận (riêng màn này, gửi
`inference`) + `ResultTable` có link + thời gian chạy + link "Endpoint chuẩn: `/sparql`" + nút tải
JSON/CSV (gọi `/sparql` với `Accept` tương ứng).

### 3.8 Bản đồ (`/map`), **tuỳ chọn, chỉ làm khi phase 1–5 xong**
`GET /api/map` → `{points: [{node, lat, lon, former: bool}], successions: [{from: id, to: id, year: int|null}]}`
(lat/lon từ `vio:latitude/longitude`; `former` = có `vio:FormerProvince`; succession từ `vio:successor`).
Leaflet + OSM tiles; tỉnh hiện hành chấm đặc, tỉnh cũ chấm rỗng, mũi tên kế thừa. Lưu ý: demo cần mạng để tải tile.
Trước khi làm: đếm xem tỉnh có toạ độ không (189 triple `vio:latitude` khai báo, phần lớn có thể là sân/trường).

## 4. Phase và tiêu chí xong

| Phase | Việc | Xong khi |
|---|---|---|
| **P0** Khung | `ui/api` (app, state, lifespan, `/api/health`, Linked Data routes, static), `ui/web` scaffold Vite, proxy, layout + nav trống, `ui/README.md` | `python -m ui.api` lên; `npm run dev` thấy nav; `/api/health` → `ready: true`; `curl -L -H "Accept: text/turtle" :8000/resource/Đặng_Quang_Huy` trả Turtle |
| **P1** API dữ liệu | `serialize`, `adapters`, `/api/overview`, `/search`, `/entity`, `/neighbors`, `/subgraph` + test | `pytest ui/tests` xanh; `ruff check ui` sạch |
| **P2** Tổng quan + tìm kiếm | `OverviewPage`, `StatTile`, `ClassBars`, `SearchBox`, `InferenceContext` | Phép thử 10 giây: nhìn màn đầu nói được "131K triple, 32% là suy luận, 18 lớp" |
| **P3** Thực thể | `EntityPage`, `CareerTimeline`, `GraphView` (mở rộng được), tab thuộc tính | Đặng Quang Huy: timeline đủ 3 làn; trang CLB Than Quảng Ninh: cạnh `playedFor` nét đứt; tắt suy luận thì cạnh biến mất |
| **P4** Hỏi đáp | `/api/ask`, `/api/ask/answer`, `demo_cache.json`, `AskPage` | Không có key: cả 5 câu demo chạy được; câu Than Quảng Ninh hiện "39 · 0"; bấm thực thể bằng chứng sang màn 2 |
| **P5** SPARQL + endpoint | `/api/sparql`, `/sparql`, `SparqlPage` | 9 mẫu chạy được; `curl ':8000/sparql?query=…'` trả SPARQL JSON |
| **P6** (tuỳ chọn) Bản đồ | `/api/map`, `MapPage` | — |
| **P7** Hoàn thiện | trạng thái loading/lỗi/rỗng, màn 1366×768 và 1920×1080, `npm run build` + chạy prod một process, cập nhật `ui/README.md` | Chạy trọn kịch bản demo (§5) không lỗi console |

Mỗi phase là một commit riêng (hoặc vài commit nhỏ), message tiếng Anh, ví dụ `ui: add entity API (P1)`.

## 5. Kịch bản demo mà UI phải chạy trơn (để tự kiểm)
1. Mở `/` → đọc số liệu, chỉ vào phần "Suy luận thêm được gì" (`playedFor` 2.772).
2. Bấm thẻ Đặng Quang Huy → timeline sự nghiệp; trên graph bấm mở rộng CLB → sân → tỉnh (đa bước).
3. Bấm chip DBpedia EN ↗ (sameAs) và "Linked Data" (dereference ra Turtle).
4. Sang Hỏi đáp → "Cầu thủ nào từng chơi cho Than Quảng Ninh?" → SPARQL dùng `vio:playedFor` → 39 dòng so với
   0 dòng khi chỉ dùng khai báo → đồ thị bằng chứng hình sao, toàn cạnh nét đứt → bấm một cầu thủ.
5. (Râu ria) Mở SPARQL, chạy một mẫu, chỉ ra `/sparql` là endpoint chuẩn.

## 6. Bẫy đã biết
- `view.search` trả `(display, local)`, với `display` = "Tên · Lớp". API phải trả `label` riêng (gọi
  `view.label(iri)`) chứ không cắt chuỗi display.
- `view.class_name` trả tên lớp tiếng Việt ("Cầu thủ"…) cho lớp chính; với lớp khác trả nhãn của lớp `vio:`.
- `ResourceTree(view)` dựng sẵn HTML trong `__init__` (mất vài giây lúc khởi động): chấp nhận được, đừng sửa.
- `view.inferred` là `set` triple rdflib, kiểm tra bằng `(s, p, o) in view.inferred`, rất nhanh.
- Id có ký tự đặc biệt (`(`, `)`, `,`, `%`…): luôn đi qua `view.resolve`, frontend luôn `encodeURIComponent`.
- `rdflib` không có timeout cho truy vấn: `/api/sparql` có thể treo với truy vấn nặng. Chấp nhận cho demo; ghi
  chú trong README.
- Thực thể "nhiễu" (vd "Giáo sư", "PGS.TS" là `vio:Person` trực tiếp): không lọc ở API, chỉ không đưa vào preset.
