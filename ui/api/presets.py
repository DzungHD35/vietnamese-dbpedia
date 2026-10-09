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

# Mỗi câu khoe một bước của luồng hỏi đáp, và không trùng ví dụ few-shot trong prompt của team
# (vidbpedia/web/kg_rag.py), để demo cho thấy LLM tự viết được SPARQL cho câu mới.
DEMO_QUESTIONS = [
    "Cầu thủ nào từng chơi cho Than Quảng Ninh?",  # chuỗi thuộc tính: 39 dòng có suy luận, 0 dòng chỉ khai báo
    "Quang Hải đã chơi cho những câu lạc bộ nào?",  # bước ①: hai cầu thủ trùng tên (sinh 1985 và 1997)
    "Câu lạc bộ nào có sân nhà ở Đà Nẵng?",  # nhiều bước CLB → sân → tỉnh; có Quảng Nam nhờ sáp nhập 2025
    "Trường đại học nào ở Huế được thành lập sớm nhất?",  # sắp xếp theo năm thành lập
    "Hà Giang sau năm 2025 sáp nhập vào tỉnh nào?",  # vio:FormerProvince và vio:successor
    "Đặng Văn Lâm tương ứng với tài nguyên nào trên DBpedia tiếng Anh?",  # owl:sameAs ra Linked Open Data
]
# câu gõ không dấu để khoe bước ① (gợi ý dưới ô hỏi, không phải chip)
NO_DIACRITICS_EXAMPLE = "quang hai da choi cho nhung clb nao"
