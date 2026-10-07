# Hiện trạng UI của VDB (2026-10-07, commit 0ae2bbc)

## Stack
- Gradio 5.46 mount trên FastAPI (`vidbpedia/web/app.py`), một process; rdflib Graph nạp toàn bộ
  `data/vietnamese_dbpedia.nt` (22MB, 131K triple) vào RAM, khởi động ~1 phút.
- HTML do Python dựng thành chuỗi rồi đổ vào `gr.HTML` (`resource_page.py`, `resource_tree.py`).
- Chạy: `.venv/bin/python -m vidbpedia serve` → http://127.0.0.1:7860

## Các tab
| Tab | Nội dung | Mạnh | Yếu |
|---|---|---|---|
| Header | 4 ô số liệu + dòng đếm theo lớp | gọn | tĩnh |
| Cây tài nguyên | cây `<details>` theo lớp `vio:`, danh sách tên | thể hiện phân cấp + suy luận | dài, ít thông tin/diện tích; nhiễu dữ liệu ("Giáo sư", "NGƯT", "PGS.TS" là thực thể trực tiếp của vio:Person) |
| Tài nguyên | header+chip LOD, abstract+ảnh, cây phân lớp, thẻ LOD (curl), đồ thị lân cận SVG, cây quan hệ (sự nghiệp kèm trận/bàn), bảng thuộc tính, bảng ngược | nội dung semantic chắc nhất; phân biệt khai báo/suy luận khắp nơi | cuộn rất dài, mọi phần ngang hàng; graph tĩnh 1 bước, bấm nút = chuyển trang |
| Hỏi đáp | chatbot + SPARQL sinh ra + bảng | pipeline schema→SPARQL→tự sửa→trả lời+reasoning | không stream (2 lần gọi LLM), không nối với graph, cần API key |
| SPARQL | editor + 9 mẫu + Bảng/JSON/CSV | đủ dùng | kết quả không có liên kết |

Linked Data: `/resource/{tên}` 303 + content negotiation, `/data/{tên}.ttl|nt|jsonld|rdf`, `/ontology/{term}`.

## Logic tái sử dụng được (không phải viết lại)
- `ResourceView` (`resource_page.py`): `search` (không dấu), `resolve`, `label`, `class_name`, `kind`,
  `is_inferred`, `_neighbors`, `_class_tree`, `_tree_groups`, `_station_note`.
- `ResourceTree`: cây lớp, thành viên trực tiếp/suy luận.
- `SparqlBasedKGRAG` (`kg_rag.py`): `generate_and_run`, `query`, `get_schema`.
- `SparqlService.run`.
- `data/vietnamese_dbpedia_stats.json`, `data/parts/{asserted,inferred}.nt`.
