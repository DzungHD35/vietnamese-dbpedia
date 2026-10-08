# .agents/ — ghi chú làm việc (phần UI + kịch bản demo, phụ trách: DHD)

Ghi chú nội bộ cho agent và người làm UI. Không phải tài liệu chính thức của dự án (xem README.md, ARCHITECTURE.md).

**Đọc trước: [`CORE.md`](CORE.md)** — tài liệu trao đổi chính: tiêu chí, core views, quyết định, câu hỏi mở.

| File | Nội dung |
|---|---|
| `docs/01-current-state.md` | Hiện trạng UI Gradio của VDB (khảo sát 2026-10-07) |
| `docs/02-vinalkg-reference.md` | VinaLKG Explorer: ý tưởng nên học / không nên mang sang |
| `docs/03-ui-direction.md` | Dữ liệu sẵn có, ràng buộc kỹ thuật |
| `docs/04-core-views.md` | Core views đề xuất + prototype |
| [`PLAN.md`](PLAN.md) | **Kế hoạch code chi tiết cho `ui/`** (API contract, component, phase, tiêu chí xong) |

Nguyên tắc chung:
- Repo do Phụng host; DHD chỉ phụ trách kịch bản demo và UI.
- UI mới đứng độc lập (thư mục riêng + API JSON mỏng), không sửa logic của team trong `vidbpedia/crawl`, `vidbpedia/kg`.
- VinaLKG (`~/projects/personal/vn-legal-graph/web`) chỉ là nguồn cảm hứng, không port code.
