# DEMO — Kịch bản v3 (~3:40, chạy live)

**Luận điểm:** "Từ 990 bài Wikipedia tiếng Việt thành đồ thị máy hiểu, tự suy luận và nối ra DBpedia toàn cầu."
**Sợi chỉ:** Công Phượng (11 chặng, 4 nước; HAGL: 77 dòng có suy luận / 0 dòng chỉ khai báo).

## Màn I — Từ bài viết đến Linked Data (~1:30): chứng minh 5 yêu cầu đề

| Beat | YC | Thao tác | Câu chốt | s |
|---|---|---|---|---|
| Bản thiết kế | #1 | Tổng quan → cây lớp | "18 lớp `vio:` căn theo DBpedia: `vio:FootballPlayer` cũng là `dbo:SoccerPlayer`" | 20 |
| Truy nguồn + Định danh | #2, #3 | Công Phượng → chip *Linked Data (Turtle)*: chỉ URL `/resource/…` → `/data/….ttl`, rồi dòng `prov:wasDerivedFrom` | "Mỗi thực thể một URI, gõ vào trả RDF: 4 sao. Và truy về đúng phiên bản bài viwiki đã đọc (`oldid`)" | 30 |
| Cầu nối | #4 | Quay lại → chip *DBpedia EN* | "777 liên kết, lấy từ sitelink Wikidata, không đoán theo tên" | 20 |
| Cửa truy vấn | #5 | Tab SPARQL: chỉ dòng `curl` → chọn mẫu *2 · Quá trình thi đấu Công Phượng* → Chạy | "Endpoint SPARQL 1.1 chuẩn: trình duyệt hay terminal (`curl`) đều gọi được" | 20 |

## Màn II — Graph biết nhiều hơn những gì được viết (~2:10): ontology suy ra và bắt lỗi

| Beat | Thao tác | Câu chốt | Vì sao | s |
|---|---|---|---|---|
| Hành trình | Timeline Công Phượng | "Mỗi chặng là một nút: năm, số trận, bàn, cho mượn" | Dữ liệu thời gian mà văn bản không có | 20 |
| Suy luận lộ diện | Tắt → bật *Hiện suy luận* | "Nhãn *Cầu thủ đội tuyển*, cạnh nét đứt tím: không ai nhập, máy suy ra" | **Gài** cho beat ★ | 25 |
| Bắt lỗi | Cùng trang, thẻ *Nếu crawler đọc nhầm infobox?* → *sân nhà → Sân Pleiku* (đồ thị đỏ: Người ⊥ Tổ chức) → rồi *tỉnh nơi sinh → Gia Lai* (xanh) | "Cầu thủ không thể có sân nhà: máy suy ra Công Phượng là Tổ chức, trái tiên đề Người ⊥ Tổ chức. Còn Gia Lai thì sai sự thật nhưng đúng loại → không bắt" | Ontology không chỉ suy ra mà còn **phát hiện** dữ liệu vô lý (YC #1) | 25 |
| Lứa HAGL | Đồ thị: bấm nút HAGL | "Từ một cầu thủ sang cả lứa HAGL, rồi CLB → sân → tỉnh" | Quan hệ đa bước | 15 |
| ★ Câu hỏi chưa ai viết sẵn | Hỏi đáp: preset "Cầu thủ nào từng chơi cho Hoàng Anh Gia Lai?" | "SPARQL chạy thật: **77 dòng**. Chỉ khai báo: **0 dòng**" | **Thu hoạch**; hiện SPARQL = LLM không bịa | 35 |
| Chốt | — | Câu luận điểm | Kết bằng luận điểm | 10 |

**Lố giờ, cắt theo thứ tự:** Lứa HAGL → Hành trình → bỏ preset đối chứng Gia Lai. Không cắt Màn I.

## Chuẩn bị

- [x] Câu HAGL đã có trong `ui/api/demo_cache.json` (77 / 0 dòng).
- [ ] Server `ui.api` đã chạy ở :8000.
- [ ] Mở sẵn tab; chụp sẵn trang DBpedia EN (phòng mất mạng).
- [ ] Không bấm CLB nước ngoài (Mito, Sint-Truiden, Incheon, Yokohama): không có sameAs.

## Đạn cho Q&A

- **sameAs có nhầm không?** Tìm "Quang Hải" → 2 người (1985, 1997), mỗi người trỏ đúng trang DBpedia của mình.
- **CLB Đồng Nai sao sân ở Bình Phước?** Bình Phước là `vio:FormerProvince`, `successor` Đồng Nai (sáp nhập 2025).
- **Thử triple khác?** Thẻ *Nếu crawler đọc nhầm infobox?* → *Tự nhập triple* (vd. `Câu_lạc_bộ_bóng_đá_Hoàng_Anh_Gia_Lai rdf:type vio:Province`).
- **Toàn graph có mâu thuẫn không?** Tab SPARQL, mẫu *7 · Kiểm tra mâu thuẫn* → 0 (khớp ô "0 lỗi kiểm tra").
- **Không có LLM?** Nói trước: câu demo lấy SPARQL từ cache, nhưng truy vấn vẫn chạy thật trên graph.
- **Sáp nhập tỉnh mô hình thế nào?** Tab Bản đồ: bật *Trước 2025* ↔ *Sau sáp nhập*. Ranh giới 34 tỉnh không tải từ ngoài mà
  gộp 63 tỉnh cũ theo `vio:successor` trong graph; bấm Gia Lai → "gộp từ Bình Định…". Tô màu: Nghệ An 58 cầu thủ quê.
