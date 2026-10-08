# Core views đề xuất cho UI demo (nháp, 2026-10-07)

Trạng thái: đã thống nhất hướng chung, chưa chốt B1 (khán giả, thời lượng, yêu cầu 2 của đề).
Cập nhật 2026-10-08: core views, stack, câu chuyện demo đã chốt (CORE.md D4–D7); kế hoạch code ở `../PLAN.md`.
Bản đầy đủ: Claude Doc "UI Design: Vietnamese DBpedia demo" (7 mục, checklist B1–B8).

## Hướng
Một web app, 3 màn chính đi thành một câu chuyện: tổng quan → đào vào một thực thể → đặt câu hỏi.
Ít màn hơn VinaLKG, nhưng mỗi màn cho thấy phần "semantic" của đồ án (ontology, suy luận, sameAs, SPARQL).

## Màn chính
1. **Tổng quan dataset**: màn đầu tiên. Số liệu chính: 131K triple, 18 lớp `vio:`, 41.730 triple suy luận,
   777 sameAs → DBpedia EN, 990 → Wikidata. Bấm vào con số ra chi tiết.
2. **Trang thực thể** (quan trọng nhất): tìm một thực thể (cầu thủ / tỉnh / trường) → thông tin, đồ thị lân cận,
   link DBpedia EN/Wikidata. Triple **khai báo** và **suy luận** tô khác màu (dữ liệu có sẵn ở `data/parts/`).
3. **Hỏi đáp có bằng chứng**: hỏi tiếng Việt → hiện SPARQL sinh ra, kết quả, thực thể làm bằng chứng;
   bấm thực thể thì nhảy sang màn 2.

## Màn tuỳ chọn
4. **Bản đồ tỉnh thành / sáp nhập**: 195 toạ độ, 81 FormerProvince. Chỉ làm nếu còn thời gian.

## Râu ria (có link, không vào kịch bản)
SPARQL editor, cổng Linked Data (dereference, tải RDF, VoID), trang ontology, mapping infobox, validation.

## Không làm
Quản trị triplestore kiểu Fuseki UI (VDB không dùng Fuseki).

## Lý do chọn
- Câu chuyện 3 bước hiểu được trong vài phút (phép thử 10 giây của CORE.md).
- Tách khai báo/suy luận bằng màu là cách rẻ nhất để chứng minh OWL 2 RL có tác dụng.

## Còn mở (cần trả lời ở B1)
- Ai xem, demo bao lâu, ai bấm máy?
- Yêu cầu 2 của đề là gì? (nếu là "trích xuất từ Wikipedia" thì mapping infobox lên thành core view)
- `/sparql`, VoID, dump: đặt trong API của UI mới hay nhờ team thêm?
- Hỏi đáp có cần stream không?

## Prototype
Claude Design canvas: https://claude.ai/artifact/Mfi7GfYUmKiZKSHTL7jgYS (riêng tư, chưa share).
3 artboard bấm qua lại được: Tổng quan → Thực thể (Đặng Quang Huy) → Hỏi đáp ("Cầu thủ nào từng chơi cho Than Quảng Ninh?").
Dữ liệu mẫu lấy từ dataset thật (`data/parts/`, `vietnamese_dbpedia_stats.json`), chỉ để xem bố cục, chưa nối backend.
Điểm nhấn: `vio:playedFor` có 0 triple khai báo, 2.772 triple suy luận (property chain `careerStation ∘ team`),
nên cùng một câu hỏi trả 39 dòng với suy luận và 0 dòng nếu chỉ dùng triple khai báo.
