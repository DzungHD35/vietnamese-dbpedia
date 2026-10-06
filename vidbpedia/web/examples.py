"""Truy vấn mẫu (tab SPARQL), câu hỏi gợi ý (tab Hỏi đáp) và thực thể ví dụ (tab Tài nguyên)."""

EXAMPLE_QUERIES = {
    "Đếm theo lớp DBpedia (suy luận)": """SELECT ?class (COUNT(DISTINCT ?x) AS ?n) WHERE {
    VALUES ?class { dbo:Person dbo:SoccerPlayer dbo:Organisation dbo:SoccerClub dbo:University
                    dbo:Place dbo:Province dbo:Stadium dbo:CareerStation }
    ?x a ?class .
}
GROUP BY ?class
ORDER BY DESC(?n)
""",
    "Quá trình thi đấu cầu thủ": """SELECT DISTINCT ?loai ?doi ?tu ?den ?tran ?ban WHERE {
    # tìm theo tên trong subquery: rdflib áp FILTER sau khi nối cả nhóm, viết phẳng chậm hơn nhiều
    { SELECT DISTINCT ?p WHERE { ?p a vio:FootballPlayer ; rdfs:label|skos:altLabel ?ten .
                                 FILTER(CONTAINS(LCASE(STR(?ten)), "quang hải")) } }
    ?p vio:careerStation ?st .
    ?st a ?type ; vio:team ?t .
    ?type rdfs:label ?loai . FILTER(lang(?loai) = "vi" && ?type != vio:CareerStation)
    ?t rdfs:label ?doi . FILTER(lang(?doi) = "vi")
    OPTIONAL { ?st vio:startYear ?tu }
    OPTIONAL { ?st vio:endYear ?den }
    OPTIONAL { ?st vio:appearances ?tran }
    OPTIONAL { ?st vio:goals ?ban }
}
ORDER BY ?tu
""",
    "CLB, sân nhà và tỉnh": """SELECT DISTINCT ?clb ?san ?suc_chua ?tinh WHERE {
    ?c a vio:FootballClub ; rdfs:label ?clb ; vio:ground ?s .
    ?s rdfs:label ?san .
    OPTIONAL { ?s vio:capacity ?suc_chua }
    OPTIONAL { ?s vio:province ?p . ?p rdfs:label ?tinh . FILTER(lang(?tinh) = "vi") }
    FILTER(lang(?clb) = "vi" && lang(?san) = "vi")
}
ORDER BY DESC(?suc_chua)
LIMIT 30
""",
    "Tỉnh có nhiều cầu thủ nhất": """SELECT ?tinh (COUNT(DISTINCT ?p) AS ?so_cau_thu) WHERE {
    ?p a vio:FootballPlayer ; vio:birthProvince ?prov .
    ?prov rdfs:label ?tinh . FILTER(lang(?tinh) = "vi")
}
GROUP BY ?tinh
ORDER BY DESC(?so_cau_thu)
LIMIT 15
""",
    "Số trường đại học theo tỉnh": """SELECT ?tinh (COUNT(DISTINCT ?u) AS ?so_truong) WHERE {
    ?u a vio:University ; vio:province ?p .
    ?p rdfs:label ?tinh . FILTER(lang(?tinh) = "vi")
}
GROUP BY ?tinh
ORDER BY DESC(?so_truong)
LIMIT 15
""",
    "Tìm theo tên khác (redirect)": """SELECT DISTINCT ?ten_khac ?trang_chinh WHERE {
    { SELECT DISTINCT ?r ?ten_khac WHERE { ?r dbo:wikiPageRedirects ?x ; rdfs:label ?ten_khac .
                                           FILTER(CONTAINS(LCASE(STR(?ten_khac)), "công phượng")) } }
    ?r dbo:wikiPageRedirects ?t . ?t a vio:FootballPlayer ; rdfs:label ?trang_chinh .
    FILTER(lang(?trang_chinh) = "vi")
}
""",
    "Thể loại Wikipedia của các CLB": """SELECT ?the_loai (COUNT(DISTINCT ?c) AS ?so_clb) WHERE {
    ?c a vio:FootballClub ; dct:subject ?cat .
    ?cat skos:prefLabel ?the_loai .
}
GROUP BY ?the_loai
ORDER BY DESC(?so_clb)
LIMIT 15
""",
    "Liên kết với English DBpedia": """SELECT ?vi ?ten ?en WHERE {
    ?vi a vio:FootballClub ; owl:sameAs ?en ; rdfs:label ?ten .
    FILTER(STRSTARTS(STR(?en), "http://dbpedia.org/resource/") && lang(?ten) = "vi")
}
LIMIT 20
""",
    "Mô tả dataset (VoID)": """SELECT ?p ?o WHERE {
    <http://vi.dbpedia.org/void/Dataset> ?p ?o .
}
""",
}

EXAMPLE_QUESTIONS = [
    "Công Phượng đã thi đấu cho những câu lạc bộ nào?",
    "Câu lạc bộ nào có sân nhà ở Hà Nội?",
    "Tỉnh nào có nhiều cầu thủ quê quán nhất?",
    "Những cầu thủ sinh ở Nghệ An từng khoác áo đội tuyển quốc gia?",
    "Sân vận động nào có sức chứa lớn nhất?",
    "Hiện có bao nhiêu tỉnh, thành phố trực thuộc trung ương?",
    "Đại học Cần Thơ được thành lập năm nào?",
    "Hà Nội có bao nhiêu trường đại học trong dữ liệu?",
    "Đặng Văn Lâm tương ứng với tài nguyên nào trên DBpedia tiếng Anh?",
]

# local name của IRI vres:, nhãn hiển thị
RESOURCE_EXAMPLES = [
    ("Nguyễn_Công_Phượng", "Nguyễn Công Phượng"),
    ("Câu_lạc_bộ_bóng_đá_Hoàng_Anh_Gia_Lai", "CLB Hoàng Anh Gia Lai"),
    ("Sân_vận_động_Hàng_Đẫy", "Sân vận động Hàng Đẫy"),
    ("Nghệ_An", "Nghệ An"),
    ("Hà_Tây_(tỉnh)", "Hà Tây (tỉnh cũ)"),
    ("Đại_học_Cần_Thơ", "Đại học Cần Thơ"),
]
