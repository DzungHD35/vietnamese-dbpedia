# CORE — Core views của UI demo

> Tài liệu trao đổi chính giữa DHD và agent. Chỉ chứa những quyết định quan trọng nhất.
> Chi tiết khảo sát nằm ở `docs/`. Trạng thái: **NHÁP — đang thảo luận** (2026-10-07).

## 1. Tiêu chí: lượng thông tin truyền tải

Ưu tiên *thông tin truyền tới khán giả*, không phải chi tiết thẩm mỹ (căn lề, editor đẹp…).

| Khái niệm | Câu hỏi | Áp vào demo |
|---|---|---|
| Information Architecture | Có màn nào, mỗi màn để làm gì, đi giữa chúng ra sao? | Chọn 3–4 core view; còn lại là râu ria |
| Information density (data-ink ratio) | Mỗi vùng màn hình chở bao nhiêu thông tin có ích? | Một khung nhìn nói nhiều điều cùng lúc, không phải danh sách chữ |
| Visual hierarchy | Khán giả thấy gì trong 5–10 giây đầu? | Ý chính của màn đọc được ngay |

**Phép thử 10 giây:** mỗi màn ghi ra *một câu hỏi* nó trả lời. Khán giả nhìn 10 giây có trả lời được không?
Không → thiết kế lại hoặc hạ xuống râu ria.

**Nguyên tắc chọn component: hình dạng dữ liệu → hình thức hiển thị.**

| Hình dạng dữ liệu | Hình thức | Dữ liệu sẵn có |
|---|---|---|
| Thời gian | Timeline | 3.244 startYear / 2.671 endYear (CareerStation) |
| Quan hệ đa bước | Graph mở rộng được | cầu thủ → CLB → sân → tỉnh |
| Địa lý | Bản đồ | 195 cặp lat/long |
| Phân cấp lớp | Cây / treemap | 18 lớp `vio:` ⊑ `dbo:` |
| Khai báo vs suy luận | Bật/tắt lớp suy luận | 89K khai báo / 42K suy luận |
| Liên kết ngoài | Thẻ / cạnh LOD | 777 sameAs → DBpedia EN, 990 → Wikidata |
| Thay đổi hành chính | Trước/sau, mũi tên kế thừa | 50 successor/predecessor, 81 FormerProvince |

## 2. Hiện trạng qua phép thử 10 giây

| Màn VDB hiện tại | Câu hỏi nên trả lời | Thu được sau 10 giây | Đánh giá |
|---|---|---|---|
| Cây tài nguyên | Dataset cấu trúc thế nào, lớn cỡ nào? | Bức tường tên người | Mật độ thấp; cấu trúc lớp chìm |
| Tài nguyên | Thực thể là gì, nối tới đâu? | Rất nhiều, ngang hàng, cuộn 6 màn | Thiếu phân cấp; sự nghiệp (dữ liệu thời gian) bị hiện thành cây chữ |
| Đồ thị lân cận | Liên quan tới những gì? | 2 cột hộp quanh tâm | Chỉ 1 bước; không thấy chuỗi đa bước |
| Hỏi đáp | Hỏi tiếng Việt, graph trả lời được không? | Một đoạn văn | Mất phần chứng minh (câu trả lời đến từ đâu trên graph) |
| SPARQL | Có endpoint chuẩn không? | Editor + bảng | Đủ — râu ria hợp lệ |

Kết luận: backend không thiếu thông tin; **hình thức hiển thị không khớp hình dạng dữ liệu**.

## 3. Core views (nháp)

| # | View | Câu hỏi nó trả lời | Chứng minh yêu cầu đề | Thành phần chính |
|---|---|---|---|---|
| 1 | Tổng quan dataset | Graph chứa gì, lớn cỡ nào, suy luận thêm được bao nhiêu? | 1 Ontology, 3 RDF 4★ | ? |
| 2 | Thực thể | X là ai/cái gì, cuộc đời và quan hệ ra sao? | 3 RDF, 4 Link DBpedia | timeline + graph mở rộng + LOD |
| 3 | Hỏi đáp có bằng chứng | Hỏi tiếng Việt → SPARQL → trả lời → đường đi trên graph | 5 SPARQL/interface | ? |
| 4 | (tuỳ chọn) Bản đồ / sáp nhập tỉnh | Ontology mô hình được thay đổi theo thời gian không? | 1, 3 | ? |

Râu ria (có là đủ, không cần wow): SPARQL editor, cây tài nguyên đầy đủ, tải RDF, content negotiation.

## 4. Quyết định

| # | Vấn đề | Quyết định | Ngày |
|---|---|---|---|
| D1 | Vai trò VinaLKG | Chỉ là reference/cảm hứng, không port code | 2026-10-07 |
| D2 | Vị trí UI | Đứng độc lập trong repo nhóm (thư mục riêng + API JSON mỏng), không đụng crawl/kg | 2026-10-07 |
| D3 | Tiêu chí thiết kế | Lượng thông tin truyền tải > chi tiết thẩm mỹ | 2026-10-07 |

## 5. Câu hỏi mở

1. Danh sách core views ở §3 đã đúng/đủ chưa? Thông tin cụ thể của từng view?
2. Khán giả/tiêu chí chấm: giảng viên theo 5 yêu cầu đề, hay cả lớp?
3. Câu chuyện xuyên suốt: một nhân vật (Công Phượng) hay sáp nhập tỉnh?
4. Demo có cần chạy offline / không LLM (cache câu trả lời)?
