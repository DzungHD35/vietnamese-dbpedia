# Chú thích thuyết trình — Vietnamese DBpedia (19 slide)

Mỗi slide gồm: **Nói** (mạch nói), **Số phải trúng** (con số cần đọc chính xác), và **Nếu bị hỏi**
ở các slide then chốt. Số slide khớp với số ở góc dưới phải. Mọi con số lấy từ report (`report/`),
tính lại được bằng `python report/report_numbers.py`.

## Bốn phần, bốn người

Bộ slide chia thành bốn phần nối tiếp, trùng với bốn tầng kiến trúc ở slide 4. Mỗi người trình bày
một đoạn liền mạch và trả lời câu hỏi về phần của mình.

| Phần | Người trình bày | Slide | Tầng kiến trúc | Thời lượng |
|---|---|---|---|---|
| 1. Đề tài và thu thập dữ liệu | Ha Thi Kim Phung | 1–5 | (1) Collection | 1:15 |
| 2. Ontology và chuyển đổi sang RDF | Bui Duc Phan Hoang | 6–8, 18–19 | (2) Semantics | 0:55 + 0:15 |
| 3. Kiểm tra, suy luận và Linked Data | Do Hoang Dung | 9–13 | (3) Post-processing | 1:20 |
| 4. Truy vấn, hỏi đáp và đánh giá | Do Ngoc Trung | 14–17 | (4) Server | 1:10 |
| | | | **Tổng** | **≈ 4:55** |

Mạch tổng: đề bài → miền dữ liệu → kiến trúc → thu thập → ontology và tiên đề → trích infobox → một
thực thể → kiểm tra, suy luận → liên kết DBpedia, URI, 5 sao → giao diện, hỏi đáp → đánh giá, hạn chế
→ kết luận. Ba chỗ dừng lâu: **slide 7** (tiên đề OWL), **slide 9** (một thực thể), **slide 11**
(liên kết DBpedia).

## Kịch bản video 3–5 phút

Tổng khoảng 4 phút 55 giây, sát giới hạn 5 phút. Mỗi người có thể ghi âm phần mình riêng rồi ghép.
Nếu bị quá 5 phút, chỉ chiếu slide 5 và 12 mà không nói (bớt khoảng 20 giây).

| Slide | Người | Thời lượng | Slide | Người | Thời lượng |
|---|---|---|---|---|---|
| 1 Title | Phung | 0:10 | 11 Linking | Dung | 0:20 |
| 2 Assignment | Phung | 0:20 | 12 Dereferenceable IRIs | Dung | 0:10 |
| 3 Why this domain | Phung | 0:15 | 13 Five stars | Dung | 0:10 |
| 4 Architecture | Phung | 0:20 | 14 Web interface | Trung | 0:25 |
| 5 Collection | Phung | 0:10 | 15 Question answering | Trung | 0:20 |
| 6 Ontology | Hoang | 0:20 | 16 Evaluation | Trung | 0:15 |
| 7 OWL axioms | Hoang | 0:20 | 17 Limitations | Trung | 0:10 |
| 8 Wikitext to RDF | Hoang | 0:15 | 18 Conclusion | Hoang | 0:10 |
| 9 One entity | Dung | 0:20 | 19 Thank you | Hoang | 0:05 |
| 10 Validation, reasoning | Dung | 0:20 | | | |

**Demo trong video (tuỳ chọn, phần của Trung):** ở slide 14, có thể chuyển sang quay màn hình 20–30
giây: `python -m vidbpedia serve`, mở `http://127.0.0.1:7860/resource/Nguyễn_Công_Phượng` trong trình
duyệt (trình duyệt tự mã hoá dấu), rồi sang tab SPARQL bấm "Chạy truy vấn". Khi có demo thì rút phần
nói của slide 15–17 để vẫn dưới 5 phút. Tab Hỏi đáp cần key LLM trong `.env`; chưa có key thì đừng
demo tab đó.

---

## Phần 1 — Ha Thi Kim Phung: đề tài và thu thập dữ liệu

### Slide 1 — Title
**Nói:** Chào thầy và các bạn. Nhóm 23 trình bày đề tài 2 của môn Semantic Web: xây dựng một phiên bản
DBpedia cho tiếng Việt. Mình là Phung, mở đầu bằng đề bài và cách nhóm thu thập dữ liệu.

### Slide 2 — The Assignment and What We Built
**Nói:** Đề bài có năm yêu cầu, và bảng này cho thấy nhóm đáp ứng từng yêu cầu ra sao: ontology
`vio:` 18 lớp, 990 bài viết tiếng Việt, 131 nghìn triple RDF, 777 liên kết sang DBpedia tiếng Anh,
và giao diện truy vấn. Nhóm không trích toàn bộ Wikipedia tiếng Việt mà chọn một miền và làm sâu.
**Số phải trúng:** 18 lớp, 54 thuộc tính; 990 bài; 131.233 triple; 777 liên kết.

### Slide 3 — Why This Domain?
**Nói:** Miền được chọn là bóng đá Việt Nam, tỉnh thành và đại học. Các thực thể này trỏ lẫn nhau,
nên trả lời được câu hỏi nhiều bước: cầu thủ, chặng thi đấu, câu lạc bộ, sân nhà, rồi tới tỉnh.
97% bài có infobox và 78% có bài tiếng Anh để liên kết.
**Số phải trúng:** 611 cầu thủ, 110 tỉnh (34 hiện hành); 97%, 78%.
**Nếu bị hỏi** "sao không chọn thực thể theo thể loại Wikipedia?": thể loại do người viết gán, không
nhất quán; Wikidata cho lớp (`P31`) và quốc gia (`Q881`) chính xác hơn.

### Slide 4 — Architecture
**Nói:** Hệ thống có bốn tầng, mỗi bước là một lệnh, và bốn phần trình bày của nhóm đi theo đúng bốn
tầng này. Chỉ tầng thu thập gọi mạng; mọi phản hồi được cache và dữ liệu thô được commit, nên dựng
lại toàn bộ dataset mà không cần Internet, kết quả giống hệt nhau.
**Số phải trúng:** 6 lệnh: seeds, enrich, ontology, build, postprocess, serve.

### Slide 5 — Collecting Entities and Articles
**Nói:** Mỗi lớp là một truy vấn Wikidata; đây là truy vấn cho cầu thủ. Sau đó lấy bài viết qua
MediaWiki API: abstract, thể loại, redirect và tham số infobox. Request được giãn cách và cache lại.
**Số phải trúng:** 2.588 đích liên kết trong infobox, 71 trang định hướng.
**Nếu bị hỏi** "sao không dùng bản dump của Wikipedia?": với 990 bài, API nhanh hơn và chỉ lấy đúng
phần cần; cache SQLite và cờ `--offline` cho kết quả lặp lại được như dùng dump.

## Phần 2 — Bui Duc Phan Hoang: ontology và chuyển đổi sang RDF

### Slide 6 — Ontology vio:
**Nói:** Mình là Hoang, phụ trách tầng ngữ nghĩa. Ontology có 18 lớp chia bốn cây: người, tổ chức,
địa điểm và chặng thi đấu. Lớp nào cũng là lớp con của một lớp DBpedia. Dữ liệu khai báo chỉ dùng
`vio:`, còn sau suy luận thì có cả lớp DBpedia, ví dụ `dbo:Person` từ 0 lên 659.
**Số phải trúng:** 54 thuộc tính, 38 là thuộc tính con của `dbo:`; 659; 486.
**Nếu bị hỏi** "sao không dùng thẳng `dbo:`?": DBpedia không có những khái niệm nhóm cần, như tỉnh cũ
hay ba loại chặng thi đấu; lớp riêng cũng giữ cho tiên đề của nhóm chỉ ràng buộc dữ liệu của nhóm.

### Slide 7 — OWL Axioms Do the Work ← DỪNG
**Nói:** Các tiên đề OWL làm phần lớn công việc. Chuỗi thuộc tính `careerStation` rồi `team` cho
2.772 cạnh "từng thi đấu cho". Ràng buộc tồn tại xếp 486 cầu thủ vào lớp tuyển thủ quốc gia. Ràng
buộc "với mọi" gán lớp CLB cho 154 đội không phải seed. Tiên đề tách lớp còn giúp phát hiện hai lỗi
mô hình hoá.
**Số phải trúng:** 2.772; 486; 154; 2 lỗi.
**Nếu bị hỏi** "vì sao không đặt domain cho `latitude` hay `province`?": CLB và trường đại học cũng có
toạ độ và tỉnh; nếu domain là `Location` thì reasoner sẽ suy ra CLB là địa điểm, trái với tiên đề
tách lớp.

### Slide 8 — From Wikitext to RDF
**Nói:** Infobox đi qua bốn bước: diễn giải template, đọc giá trị kiểu Việt như "16.361,2" hay dấu
cho mượn, ánh xạ khoá sang `vio:`, rồi chọn Wikidata hay infobox cho từng thuộc tính. Các hàng năm,
CLB, số trận, bàn thắng thành 3.382 chặng thi đấu. Nhóm tái tạo đủ các dataset cơ bản của DBpedia.
**Số phải trúng:** 3.382 chặng của 601 cầu thủ; 24.605 triple infobox thô.
**Nếu bị hỏi** "khi Wikidata và infobox khác nhau thì lấy bên nào?": bảng `PRECEDENCE` quyết định;
Wikidata cho ngày, chiều cao, dân số, sức chứa; infobox cho số áo, số sinh viên, khẩu hiệu.

## Phần 3 — Do Hoang Dung: kiểm tra, suy luận và Linked Data

### Slide 9 — One Entity, End to End ← DỪNG
**Nói:** Mình là Dung, phụ trách tầng hậu xử lý. Đây là Nguyễn Công Phượng. Nét xám là dữ liệu khai
báo: hai chặng thi đấu, đội, sân nhà Pleiku, tỉnh Gia Lai. Nét đỏ đứt là phần suy luận: các lớp
DBpedia, cạnh `playedFor`, và Mito HollyHock được xếp vào lớp CLB. Nét xanh là liên kết ra ngoài.
**Số phải trúng:** 11 chặng thi đấu; 2015–2023, 103 trận, 36 bàn ở Hoàng Anh Gia Lai.

### Slide 10 — Validation and OWL 2 RL Reasoning
**Nói:** Trước khi xuất, tám hàm kiểm tra chạy trên dữ liệu: lần dựng cuối không có lỗi nào. Suy
luận thêm 41.730 triple trong 117 giây, nhờ đó truy vấn bằng từ vựng DBpedia mới có kết quả. Suy
luận còn bắt được hai lỗi mô hình hoá mà nhóm đã sửa.
**Số phải trúng:** 0 lỗi, 0 cảnh báo; 47 test; +41.730 triple.
**Nếu bị hỏi** về hai lỗi: (1) đội tuyển bị suy ra là CLB vì domain của `ground` đặt sai; (2) khai báo
`tenant` là nghịch đảo của `ground` làm sai sân nhà, vì ô "bên thuê" liệt kê mọi đội từng dùng sân.
**Nếu bị hỏi** "sao bỏ `owl:sameAs` và functional khỏi reasoner?": OWL 2 RL sinh `x sameAs x` cho mọi
nút và gộp các thực thể có cùng giá trị functional; functional được kiểm tra riêng ở bước validation.

### Slide 11 — Linking to English DBpedia ← DỪNG
**Nói:** Liên kết lấy từ sitelink tiếng Anh của chính item Wikidata, không ghép theo tên vì tên Việt
trùng nhiều. Có 777 liên kết sang DBpedia và 990 sang Wikidata. Nhóm kiểm tra cả 777 trên DBpedia
thật: 733 trỏ đúng bài viết, 44 còn lại lệch vì DBpedia lấy dữ liệu từ bản Wikipedia cũ hơn.
**Số phải trúng:** 777 / 990; 733 (94,3%); 12 đổi hướng, 32 chưa có.
**Nếu bị hỏi** "sửa 44 liên kết thế nào?": 12 cái đi theo `dbo:wikiPageRedirects` là sửa được; 32 cái
phải chờ bản DBpedia mới hoặc kiểm lại sau mỗi lần phát hành.

### Slide 12 — Dereferenceable IRIs
**Nói:** Mỗi IRI tra được như DBpedia: máy chủ trả 303, chuyển trình duyệt tới trang HTML và chuyển
client RDF tới Turtle, N-Triples, JSON-LD hoặc RDF/XML theo header `Accept`.

### Slide 13 — Five Stars, Checked
**Nói:** Vậy dataset đạt đủ năm sao: giấy phép mở, máy đọc được, định dạng mở, URI cho mọi thứ, và
liên kết sang DBpedia, Wikidata. Lưu ý duy nhất: nhóm không sở hữu tên miền vi.dbpedia.org, nên IRI
chỉ mở được qua máy chủ của dự án.
**Nếu bị hỏi** "4 sao khác 3 sao ở đâu?": 3 sao là định dạng mở; 4 sao là dùng URI để định danh từng
thứ, để người khác trỏ tới được.

## Phần 4 — Do Ngoc Trung: truy vấn, hỏi đáp và đánh giá

### Slide 14 — Web Interface
**Nói:** Mình là Trung, phụ trách tầng máy chủ. Giao diện có bốn tab. Bên trái là trang tài nguyên
giống dbpedia.org/page: lớp nào khai báo, lớp nào suy luận đều được đánh dấu. Bên phải là tab SPARQL,
đang đếm số thực thể theo lớp DBpedia, toàn bộ đều có nhờ suy luận.
*(Nếu demo: chuyển sang quay màn hình ở đây, xem phần "Demo trong video" ở trên.)*

### Slide 15 — Question Answering
**Nói:** Tab Hỏi đáp cho phép hỏi bằng tiếng Việt. Mô hình ngôn ngữ đọc tóm tắt schema, viết SPARQL;
hệ thống chỉ chấp nhận SELECT hoặc ASK, chạy trên graph, rồi để mô hình trả lời từ kết quả. Nếu truy
vấn lỗi hoặc rỗng, mô hình được sửa một lần.
**Số phải trúng:** 10,7 giây xuống 0,27 giây nhờ subquery.
**Nếu bị hỏi** "LLM viết sai truy vấn thì sao?": truy vấn được parse trước khi chạy, chỉ SELECT/ASK;
lỗi hoặc rỗng thì gửi lại cho mô hình sửa một lần; SPARQL mode cho người dùng xem truy vấn thật.

### Slide 16 — Evaluation
**Nói:** Graph trả lời đúng các câu hỏi năng lực, ví dụ: hiện còn 34 tỉnh thành, Nghệ An có nhiều cầu
thủ nhất với 58 người. Mỗi câu hỏi là một test tự động trên dữ liệu thật.
**Số phải trúng:** 34; Nghệ An 58; 11 đội của Công Phượng.

### Slide 17 — Limitations and Future Work
**Nói:** Hạn chế chính: mới một miền, 44 liên kết cần sửa, và chưa có endpoint `/sparql` chuẩn. Hướng
tiếp theo là thêm endpoint đó, thêm lớp mới và đo độ chính xác của tab Hỏi đáp.
**Nếu bị hỏi** "SPARQL endpoint ở đâu?": hiện truy vấn qua tab SPARQL trên giao diện; muốn có endpoint
HTTP chuẩn thì nạp dump vào Virtuoso đã khai báo sẵn trong `docker-compose.yml`, cổng 8890.

## Kết thúc — Bui Duc Phan Hoang

### Slide 18 — Conclusion
**Nói:** Tóm lại, nhóm đã xây dựng một DBpedia tiếng Việt năm sao cho ba miền dữ liệu. Suy luận OWL là
thứ giúp dữ liệu dùng chung được với DBpedia. Mã nguồn và dữ liệu có trên GitHub.

### Slide 19 — Thank you
**Nói:** Cảm ơn thầy và các bạn đã lắng nghe.
