"""Dữ liệu preset cho demo: thực thể nổi bật và câu hỏi mẫu (nơi duy nhất hard-code danh sách)."""

# local name của IRI vres:; id không resolve được sẽ bị bỏ qua ở /api/overview
FEATURED = [
    "Đặng_Quang_Huy",
    "Nguyễn_Công_Phượng",
    "Câu_lạc_bộ_bóng_đá_Than_Quảng_Ninh",
    "Sân_vận_động_Quốc_gia_Mỹ_Đình",
    "Hà_Nội",
    "Đại_học_Cần_Thơ",
]

DEMO_QUESTIONS = [
    "Cầu thủ nào từng chơi cho Hoàng Anh Gia Lai?",  # beat ★ của DEMO.md: 77 dòng có suy luận, 0 chỉ khai báo
    "Cầu thủ nào từng chơi cho Than Quảng Ninh?",  # khoe property chain: có suy luận vs chỉ khai báo
    "Quá trình thi đấu ở câu lạc bộ của Công Phượng?",
    "Câu lạc bộ nào có sân nhà ở Hà Nội?",  # nhiều bước CLB → sân → tỉnh
    "Tỉnh nào có nhiều cầu thủ quê quán nhất?",
    "Đại học Cần Thơ tương ứng với tài nguyên nào trên DBpedia?",  # owl:sameAs
]

# Bậc thang SPARQL cho tab SPARQL: mỗi bậc thêm một khả năng mới (tên hiện trong ô "Truy vấn mẫu")
SPARQL_LADDER = [
    (
        "1 · Thông tin Công Phượng (triple cơ bản)",
        """SELECT ?thuoc_tinh ?gia_tri WHERE {
  vres:Nguyễn_Công_Phượng ?p ?gia_tri .
  ?p rdfs:label ?thuoc_tinh . FILTER(lang(?thuoc_tinh) = "vi")
  FILTER(STRSTARTS(STR(?p), STR(vio:)) && ?p NOT IN (vio:careerStation, vio:playedFor))
}""",
    ),
    (
        "2 · Quá trình thi đấu Công Phượng (nối nhiều triple)",
        """SELECT ?loai ?doi ?tu ?den ?tran ?ban ?cho_muon WHERE {
  vres:Nguyễn_Công_Phượng vio:careerStation ?chang .
  ?chang a ?lop ; vio:team ?doi ; vio:startYear ?tu .
  ?lop rdfs:subClassOf vio:CareerStation ; rdfs:label ?loai . FILTER(lang(?loai) = "vi")
  OPTIONAL { ?chang vio:endYear ?den }
  OPTIONAL { ?chang vio:appearances ?tran }
  OPTIONAL { ?chang vio:goals ?ban }
  OPTIONAL { ?chang vio:onLoan ?cho_muon }
} ORDER BY ?tu""",
    ),
    (
        "3 · CLB → sân nhà → tỉnh (nhiều bước)",
        """SELECT ?clb ?san ?tinh WHERE {
  ?clb a vio:FootballClub ; vio:ground ?san .
  ?san vio:province ?tinh .
} ORDER BY ?tinh""",
    ),
    (
        "4 · Tỉnh có nhiều cầu thủ quê quán nhất (gom nhóm)",
        """SELECT ?tinh (COUNT(DISTINCT ?cau_thu) AS ?so_cau_thu) WHERE {
  ?cau_thu a vio:FootballPlayer ; vio:birthProvince ?tinh .
} GROUP BY ?tinh ORDER BY DESC(?so_cau_thu) LIMIT 10""",
    ),
    (
        "5 · Như bậc 4, gộp tỉnh cũ vào tỉnh sau sáp nhập (successor)",
        """SELECT ?tinh_hien_nay (COUNT(DISTINCT ?cau_thu) AS ?so_cau_thu)
       (GROUP_CONCAT(DISTINCT ?ten_que; separator=", ") AS ?gom_tu) WHERE {
  ?cau_thu a vio:FootballPlayer ; vio:birthProvince ?que .
  ?que rdfs:label ?ten_que . FILTER(lang(?ten_que) = "vi")
  OPTIONAL { ?que a vio:FormerProvince ; vio:successor ?moi }
  BIND(COALESCE(?moi, ?que) AS ?tinh_hien_nay)
} GROUP BY ?tinh_hien_nay ORDER BY DESC(?so_cau_thu) LIMIT 10""",
    ),
    (
        "6 · Ai từng chơi cho HAGL (tắt “Có suy luận” → 0 dòng)",
        """SELECT DISTINCT ?cau_thu WHERE {
  ?cau_thu vio:playedFor vres:Câu_lạc_bộ_bóng_đá_Hoàng_Anh_Gia_Lai .
}""",
    ),
    (
        "7 · Kiểm tra mâu thuẫn: cá thể thuộc hai lớp tách rời (kỳ vọng 0)",
        """SELECT (COUNT(*) AS ?so_vi_pham) WHERE {
  ?tien_de a owl:AllDisjointClasses ; owl:members ?ds .
  ?ds rdf:rest*/rdf:first ?a .
  ?ds rdf:rest*/rdf:first ?b .
  FILTER(STR(?a) < STR(?b))
  ?x a ?a , ?b .
}""",
    ),
]

# Thử thêm một triple vào graph rồi chạy reasoner (trang Thực thể). Khoá = local name của chủ ngữ.
# (chủ ngữ, thuộc tính, tân ngữ, mô tả bằng lời); tân ngữ là local name trong vres: hoặc qname của lớp
CONSISTENCY_PRESETS = {
    "Nguyễn_Công_Phượng": [
        (
            "Nguyễn_Công_Phượng",
            "vio:ground",
            "Sân_vận_động_Pleiku",
            "Đọc nhầm ô “sân nhà” của CLB sang cầu thủ",
        ),
        (
            "Nguyễn_Công_Phượng",
            "vio:currentClub",
            "Đội_tuyển_bóng_đá_quốc_gia_Việt_Nam",
            "Ghi đội tuyển vào ô “CLB hiện tại”",
        ),
        (
            "Nguyễn_Công_Phượng",
            "vio:birthPlace",
            "Câu_lạc_bộ_bóng_đá_Hoàng_Anh_Gia_Lai",
            "Link nơi sinh trỏ nhầm sang CLB",
        ),
        (
            "Nguyễn_Công_Phượng",
            "vio:birthProvince",
            "Gia_Lai",
            "Sai sự thật nhưng đúng loại (đối chứng)",
        ),
    ],
}
