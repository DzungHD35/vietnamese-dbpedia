# slides/

Bộ slide Beamer cho báo cáo môn Semantic Web, đề tài 2: *Build a DBpedia version for Vietnamese
language*. Cùng khuôn với slide luận văn (SSI-DDI): theme Madrid, bảng màu đỏ HUST, logo HUST ở góc
dưới trái và số trang ở góc dưới phải, tỉ lệ 4:3. Slide viết tiếng Anh, ghi chú thuyết trình viết
tiếng Việt. Có 20 slide.

## Build

```
latexmk -pdf main.tex     # -> main.pdf   (hoặc `make` nếu máy có make)
python make_pptx.py       # -> Vietnamese-DBpedia-slides.pptx, từ main.pdf + SPEAKER_NOTES.md
latexmk -c                # dọn file phụ, giữ PDF
```

`make_pptx.py` biến mỗi trang PDF thành một ảnh tràn khung (300 dpi, 4:3) và chép mục
`### Slide N` tương ứng của `SPEAKER_NOTES.md` vào phần ghi chú, để xem ở Presenter View. Cần
python-pptx và PyMuPDF (có sẵn ở python base của anaconda). Sửa PDF hay ghi chú thì chạy lại script,
và giữ số slide trong `SPEAKER_NOTES.md` khớp với bộ slide; script dừng nếu có ghi chú trỏ quá slide cuối.

Bản PPTX là ảnh, không sửa chữ trong PowerPoint được. Muốn sửa thì sửa LaTeX rồi build lại.

## Cấu trúc

```
main.tex                  thứ tự \input
preamble.tex              theme Madrid, màu HUST, chân trang, macro \term{} \hl{} \fillin{}
sections/                 4 phần theo 4 tầng kiến trúc, mỗi phần một người trình bày
  00-title.tex            (1)      Phần 1 · Phung: bìa HUST
  01-introduction.tex     (2–4)    Phần 1 · Phung: đề bài, miền dữ liệu, kiến trúc
  02-collection.tex       (5)      Phần 1 · Phung: thu thập từ Wikidata và MediaWiki API
  03-ontology.tex         (6–7)    Phần 2 · Hoang: đồ thị RDFS (schema + dữ liệu), tiên đề OWL
  04-extraction.tex       (8–9)    Phần 2 · Hoang: wikitext → RDF, chuyển sang 4 sao (trước/sau)
  05-reasoning.tex        (10–11)  Phần 3 · Dung: một thực thể, kiểm tra, suy luận OWL 2 RL
  06-linking.tex          (12–14)  Phần 3 · Dung: liên kết DBpedia, 303 + content negotiation, 5 sao
  07-interface.tex        (15–16)  Phần 4 · Trung: giao diện 4 tab, hỏi đáp bằng LLM
  08-evaluation.tex       (17–18)  Phần 4 · Trung: competency questions, hạn chế
  09-conclusion.tex       (19–20)  Phần 4 · Trung: kết luận, cảm ơn
SPEAKER_NOTES.md          người trình bày, nói gì ở từng slide, kịch bản và thời lượng video 3–5 phút
make_pptx.py              bản PowerPoint có ghi chú thuyết trình
figures/                  hình HUST và ảnh chụp giao diện
```

## Số liệu

Mọi con số trong slide lấy từ report (`../report/`). Sau khi chạy lại pipeline, chạy
`python report/report_numbers.py` ở thư mục gốc của repo, rồi sửa cả report lẫn slide.

## Hình

- `hust_closing.png`, `hust_emblem.png`: chép nguyên từ slide luận văn.
- `hust_title.png`: bìa HUST của slide luận văn, đã xoá bốn dòng chữ (tên luận văn, đề tài, học viên,
  giáo viên hướng dẫn) bằng các khung trắng; logo, vòng chấm và dòng "ONE LOVE. ONE FUTURE." giữ
  nguyên. Chữ trên bìa mới đặt bằng TikZ trong `00-title.tex`.
- `ui_resource.png`, `ui_sparql.png`: giống `../report/figures/`, chụp bằng Playwright trên
  `python -m vidbpedia serve` (xem `../report/README.md`).

Slide 6 dùng chung hình đồ thị RDFS (kiểu bài giảng) với report: `../report/figures/rdfs_graph.tex`,
màu HUST đặt trong `preamble.tex`. Vì vậy build slide cần có thư mục `report/` bên cạnh.

Các sơ đồ còn lại (kiến trúc, chuỗi quan hệ, một thực thể, luồng hỏi đáp) vẽ bằng TikZ ngay trong `sections/`:
khối nền hồng viền đỏ là các bước của hệ thống, khối xám là dữ liệu, khối viền đứt là hệ thống ngoài;
nét đỏ đứt là triple suy luận, nét xanh là liên kết sang dataset khác.

## Trước khi trình bày

- Bìa đã đủ: 4 thành viên nhóm 23 và giảng viên Dr. Do Ba Lam (`sections/00-title.tex`). Sửa bìa
  thì build lại PDF rồi chạy `make_pptx.py`.
- Đọc phần "Kịch bản video" trong `SPEAKER_NOTES.md`: tổng khoảng 4 phút 55 giây, sát giới hạn 5 phút.
- Nếu thêm endpoint `/sparql` vào máy chủ thì sửa slide 18 (`08-evaluation.tex`) và report mục 4.4.
