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
    "Cầu thủ nào từng chơi cho Than Quảng Ninh?",  # khoe property chain: có suy luận vs chỉ khai báo
    "Quá trình thi đấu ở câu lạc bộ của Công Phượng?",
    "Câu lạc bộ nào có sân nhà ở Hà Nội?",  # nhiều bước CLB → sân → tỉnh
    "Tỉnh nào có nhiều cầu thủ quê quán nhất?",
    "Đại học Cần Thơ tương ứng với tài nguyên nào trên DBpedia?",  # owl:sameAs
]
