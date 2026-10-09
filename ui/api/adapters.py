"""Nơi DUY NHẤT gọi hàm/thuộc tính private của vidbpedia (chỉ đọc).

Team đổi `ResourceView`, `SparqlBasedKGRAG`… thì chỉ phải sửa file này. Mọi hàm trả dữ liệu thuần
(list, dict, set), không trả HTML.
"""

from vidbpedia.web.kg_rag import ANSWER_TEMPLATE
from vidbpedia.web.resource_page import ResourceView


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


def answer(rag, question, sparql, rows):
    """Nửa sau của `SparqlBasedKGRAG.query`: LLM viết câu trả lời từ kết quả → (answer, reasoning)."""
    shown = rows[: rag.max_rows_for_answer]
    rows_text = "\n".join(" | ".join(f"{k}={v[:800]}" for k, v in r.items()) for r in shown) or "(rỗng)"
    prompt = ANSWER_TEMPLATE.format(
        question=question, sparql=sparql, n_rows=len(rows), shown=len(shown), rows=rows_text
    )
    return rag._parse_answer(rag._complete(prompt))


def tree_groups(view, node, path, root):
    """Nhóm quan hệ của một nút trong cây quan hệ 3 bước: [(thuộc tính, "out"/"in", [đích đã sắp xếp])].

    Cùng hàm với tab Tài nguyên của team (TREE_OUT, TREE_IN, chỉ triple khai báo trừ playedFor)."""
    return view._tree_groups(node, path, root)


def station_note(view, station):
    """Ghi chú của một chặng thi đấu: "2015–2023, 103 trận, 36 bàn, cho mượn"."""
    return view._station_note(station)
