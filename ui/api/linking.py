"""Bước ① của màn Hỏi đáp: nhận diện thực thể trong câu hỏi bằng chỉ mục tên, không phân biệt dấu.

Chỉ mục là nhãn và tên khác (redirect) của các thực thể thuộc lớp chính, cùng chỉ mục với ô tìm kiếm của trang
tài nguyên. Câu hỏi được tách thành từ và thử cụm dài trước; cụm đã khớp không dùng lại cho cụm ngắn hơn.
- Khớp đầy đủ: cụm trùng nguyên một tên, kể cả khi bỏ phần trong ngoặc ("Hà Tây (tỉnh)" → "ha tay").
- Khớp đuôi tên: cụm từ hai từ trở lên trùng phần cuối của một tên ("quang hai" → "Nguyễn Quang Hải").
Kết quả gửi kèm prompt để LLM dùng thẳng IRI thay vì tự đoán chuỗi tìm theo nhãn.
"""

import re
import time
from functools import lru_cache

from ui.api import adapters, serialize
from ui.api.state import kg
from vidbpedia.web.resource_page import fold

MAX_SPAN = 8  # số từ tối đa của một tên trong câu hỏi
MAX_CANDIDATES = 6  # một cụm khớp nhiều thực thể hơn thế là quá chung chung, bỏ qua
TAIL_WORDS = (
    2,
    3,
    4,
)  # độ dài phần đuôi tên dùng để khớp ("kinh tế quốc dân" → Trường Đại học Kinh tế Quốc dân)
# từ chỉ loại thực thể: cụm chỉ gồm các từ này ("vận động", "quốc gia", "đại học") không phải là tên
GENERIC = {
    "bo", "bong", "cau", "clb", "da", "dai", "doi", "dong", "gia", "hoc", "lac", "pho", "quoc",
    "san", "su", "pham", "thanh", "thao", "the", "thu", "tinh", "truong", "tuyen", "van", "vien",
}  # fmt: skip


def _words(text: str) -> list[str]:
    return re.sub(r"[^\w\s]", " ", text).split()


def _key(text: str) -> str:
    return " ".join(fold(w).replace(" ", "") for w in _words(text))


@lru_cache(maxsize=1)
def _indexes() -> tuple[dict[str, set], dict[str, set]]:
    """(tên đầy đủ → {IRI}, đuôi tên → {IRI}); dựng một lần từ chỉ mục tìm kiếm của team."""
    exact: dict[str, set] = {}
    tail: dict[str, set] = {}
    for name, iris in adapters.label_index(kg.view).items():
        base = _key(re.sub(r"\(.*?\)", " ", name))
        for key in {_key(name), base}:
            if key:
                exact.setdefault(key, set()).update(iris)
        words = base.split()
        for n in TAIL_WORDS:
            if len(words) > n:
                tail.setdefault(" ".join(words[-n:]), set()).update(iris)
    return exact, tail


def link(question: str) -> dict:
    """→ {mentions: [{text, match, candidates: [Node]}], ms}; mentions theo thứ tự xuất hiện trong câu."""
    t0 = time.perf_counter()
    words = _words(question)
    keys = [fold(w).replace(" ", "") for w in words]
    exact, tail = _indexes()
    used = [False] * len(words)
    found = []
    for n in range(min(MAX_SPAN, len(words)), 0, -1):
        for i in range(len(words) - n + 1):
            span = keys[i : i + n]
            if any(used[i : i + n]) or set(span) <= GENERIC:
                continue
            phrase = " ".join(span)
            if n == 1 and len(phrase) < 3:
                continue
            iris, match = exact.get(phrase), "exact"
            if not iris and n >= 2:
                iris, match = tail.get(phrase), "tail"
            if not iris or len(iris) > MAX_CANDIDATES:
                continue
            used[i : i + n] = [True] * n
            candidates = [serialize.node(kg.view, iri) for iri in sorted(iris, key=str)]
            found.append((i, {"text": " ".join(words[i : i + n]), "match": match, "candidates": candidates}))
    mentions = [m for _, m in sorted(found, key=lambda x: x[0])]
    return {"mentions": mentions, "ms": round((time.perf_counter() - t0) * 1000, 1)}


# Không nhận diện được tên nào: LLM tìm theo nhãn, nguyên cụm trước; ra 0 dòng thì lần sửa tách cụm thành từng từ
# (qa.split_contains viết sẵn điều kiện tách từ vào phản hồi gửi lại LLM).
NO_MENTION_HINT = (
    "\nKhông nhận diện được tên thực thể nào trong câu hỏi bằng chỉ mục tên. Nếu câu hỏi nhắc tới một thực thể cụ "
    "thể, tìm nó theo nhãn trong một subquery (rdfs:label|skos:altLabel, luôn kèm lớp):\n"
    "- Lần đầu: tìm nhãn chứa NGUYÊN cụm tên như trong câu hỏi (giữ dấu, chữ thường), ví dụ "
    'FILTER(CONTAINS(LCASE(STR(?n)), "sân thống nhất")).\n'
    "- Nếu không ra dòng nào: tách cụm tên theo khoảng trắng và tìm nhãn chứa đủ TỪNG từ, ví dụ "
    'FILTER(CONTAINS(LCASE(STR(?n)), "sân") && CONTAINS(LCASE(STR(?n)), "thống") && '
    'CONTAINS(LCASE(STR(?n)), "nhất")).\n'
)


def hint_text(mentions: list[dict]) -> str:
    """Đoạn gửi kèm prompt sinh SPARQL (chèn ngay trước câu hỏi)."""
    if not mentions:
        return NO_MENTION_HINT
    lines = [
        "",
        "Thực thể đã nhận diện trong câu hỏi (tìm bằng chỉ mục tên, không phân biệt dấu; các IRI này có thật trong graph):",
    ]
    for m in mentions:
        options = " hoặc ".join(
            f"<{c['iri']}> ({c['label']}; {c['cls'] or 'không rõ lớp'})" for c in m["candidates"]
        )
        lines.append(f'- "{m["text"]}" → {options}')
    lines += [
        "Cách dùng các IRI này:",
        "- Dùng thẳng IRI thay cho subquery tìm theo nhãn, đúng vai trò theo lớp của nó: tỉnh là đối tượng của "
        "vio:province hoặc vio:birthProvince (ví dụ ?u vio:province <iri_tỉnh>), CLB là đối tượng của vio:team hoặc "
        "vio:playedFor, cầu thủ là chủ thể của vio:careerStation.",
        "- Chỉ viết IRI có trong danh sách này. Thực thể khác (ví dụ các trường trong một tỉnh) phải tìm qua thuộc "
        "tính hoặc theo nhãn, KHÔNG tự đặt IRI.",
        "- Một tên ứng với nhiều thực thể: dùng VALUES ?x { <iri1> <iri2> } và BẮT BUỘC SELECT cả ?x lẫn nhãn của "
        "?x, để câu trả lời phân biệt được từng thực thể.",
    ]
    return "\n".join(lines) + "\n"
