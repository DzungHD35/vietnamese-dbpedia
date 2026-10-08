# Chú thích thuyết trình — Vietnamese DBpedia (20 slide)

Mỗi slide gồm: **Nói** (mạch nói), **Số phải trúng** (con số cần đọc chính xác), và **Nếu bị hỏi**
ở các slide then chốt. Số slide khớp với số ở góc dưới phải. Mọi con số lấy từ report (`report/`),
tính lại được bằng `python report/report_numbers.py`.

## Bốn phần, bốn người

Bộ slide chia thành bốn phần nối tiếp, trùng với bốn tầng kiến trúc ở slide 4. Mỗi người trình bày
một đoạn liền mạch và trả lời câu hỏi về phần của mình.

| Phần | Người trình bày | Slide | Tầng kiến trúc | Thời lượng |
|---|---|---|---|---|
| 1. Đề tài và thu thập dữ liệu | Ha Thi Kim Phung | 1–5 | (1) Collection | 1:05 |
| 2. Ontology và chuyển đổi sang RDF 4 sao | Bui Duc Phan Hoang | 6–9 | (2) Semantics | 1:15 |
| 3. Kiểm tra, suy luận và Linked Data | Do Hoang Dung | 10–14 | (3) Post-processing | 1:20 |
| 4. Truy vấn, hỏi đáp, đánh giá và kết luận | Do Ngoc Trung | 15–20 | (4) Server | 1:15 |
| | | | **Tổng** | **≈ 4:55** |

Mạch tổng: đề bài → miền dữ liệu → kiến trúc → thu thập → đồ thị RDFS và tiên đề → trích infobox →
chuyển sang 4 sao → một thực thể → kiểm tra, suy luận → liên kết DBpedia, URI, 5 sao → giao diện, hỏi
đáp → đánh giá, hạn chế → kết luận. Bốn chỗ dừng lâu: **slide 7** (tiên đề OWL), **slide 9** (4 sao),
**slide 10** (một thực thể), **slide 12** (liên kết DBpedia).

## Kịch bản video 3–5 phút

Tổng khoảng 4 phút 55 giây, sát giới hạn 5 phút. Mỗi người có thể ghi âm phần mình riêng rồi ghép.
Nếu bị quá 5 phút, chỉ chiếu slide 5 và 13 mà không nói (bớt khoảng 20 giây).

| Slide | Người | Thời lượng | Slide | Người | Thời lượng |
|---|---|---|---|---|---|
| 1 Title | Phung | 0:10 | 11 Validation, reasoning | Dung | 0:20 |
| 2 Assignment | Phung | 0:20 | 12 Linking | Dung | 0:20 |
| 3 Why this domain | Phung | 0:10 | 13 Dereferenceable IRIs | Dung | 0:10 |
| 4 Architecture | Phung | 0:15 | 14 Five stars | Dung | 0:10 |
| 5 Collection | Phung | 0:10 | 15 Web interface | Trung | 0:20 |
| 6 RDFS graph | Hoang | 0:20 | 16 Question answering | Trung | 0:20 |
| 7 OWL axioms | Hoang | 0:20 | 17 Evaluation | Trung | 0:10 |
| 8 Wikitext to RDF | Hoang | 0:15 | 18 Limitations | Trung | 0:10 |
| 9 Transform to 4★ | Hoang | 0:20 | 19 Conclusion | Trung | 0:10 |
| 10 One entity | Dung | 0:20 | 20 Thank you | Trung | 0:05 |

**Demo trong video (tuỳ chọn, phần của Trung):** ở slide 15, có thể chuyển sang quay màn hình 20–30
giây: `python -m vidbpedia serve`, mở `http://127.0.0.1:7860/resource/Nguyễn_Công_Phượng` trong trình
duyệt (trình duyệt tự mã hoá dấu), rồi sang tab SPARQL bấm "Chạy truy vấn". Khi có demo thì rút phần
nói của slide 16–18 để vẫn dưới 5 phút. Tab Hỏi đáp cần key LLM trong `.env`; chưa có key thì đừng
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
**Nói:** Miền được chọn là bóng đá Việt Nam, tỉnh thành và đại học, vì các thực thể trỏ lẫn nhau:
cầu thủ, câu lạc bộ, sân nhà, tỉnh. 97% bài có infobox, 78% có bài tiếng Anh để liên kết.
**Số phải trúng:** 611 cầu thủ, 110 tỉnh (34 hiện hành); 97%, 78%.
**Nếu bị hỏi** "sao không chọn thực thể theo thể loại Wikipedia?": thể loại do người viết gán, không
nhất quán; Wikidata cho lớp (`P31`) và quốc gia (`Q881`) chính xác hơn.

### Slide 4 — Architecture
**Nói:** Hệ thống có bốn tầng, mỗi bước một lệnh, và bốn phần trình bày đi theo đúng bốn tầng này.
Chỉ tầng thu thập gọi mạng; mọi thứ được cache nên dựng lại được mà không cần Internet.
**Số phải trúng:** 6 lệnh: seeds, enrich, ontology, build, postprocess, serve.

### Slide 5 — Collecting Entities and Articles
**Nói:** Mỗi lớp là một truy vấn Wikidata; đây là truy vấn cho cầu thủ. Sau đó lấy bài viết qua
MediaWiki API: abstract, thể loại, redirect và tham số infobox. Request được giãn cách và cache lại.
**Số phải trúng:** 2.588 đích liên kết trong infobox, 71 trang định hướng.
**Nếu bị hỏi** "sao không dùng bản dump của Wikipedia?": với 990 bài, API nhanh hơn và chỉ lấy đúng
phần cần; cache SQLite và cờ `--offline` cho kết quả lặp lại được như dùng dump.

## Phần 2 — Bui Duc Phan Hoang: ontology và chuyển đổi sang RDF 4 sao

### Slide 6 — Ontology vio: as an RDFS Graph
**Nói:** Mình là Hoang, phụ trách tầng ngữ nghĩa. Đây là một phần ontology vẽ dạng đồ thị RDFS. Phía
trên đường kẻ là schema: lớp là `rdfs:Class`, thuộc tính là `rdf:Property`, nối bằng `subClassOf` và
`subPropertyOf`; `careerStation` có domain là cầu thủ, range là chặng thi đấu. Phía dưới là dữ liệu:
Công Phượng có chặng thi đấu ở Hoàng Anh Gia Lai, quê Nghệ An. Nét đứt là triple RDFS suy ra: Công
Phượng cũng là `dbo:Person`.
**Số phải trúng:** toàn bộ ontology có 18 lớp, 54 thuộc tính; lớp nào cũng là lớp con của một lớp DBpedia.
**Nếu bị hỏi** "vì sao Công Phượng là `dbo:Person`?": luật rdfs9, kiểu được truyền lên theo
`subClassOf`: FootballPlayer ⊑ Athlete ⊑ Person ⊑ dbo:Person.

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
CLB, số trận, bàn thắng thành 3.382 chặng thi đấu.
**Số phải trúng:** 3.382 chặng của 601 cầu thủ; 24.605 triple infobox thô.
**Nếu bị hỏi** "khi Wikidata và infobox khác nhau thì lấy bên nào?": bảng `PRECEDENCE` quyết định;
Wikidata cho ngày, chiều cao, dân số, sức chứa; infobox cho số áo, số sinh viên, khẩu hiệu.

### Slide 9 — Transform to 4★: One Infobox, Before and After ← DỪNG
**Nói:** Đây là bước chuyển sang 4 sao trên một infobox thật. Phía trên là wikitext: máy đọc được
nhưng chỉ là chữ, không có URI. Phía dưới là RDF: mỗi thứ có một IRI, kể cả chặng cho mượn ở Mito;
giá trị có kiểu, như ngày sinh là `xsd:date`; dấu "mượn" thành `onLoan true`; còn chiều cao lấy theo
Wikidata là 1,68 thay vì 1,69 của infobox.
**Số phải trúng:** 21/01/1995; Mito HollyHock 2016, 5 trận, 0 bàn, cho mượn.
**Nếu bị hỏi** "3 sao khác 4 sao ở đâu?": 3 sao là định dạng mở như CSV hay JSON; 4 sao là dùng URI
để định danh từng thứ, để người khác trỏ tới và tra được (303 ở slide 13).

## Phần 3 — Do Hoang Dung: kiểm tra, suy luận và Linked Data

### Slide 10 — One Entity, End to End ← DỪNG
**Nói:** Mình là Dung, phụ trách tầng hậu xử lý. Đây là Nguyễn Công Phượng. Nét xám là dữ liệu khai
báo: hai chặng thi đấu, đội, sân nhà Pleiku, tỉnh Gia Lai. Nét đỏ đứt là phần suy luận: các lớp
DBpedia, cạnh `playedFor`, và Mito HollyHock được xếp vào lớp CLB. Nét xanh là liên kết ra ngoài.
**Số phải trúng:** 11 chặng thi đấu; 2015–2023, 103 trận, 36 bàn ở Hoàng Anh Gia Lai.

### Slide 11 — Validation and OWL 2 RL Reasoning
**Nói:** Trước khi xuất, tám hàm kiểm tra chạy trên dữ liệu: lần dựng cuối không có lỗi nào. Suy
luận thêm 41.730 triple trong 117 giây, nhờ đó truy vấn bằng từ vựng DBpedia mới có kết quả. Suy
luận còn bắt được hai lỗi mô hình hoá mà nhóm đã sửa.
**Số phải trúng:** 0 lỗi, 0 cảnh báo; 47 test; +41.730 triple.
**Nếu bị hỏi** về hai lỗi: (1) đội tuyển bị suy ra là CLB vì domain của `ground` đặt sai; (2) khai báo
`tenant` là nghịch đảo của `ground` làm sai sân nhà, vì ô "bên thuê" liệt kê mọi đội từng dùng sân.
**Nếu bị hỏi** "sao bỏ `owl:sameAs` và functional khỏi reasoner?": OWL 2 RL sinh `x sameAs x` cho mọi
nút và gộp các thực thể có cùng giá trị functional; functional được kiểm tra riêng ở bước validation.

### Slide 12 — Linking to English DBpedia ← DỪNG
**Nói:** Liên kết lấy từ sitelink tiếng Anh của chính item Wikidata, không ghép theo tên vì tên Việt
trùng nhiều. Có 777 liên kết sang DBpedia và 990 sang Wikidata. Nhóm kiểm tra cả 777 trên DBpedia
thật: 733 trỏ đúng bài viết, 44 còn lại lệch vì DBpedia lấy dữ liệu từ bản Wikipedia cũ hơn.
**Số phải trúng:** 777 / 990; 733 (94,3%); 12 đổi hướng, 32 chưa có.
**Nếu bị hỏi** "sửa 44 liên kết thế nào?": 12 cái đi theo `dbo:wikiPageRedirects` là sửa được; 32 cái
phải chờ bản DBpedia mới hoặc kiểm lại sau mỗi lần phát hành.

### Slide 13 — Dereferenceable IRIs
**Nói:** Mỗi IRI tra được như DBpedia: máy chủ trả 303, chuyển trình duyệt tới trang HTML và chuyển
client RDF tới Turtle, N-Triples, JSON-LD hoặc RDF/XML theo header `Accept`.

### Slide 14 — Five Stars, Checked
**Nói:** Vậy dataset đạt đủ năm sao: giấy phép mở, máy đọc được, định dạng mở, URI cho mọi thứ, và
liên kết sang DBpedia, Wikidata. Lưu ý duy nhất: nhóm không sở hữu tên miền vi.dbpedia.org, nên IRI
chỉ mở được qua máy chủ của dự án.
**Nếu bị hỏi** "vậy sao đã đủ 4 sao?": 4 sao đòi hỏi định danh bằng URI và tra được; IRI của nhóm
dereference đúng chuẩn (303, content negotiation) trên máy chủ dự án; đưa lên Internet thật thì cần
một tên miền của nhóm hoặc dịch vụ như w3id.org.

## Phần 4 — Do Ngoc Trung: truy vấn, hỏi đáp, đánh giá và kết luận

### Slide 15 — Web Interface
**Nói:** Mình là Trung, phụ trách tầng máy chủ. Giao diện có bốn tab. Bên trái là trang tài nguyên
giống dbpedia.org/page, đánh dấu lớp khai báo và lớp suy luận. Bên phải là tab SPARQL, đang đếm thực
thể theo lớp DBpedia, toàn bộ có nhờ suy luận.
*(Nếu demo: chuyển sang quay màn hình ở đây, xem phần "Demo trong video" ở trên.)*

### Slide 16 — Question Answering
**Nói:** Tab Hỏi đáp cho phép hỏi bằng tiếng Việt. Mô hình ngôn ngữ đọc tóm tắt schema, viết SPARQL;
hệ thống chỉ chấp nhận SELECT hoặc ASK, chạy trên graph, rồi để mô hình trả lời từ kết quả. Nếu truy
vấn lỗi hoặc rỗng, mô hình được sửa một lần.
**Số phải trúng:** 10,7 giây xuống 0,27 giây nhờ subquery.
**Nếu bị hỏi** "LLM viết sai truy vấn thì sao?": truy vấn được parse trước khi chạy, chỉ SELECT/ASK;
lỗi hoặc rỗng thì gửi lại cho mô hình sửa một lần; SPARQL mode cho người dùng xem truy vấn thật.

### Slide 17 — Evaluation
**Nói:** Graph trả lời đúng các câu hỏi năng lực, ví dụ còn 34 tỉnh thành, Nghệ An nhiều cầu thủ
nhất với 58 người. Mỗi câu là một test tự động.
**Số phải trúng:** 34; Nghệ An 58; 11 đội của Công Phượng.

### Slide 18 — Limitations and Future Work
**Nói:** Hạn chế chính: mới một miền, 44 liên kết cần sửa, và chưa có endpoint `/sparql` chuẩn. Hướng
tiếp theo là thêm endpoint đó, thêm lớp mới và đo độ chính xác của tab Hỏi đáp.
**Nếu bị hỏi** "SPARQL endpoint ở đâu?": hiện truy vấn qua tab SPARQL trên giao diện; muốn có endpoint
HTTP chuẩn thì nạp dump vào Virtuoso đã khai báo sẵn trong `docker-compose.yml`, cổng 8890.

### Slide 19 — Conclusion
**Nói:** Tóm lại, nhóm đã xây dựng một DBpedia tiếng Việt năm sao cho ba miền dữ liệu. Suy luận OWL là
thứ giúp dữ liệu dùng chung được với DBpedia. Mã nguồn và dữ liệu có trên GitHub.

### Slide 20 — Thank you
**Nói:** Cảm ơn thầy và các bạn đã lắng nghe.
