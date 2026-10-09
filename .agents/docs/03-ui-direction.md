# Hướng UI mới — chi tiết bổ trợ

Tiêu chí, core views, quyết định: xem `../CORE.md`. File này chỉ giữ chi tiết bổ trợ.

## Dữ liệu sẵn có (đếm trong data/vietnamese_dbpedia.nt, 2026-10-07)
- 3.244 `vio:startYear` / 2.671 `endYear`, 2.415 `goals`, 2.386 `appearances` trên CareerStation
  (1.972 ClubStation, 896 NationalTeamStation, 533 YouthStation); 282 `onLoan`.
- 195 cặp `vio:latitude/longitude`.
- 50 `successor/predecessor`, 42 `dissolutionYear`, 81 `FormerProvince`.
- 544 `dbo:thumbnail`; 580 `birthDate`; 541 `height`; 87 `population`/`area`; 226 `foundingYear`.
- Khai báo 88.898 / suy luận 41.730 / ontology 549 triple.
- 777 `owl:sameAs` → DBpedia EN, 990 → Wikidata.

## Ràng buộc kỹ thuật
- UI mới ở thư mục riêng, gọi API JSON mỏng bọc `ResourceView` / `ResourceTree` / `SparqlBasedKGRAG`;
  giữ nguyên Gradio của team.
- Không hard-code danh sách lớp nếu ontology có thể dẫn dắt (team còn mở rộng ontology).
- Nạp graph rdflib ~1 phút lúc khởi động; truy vấn trong RAM.
