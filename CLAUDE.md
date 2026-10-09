# Vietnamese DBpedia

Đồ án nhóm môn Semantic Web: DBpedia tiếng Việt (bóng đá VN, tỉnh thành, đại học) từ Wikipedia tiếng Việt +
Wikidata, ontology `vio:` căn theo DBpedia, suy luận OWL 2 RL, `owl:sameAs` sang DBpedia EN, giao diện SPARQL + KG-RAG.
Chi tiết: README.md (tổng quan, lệnh), ARCHITECTURE.md (pipeline, ontology, runtime).

## Lệnh
```bash
uv venv .venv && uv pip install -p .venv -r requirements.txt
.venv/bin/python -m vidbpedia serve      # http://127.0.0.1:7860, nạp graph ~1 phút
.venv/bin/python -m pytest               # ~1–2 phút, dùng dataset thật
```
Pipeline: `seeds → enrich → ontology → build → postprocess` (`python -m vidbpedia <bước>`, có `--offline`).

## Cấu trúc
- `ontology/*.ttl` → ghép thành `vi-ontology.ttl`; `vidbpedia/crawl` (thu thập, dựng RDF); `vidbpedia/kg` (kiểm tra, suy luận, VoID)
- `vidbpedia/web`: FastAPI + Gradio, `resource_page.py` (logic trang thực thể), `kg_rag.py`, `linked_data.py`
- `data/`: dataset đã dựng sẵn (commit), `data/parts/{asserted,inferred}.nt` tách khai báo/suy luận

## Quy ước
- Code, comment, UI bằng tiếng Việt; ruff, line-length 110.
- Không sửa tay `data/` hay `vi-ontology.ttl`: dựng lại bằng pipeline.

## Phân công
Repo do Phụng host. DHD phụ trách kịch bản demo + UI mới: UI đứng độc lập (thư mục riêng, API JSON mỏng),
không đụng logic crawl/kg của team. Tài liệu trao đổi chính: `.agents/CORE.md` (đọc trước khi làm UI);
khảo sát chi tiết ở `.agents/docs/`.
