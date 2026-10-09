"""Nơi DUY NHẤT gọi hàm/thuộc tính private của vidbpedia (chỉ đọc).

Team đổi `ResourceView`, `SparqlBasedKGRAG`… thì chỉ phải sửa file này. Mọi hàm trả dữ liệu thuần
(list, dict, set), không trả HTML.
"""

from vidbpedia.web.kg_rag import ANSWER_TEMPLATE
from vidbpedia.web.resource_page import ResourceView

# Prompt trả lời của team bảo LLM tin tuyệt đối vào kết quả; màn Hỏi đáp cho LLM nói rõ khi kết quả không khớp
# câu hỏi (ví dụ hai cầu thủ trùng tên) thay vì trả lời chắc chắn. Team đổi câu này thì import báo lỗi ngay.
TRUST_RULE = "- Kết quả đã được lọc đúng theo câu hỏi; mỗi dòng là một kết quả hợp lệ.\n"
CAREFUL_RULE = (
    "- Mỗi dòng là một kết quả đúng theo dữ liệu: nhắc đủ mọi dòng, KHÔNG loại dòng nào theo hiểu biết riêng (dữ liệu "
    "đã cập nhật, ví dụ địa giới sau sáp nhập tỉnh năm 2025). Chỉ nói rõ khi bảng thiếu thông tin câu hỏi cần, "
    "thay vì đoán.\n"
)
# Prompt của team luôn trả lời bằng tiếng Việt; màn Hỏi đáp trả lời theo ngôn ngữ của câu hỏi.
VIETNAMESE_ONLY = "Trả lời câu hỏi bằng tiếng Việt, CHỈ dựa trên kết quả truy vấn SPARQL bên dưới."
SAME_LANGUAGE = (
    "Trả lời bằng đúng ngôn ngữ của câu hỏi (hỏi bằng tiếng Anh thì trả lời bằng tiếng Anh), giữ nguyên tên riêng "
    "tiếng Việt, CHỈ dựa trên kết quả truy vấn SPARQL bên dưới."
)
for _rule in (TRUST_RULE, VIETNAMESE_ONLY):
    assert _rule in ANSWER_TEMPLATE, f"ANSWER_TEMPLATE của team đã đổi, cập nhật adapters.py: {_rule!r}"
ASK_ANSWER_TEMPLATE = ANSWER_TEMPLATE.replace(TRUST_RULE, CAREFUL_RULE).replace(
    VIETNAMESE_ONLY, SAME_LANGUAGE
)


def neighbors(view, iri):
    """→ (đi ra, đi vào); mỗi phần tử là (IRI, [thuộc tính]) theo thứ tự LINK_PROPS."""
    return view._neighbors(iri)


def round_robin(items, n):
    """Lấy n phần tử của `neighbors`, xoay vòng giữa các thuộc tính để quan hệ nào cũng có mặt."""
    return ResourceView._round_robin(items, n)


def prop_key(view, prop):
    """Khoá sắp xếp thuộc tính như trang tài nguyên của team: rdf:type, nhãn… trước, rồi vio:, dbo:, khác, vip:."""
    return view._prop_key(prop)


def label_index(view):
    """Chỉ mục tên → thực thể: {fold(tên hoặc tên khác): {IRI}}; dựng từ chỉ mục tìm kiếm của team."""
    index: dict[str, set] = {}
    for key, iri in view._entries:
        index.setdefault(key, set()).add(iri)
    return index


def validate(rag, query):
    """Truy vấn đầy đủ PREFIX (kiểm tra cú pháp, chỉ cho SELECT/ASK); ném lỗi nếu không hợp lệ."""
    return rag._validate(query)


def answer(rag, question, sparql, rows, notes=()):
    """Nửa sau của `SparqlBasedKGRAG.query` với ASK_ANSWER_TEMPLATE: LLM viết câu trả lời từ kết quả → (answer, reasoning).

    `notes` (ngôn ngữ trả lời, tên trùng nhiều thực thể) đặt ở cuối prompt, chỗ LLM ít bỏ qua nhất."""
    shown = rows[: rag.max_rows_for_answer]
    rows_text = "\n".join(" | ".join(f"{k}={v[:800]}" for k, v in r.items()) for r in shown) or "(rỗng)"
    prompt = ASK_ANSWER_TEMPLATE.format(
        question=question, sparql=sparql, n_rows=len(rows), shown=len(shown), rows=rows_text
    )
    if notes:
        prompt += "\nLưu ý:\n" + "\n".join(f"- {n}" for n in notes) + "\n"
    return rag._parse_answer(rag._complete(prompt))


def tree_groups(view, node, path, root):
    """Nhóm quan hệ của một nút trong cây quan hệ 3 bước: [(thuộc tính, "out"/"in", [đích đã sắp xếp])].

    Cùng hàm với tab Tài nguyên của team (TREE_OUT, TREE_IN, chỉ triple khai báo trừ playedFor)."""
    return view._tree_groups(node, path, root)


def station_note(view, station):
    """Ghi chú của một chặng thi đấu: "2015–2023, 103 trận, 36 bàn, cho mượn"."""
    return view._station_note(station)
