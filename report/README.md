# report/

Nguồn LaTeX của báo cáo môn Semantic Web, đề tài 2: *Build a DBpedia version for Vietnamese
language*. Viết bằng tiếng Anh, theo cùng khuôn với báo cáo luận văn (SSI-DDI): `main.tex` chỉ chứa
thứ tự `\input`, `preamble.tex` chứa package và trang tiêu đề, mỗi chương một file trong `sections/`.

## Build

Cần MiKTeX hoặc TeX Live có `latexmk`:

```
make            # -> main.pdf
make watch      # build lại mỗi khi lưu
make clean      # xoá file phụ, giữ PDF
```

Hoặc chạy thẳng `latexmk -pdf main.tex`. Không có `make` thì chạy `latexmk -c` để dọn file phụ.

Tiếng Việt chạy được với pdflatex nhờ encoding T5 đặt làm mặc định trong `preamble.tex`. Khối mã dùng
`fancyvrb` (`Verbatim`), không dùng `listings`, vì `listings` không đọc được ký tự UTF-8 có dấu.

## Cấu trúc

```
main.tex            thứ tự \input
preamble.tex        package, macro \term{} \fillin{} \apx, màu, trang tiêu đề
references.bib      tài liệu tham khảo (IEEEtran), mục nào cũng được trích
report_numbers.py   in mọi con số mà report trích, tính từ data/
sections/
  00-abstract.tex      tóm tắt và từ khoá
  01-introduction.tex  bối cảnh, phạm vi, đóng góp, bảng đối chiếu 5 yêu cầu của đề
  02-related-work.tex  DBpedia, Linked Data và 5 sao, Wikidata, OWL 2 RL, KG-QA
  03-method.tex        kiến trúc, ontology, thu thập, chuyển sang RDF, liên kết, kiểm tra và suy luận
  04-publishing.tex    máy chủ, URI dereference được, giao diện, hỏi đáp, SPARQL endpoint
  05-evaluation.tex    thống kê, độ phủ, tác động của suy luận, test, kiểm tra liên kết DBpedia, CQ, 5 sao
  06-discussion.tex    quyết định thiết kế và hạn chế
  07-conclusion.tex
figures/            ảnh chụp giao diện (ui_resource.png, ui_sparql.png) và hình RDFS (rdfs_graph.tex)
```

Ba hình sơ đồ vẽ bằng TikZ:
- kiến trúc và ví dụ đồ thị một thực thể: ngay trong `03-method.tex`;
- đồ thị RDFS (Hình 2): `figures/rdfs_graph.tex`, vẽ theo kiểu bài giảng (hình elip, `rdfs:Class` và
  `rdf:Property` ở trên, đường kẻ ngang tách schema với dữ liệu) cho một phần ontology và ví dụ Công
  Phượng. Dùng chung với slide 6; màu đặt trong `preamble.tex` của từng thư mục, cỡ chữ trong hình
  là cỡ tuyệt đối nên hai nơi hiển thị giống nhau. Cây lớp đầy đủ kèm số thực thể nằm ở Bảng 3.

## Số liệu

Mọi con số trong report lấy từ dataset hiện tại. Sau khi chạy lại pipeline, chạy:

```
python report/report_numbers.py             # từ thư mục gốc của repo
python report/report_numbers.py --dbpedia   # thêm kiểm tra owl:sameAs trên dbpedia.org (cần mạng)
```

rồi so với các bảng trong `sections/`. Mỗi nhóm số trong output ghi nhãn bảng tương ứng
(`tab:dataset`, `tab:reasoning`, `tab:links`…). Phần kiểm tra liên kết in luôn danh sách 12 liên kết
trỏ tới trang đổi hướng và 32 liên kết chưa có trên DBpedia.

Số đo thời gian chỉ đúng với máy đã chạy: suy luận 117 s (lấy từ `vietnamese_dbpedia_stats.json`),
và truy vấn tìm theo tên viết phẳng 10,7 s so với 0,27 s khi đặt trong subquery.

## Ảnh chụp giao diện

Chụp bằng Playwright (Chrome headless) trên `python -m vidbpedia serve`, khung nhìn rộng 1000 px, độ
phân giải 2x. Ảnh trang tài nguyên ẩn phần tóm tắt và ảnh cầu thủ cho gọn; chú thích hình đã ghi rõ.
Ảnh tab SPARQL chạy truy vấn mẫu đầu tiên ("Đếm theo lớp DBpedia"), được xuống dòng ngắn lại cho vừa
khung, nội dung truy vấn không đổi.

## Trạng thái

Build sạch: 15 trang, đúng bằng giới hạn của đề (≤ 15), 0 lỗi LaTeX, 0 tham chiếu hay trích dẫn
chưa giải, 0 cảnh báo BibTeX, 0 dòng tràn lề. Thêm nội dung thì phải bớt chỗ khác: trang 14 chỉ có
mục Conclusion, trang 15 là tài liệu tham khảo.

## Trước khi nộp

- Trang tiêu đề đã đủ: 4 thành viên nhóm 23 và giảng viên Dr. Do Ba Lam (`preamble.tex`). Macro
  `\fillin{}` vẫn còn trong preamble nếu cần chỗ trống chờ điền.
- Nếu đổi ngày nộp thì sửa `\date{}` trong `preamble.tex`.
- Nếu thêm SPARQL endpoint chuẩn (`/sparql`) vào máy chủ thì sửa mục 4.4 và gạch "Serving" trong
  mục Limitations (`06-discussion.tex`).
