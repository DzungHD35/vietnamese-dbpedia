"""Bước ②–④ của màn Hỏi đáp, ghi lại để giao diện chỉ ra hệ thống đã làm gì.

② sinh SPARQL: vòng tự sửa giống `SparqlBasedKGRAG.generate_and_run` của team (cùng số lần, cùng phản hồi gửi lại
LLM), khác ở chỗ giữ mọi lần thử kèm thời gian, gửi kèm thực thể đã nhận diện ở bước ①, và phản hồi nói rõ lỗi kiểm
tra được bằng graph: IRI LLM tự đặt, IRI dùng sai lớp (tỉnh Huế đặt vào chỗ một trường đại học). Tìm nhãn chứa
nguyên cụm tên mà ra 0 dòng thì phản hồi viết sẵn điều kiện tách cụm thành từng từ ("sân thống nhất" → nhãn chứa
"sân", "thống" và "nhất"). Kết quả gộp các thực thể trùng tên thì hệ thống tự thêm biến thực thể vào SELECT, không
gọi LLM.
③ kiểm tra truy vấn trước khi tin kết quả, và đếm triple khai báo / suy luận của từng thuật ngữ ontology dùng tới.
④ thời gian chạy và số dòng lấy từ lần thử cuối.
"""

import re
import time

from rdflib import URIRef
from rdflib.namespace import OWL, RDF, RDFS

from vidbpedia.kg.query import QueryError, ensure_local, prepare
from vidbpedia.vocab import PREFIXES, VIO, VRES
from vidbpedia.web.kg_rag import SPARQL_GENERATION_TEMPLATE
from vidbpedia.web.resource_page import fold

MAX_TERMS = 12
LIMIT_RE = re.compile(r"\bLIMIT\s+(\d+)", re.I)
AGGREGATE_RE = re.compile(r"\b(COUNT|SUM|AVG|MIN|MAX)\s*\(", re.I)
TERM_RE = re.compile(r"\b(vio|dbo):([A-Za-z]\w*)")
FULL_IRI_RE = re.compile(r"<(http://vi\.dbpedia\.org/resource/[^>\s]+)>")
PREFIXED_RE = re.compile(r"\bvres:([\w\-]+)")
VALUES_RE = re.compile(r"VALUES\s+\?(\w+)\s*\{([^}]*)\}", re.I)
SELECT_RE = re.compile(r"\bSELECT\b(.*?)\bWHERE\b", re.I | re.S)
SELECT_HEAD_RE = re.compile(r"\bSELECT\s+(?:DISTINCT\s+|REDUCED\s+)?", re.I)
GROUP_BY_RE = re.compile(r"\bGROUP\s+BY\b", re.I)
TYPE_OF = r"\?{var}\s+(?:a|rdf:type)\s+(vio|dbo):([A-Za-z]\w*)"
CONTAINS_RE = re.compile(
    r'CONTAINS\s*\(\s*LCASE\s*\(\s*STR\s*\(\s*\?(\w+)\s*\)\s*\)\s*,\s*"([^"]+)"\s*\)', re.I
)

# phản hồi gửi lại LLM, chép từ SparqlBasedKGRAG.generate_and_run
REPAIR_ERROR = "\nLần trước bạn viết:\n{sparql}\nTruy vấn này lỗi: {error}\nHãy sửa lại.\n"
REPAIR_EMPTY = (
    "\nLần trước bạn viết:\n{sparql}\nTruy vấn chạy được nhưng không có kết quả. "
    "Hãy thử nới điều kiện (từ khóa ngắn hơn, bỏ lọc ngôn ngữ, dùng OPTIONAL).\n"
)
REPAIR_UNKNOWN = (
    "Các IRI sau KHÔNG có trong graph (bạn đã tự đặt): {iris}. Chỉ dùng IRI trong danh sách thực thể đã nhận diện; "
    "thực thể khác phải tìm qua thuộc tính hoặc theo nhãn.\n"
)


def unknown_iris(graph, sparql: str) -> list[str]:
    """IRI vres: trong truy vấn mà graph không có: dấu hiệu LLM tự đặt IRI thay vì tìm."""
    iris = set(FULL_IRI_RE.findall(sparql)) | {str(VRES) + local for local in PREFIXED_RE.findall(sparql)}
    return sorted(
        i for i in iris if (URIRef(i), None, None) not in graph and (None, None, URIRef(i)) not in graph
    )


REPAIR_CLASS = (
    "<{iri}> thuộc lớp {actual}, không phải {expected}: đừng gán nó cho ?{var}. Dùng nó làm đối tượng của thuộc "
    "tính nối tới nó (ví dụ ?{var} vio:province <{iri}> khi đó là tỉnh, ?{var} vio:team <{iri}> khi đó là CLB).\n"
)
REPAIR_SPLIT = (
    "Tìm nhãn chứa nguyên cụm tên không ra thực thể nào. Hệ thống đã tách cụm tên theo khoảng trắng và tìm thực thể "
    "có nhãn chứa đủ TỪNG từ:\n{lines}"
)
SPLIT_FOUND = (
    "Viết lại truy vấn dùng thẳng IRI của thực thể đúng ở trên, theo đúng lớp và quan hệ của nó: bỏ subquery tìm "
    "theo nhãn và mọi ràng buộc lớp không khớp (ví dụ đừng ép một huấn luyện viên là vio:FootballPlayer).\n"
)
SPLIT_NOT_FOUND = (
    "- điều kiện {new}: không có thực thể nào. Thử từ khóa ngắn hơn; có thể dữ liệu chưa có thực thể này.\n"
)
# lớp hiển thị cho thực thể, cụ thể trước chung chung
PREFERRED_CLASSES = [
    "FootballPlayer", "FootballClub", "NationalFootballTeam", "Stadium", "University", "FormerProvince", "Province",
    "Country", "ClubStation", "NationalTeamStation", "YouthStation", "Person", "Organisation", "Location",
]  # fmt: skip


MAX_LABEL_MATCHES = 5


def split_contains(sparql: str) -> list[tuple[str, str, list[str]]]:
    """Mỗi `CONTAINS(LCASE(STR(?n)), "cụm nhiều từ")` → (điều kiện cũ, điều kiện chứa đủ từng từ, các từ)."""
    out = []
    for m in CONTAINS_RE.finditer(sparql):
        var, words = m.group(1), m.group(2).split()
        if len(words) >= 2 and not any("\\" in w for w in words):
            out.append(
                (m.group(0), " && ".join(f'CONTAINS(LCASE(STR(?{var})), "{w}")' for w in words), words)
            )
    return out


def _vio_classes(graph, iri) -> list[str]:
    present = {str(t)[len(VIO) :] for t in graph.objects(iri, RDF.type) if str(t).startswith(str(VIO))}
    return [f"vio:{c}" for c in PREFERRED_CLASSES if c in present] + sorted(
        f"vio:{c}" for c in present if c not in PREFERRED_CLASSES
    )


def _label(graph, iri) -> str:
    labels = list(graph.objects(iri, RDFS.label))
    vi = [str(x) for x in labels if getattr(x, "language", None) == "vi"]
    return (vi or [str(x) for x in labels] or [str(iri)[len(VRES) :]])[0]


def label_matches(rag, words: list[str]) -> list[dict]:
    """Hệ thống tự tìm thử thực thể có nhãn chứa đủ các từ (mọi lớp, kể cả huấn luyện viên chỉ có nhãn) →
    [{iri, label, classes, links: [(thuộc tính vio: nối tới nó, lớp của đầu kia, nhãn đầu kia)]}]."""
    cond = " && ".join(f'CONTAINS(LCASE(STR(?n)), "{w}")' for w in words)
    query = f"SELECT DISTINCT ?x WHERE {{ ?x rdfs:label|skos:altLabel ?n . FILTER({cond}) }} LIMIT 20"
    graph, out = rag.graph, []
    try:
        # graph.query giữ nguyên URIRef (run_sparql giải mã %xx trong IRI)
        found = [row[0] for row in graph.query(prepare(query, allow_remote=False))]
    except Exception:
        return []
    for iri in found:
        if not str(iri).startswith(str(VRES)):
            continue
        links = []
        for p in sorted(
            {p for _, p in graph.subject_predicates(iri) if str(p).startswith(str(VIO))}, key=str
        )[:3]:
            s = next(graph.subjects(p, iri))
            classes = _vio_classes(graph, s)
            links.append((f"vio:{str(p)[len(VIO) :]}", classes[0] if classes else "?", _label(graph, s)))
        out.append(
            {
                "iri": str(iri),
                "label": _label(graph, iri),
                "classes": _vio_classes(graph, iri),
                "links": links,
            }
        )
        if len(out) == MAX_LABEL_MATCHES:
            break
    return out


def _describe_match(m: dict) -> str:
    links = "; ".join(f"?s {p} <{m['iri']}> với ?s là {cls}, ví dụ “{label}”" for p, cls, label in m["links"])
    return f"  - <{m['iri']}> “{m['label']}”: lớp {', '.join(m['classes']) or '?'}" + (
        f"; được nối tới qua {links}" if links else ""
    )


def _split_feedback(rag, splits) -> str:
    lines, found_any = [], False
    for _, new, words in splits:
        found = label_matches(rag, words)
        if found:
            found_any = True
            quoted = ", ".join(f'"{w}"' for w in words)
            lines.append(f"- nhãn chứa đủ {quoted} (điều kiện {new}):\n")
            lines += [_describe_match(m) + "\n" for m in found]
        else:
            lines.append(SPLIT_NOT_FOUND.format(new=new))
    return REPAIR_SPLIT.format(lines="".join(lines)) + (SPLIT_FOUND if found_any else "")


def _values_iris(body: str) -> list[str]:
    return FULL_IRI_RE.findall(body) + [str(VRES) + local for local in PREFIXED_RE.findall(body)]


def class_mismatches(graph, sparql: str) -> list[dict]:
    """IRI trong `VALUES ?x` mà truy vấn lại đòi ?x thuộc một lớp IRI đó không có (tỉnh Huế dùng làm vio:University):
    truy vấn như vậy không bao giờ ra dòng nào."""
    out = []
    for var, body in VALUES_RE.findall(sparql):
        iris = _values_iris(body)
        for prefix, local in re.findall(TYPE_OF.format(var=var), sparql):
            cls = URIRef(PREFIXES[prefix] + local)
            if not iris or any((URIRef(i), RDF.type, cls) in graph for i in iris):
                continue
            for i in iris:
                actual = sorted(
                    f"vio:{str(t)[len(VIO) :]}"
                    for t in graph.objects(URIRef(i), RDF.type)
                    if str(t).startswith(str(VIO))
                )
                out.append(
                    {
                        "iri": i,
                        "var": var,
                        "expected": f"{prefix}:{local}",
                        "actual": ", ".join(actual) or "?",
                    }
                )
    return out


def _project_entity(sparql: str, mentions: list[dict]) -> tuple[str, str, str] | None:
    """Truy vấn có VALUES chứa các thực thể trùng tên nhưng không SELECT biến đó (kết quả gộp, không biết dòng nào của
    ai) → (truy vấn đã thêm biến vào SELECT, tên trong câu hỏi, biến); None nếu không cần hoặc không sửa an toàn được."""
    head = SELECT_RE.search(sparql)
    if not head or GROUP_BY_RE.search(sparql) or AGGREGATE_RE.search(head.group(1)) or "*" in head.group(1):
        return None
    for m in mentions:
        iris = [c["iri"] for c in m["candidates"]]
        if len(iris) < 2:
            continue
        for var, body in VALUES_RE.findall(sparql):
            if sum(f"<{i}>" in body for i in iris) >= 2 and not re.search(rf"\?{var}\b", head.group(1)):
                fixed = SELECT_HEAD_RE.sub(lambda s: f"{s.group(0)}?{var} ", sparql, count=1)
                return fixed, m["text"], var
    return None


def _ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 1)


def prompt_text(rag, question: str, hints: str) -> str:
    """Prompt của lần thử đầu, đúng như gửi cho LLM (các lần sửa chỉ thêm phản hồi vào trước câu hỏi)."""
    return SPARQL_GENERATION_TEMPLATE.format(
        schema=rag.get_schema(), prefix_names=", ".join(PREFIXES), feedback=hints, question=question
    )


def _execute(rag, sparql: str) -> tuple[list, list, str | None, float]:
    t0 = time.perf_counter()
    try:
        columns, rows = rag.run_sparql(sparql)
        return columns, rows, None, _ms(t0)
    except Exception as e:  # cú pháp sai, không phải SELECT/ASK, có SERVICE/FROM, lỗi khi chạy
        return [], [], str(e), _ms(t0)


def _attempt(n, sparql, rows, error, llm_ms, run_ms, feedback, by="llm") -> dict:
    """Một lần thử ở bước ②; `by`: "llm" (LLM viết), "cache" (SPARQL viết sẵn), "system" (hệ thống tự sửa)."""
    status = "error" if error else "ok" if rows else "empty"
    return {
        "n": n,
        "by": by,
        "sparql": sparql,
        "status": status,
        "error": error,
        "rows": len(rows),
        "llmMs": llm_ms,
        "runMs": run_ms,
        "feedback": feedback.strip() or None,
    }


def generate(rag, question: str, hints: str = "", mentions=()) -> dict:
    """LLM sinh SPARQL, chạy, sửa nếu lỗi hoặc rỗng → {sparql, columns, rows, error, attempts: [...]}.

    Lỗi khi gọi LLM (thiếu key, mạng, quota) được ném ra cho route xử lý."""
    attempts: list[dict] = []
    feedback = ""
    sparql, columns, rows, error = "", [], [], None
    for n in range(1, rag.max_repairs + 2):
        t0 = time.perf_counter()
        sparql = rag.get_explicit_sparql(question, hints + feedback)
        llm_ms = _ms(t0)
        columns, rows, error, run_ms = _execute(rag, sparql)
        attempts.append(_attempt(n, sparql, rows, error, llm_ms, run_ms, feedback))
        if rows and not error:
            break
        template = REPAIR_ERROR if error else REPAIR_EMPTY
        feedback = template.format(sparql=sparql, error=error)
        unknown = unknown_iris(rag.graph, sparql)
        if unknown:
            feedback += REPAIR_UNKNOWN.format(iris=", ".join(f"<{i}>" for i in unknown))
        for wrong in class_mismatches(rag.graph, sparql):
            feedback += REPAIR_CLASS.format(**wrong)
        splits = split_contains(sparql) if not error else []
        if splits:
            feedback += _split_feedback(rag, splits)
    if rows and not error:
        split = _project_entity(sparql, list(mentions))
        if split:
            fixed, text, var = split
            fixed_columns, fixed_rows, fixed_error, run_ms = _execute(rag, fixed)
            if fixed_rows and not fixed_error:
                note = (
                    f"Hệ thống thêm ?{var} vào SELECT để tách kết quả theo từng thực thể trùng tên “{text}”."
                )
                attempts.append(
                    _attempt(len(attempts) + 1, fixed, fixed_rows, None, None, run_ms, note, "system")
                )
                sparql, columns, rows = fixed, fixed_columns, fixed_rows
    return {"sparql": sparql, "columns": columns, "rows": rows, "error": error, "attempts": attempts}


def from_cache(rag, sparql: str) -> dict:
    """SPARQL viết sẵn cho câu hỏi mẫu: chạy một lần, không gọi LLM."""
    columns, rows, error, run_ms = _execute(rag, sparql)
    return {
        "sparql": sparql,
        "columns": columns,
        "rows": rows,
        "error": error,
        "attempts": [_attempt(1, sparql, rows, error, None, run_ms, "", "cache")],
    }


def _check(label: str, status: str, detail: str) -> dict:
    return {"label": label, "status": status, "detail": detail}


def checks(sparql: str, mentions: list[dict], source: str, graph=None) -> list[dict]:
    """Danh sách kiểm tra truy vấn: status "ok" | "warn" | "fail" | "info"."""
    try:
        prepared = prepare(sparql)
    except QueryError as e:
        return [_check("Cú pháp SPARQL 1.1", "fail", str(e))]
    out = [_check("Cú pháp SPARQL 1.1", "ok", "rdflib phân tích được truy vấn, 19 prefix khai báo sẵn")]
    kind = prepared.algebra.name.removesuffix("Query").upper()
    read_only = kind in ("SELECT", "ASK")
    out.append(
        _check(
            "Chỉ đọc",
            "ok" if read_only else "fail",
            f"{kind}" + ("" if read_only else ": màn Hỏi đáp chỉ nhận SELECT hoặc ASK"),
        )
    )
    try:
        ensure_local(prepared)
        out.append(_check("Không gọi dữ liệu bên ngoài", "ok", "không có SERVICE, FROM"))
    except QueryError as e:
        out.append(_check("Không gọi dữ liệu bên ngoài", "fail", str(e)))
    limit = LIMIT_RE.search(sparql)
    if kind == "ASK":
        out.append(_check("Giới hạn số dòng", "ok", "ASK chỉ trả true/false"))
    elif limit:
        out.append(_check("Giới hạn số dòng", "ok", f"LIMIT {limit.group(1)}"))
    elif AGGREGATE_RE.search(sparql):
        out.append(_check("Giới hạn số dòng", "ok", "truy vấn tổng hợp (COUNT, MAX…)"))
    else:
        out.append(_check("Giới hạn số dòng", "warn", "không có LIMIT; giao diện chỉ hiện 200 dòng đầu"))
    if graph is not None and (FULL_IRI_RE.search(sparql) or PREFIXED_RE.search(sparql)):
        unknown = unknown_iris(graph, sparql)
        if unknown:
            names = ", ".join(i[len(VRES) :] for i in unknown)
            out.append(_check("IRI có trong graph", "fail", f"LLM tự đặt IRI không có trong graph: {names}"))
        else:
            out.append(_check("IRI có trong graph", "ok", "mọi IRI vres: trong truy vấn đều có thật"))
    if graph is not None and VALUES_RE.search(sparql):
        wrong = class_mismatches(graph, sparql)
        if wrong:
            detail = "; ".join(
                f"{w['iri'][len(VRES) :]} là {w['actual']}, không phải {w['expected']}" for w in wrong
            )
            out.append(_check("IRI đúng vai trò", "fail", detail))
        elif any(re.search(TYPE_OF.format(var=var), sparql) for var, _ in VALUES_RE.findall(sparql)):
            out.append(
                _check("IRI đúng vai trò", "ok", "lớp của IRI trong VALUES khớp với lớp truy vấn yêu cầu")
            )
    if mentions:
        iris = {c["iri"] for m in mentions for c in m["candidates"]}
        used = sorted(i for i in iris if f"<{i}>" in sparql or f"vres:{i[len(VRES) :]}" in sparql)
        if source == "cache":
            out.append(_check("Dùng IRI ở bước 1", "info", "SPARQL viết sẵn tự tìm thực thể theo nhãn"))
        elif used:
            out.append(
                _check(
                    "Dùng IRI ở bước 1", "ok", f"{len(used)}/{len(iris)} IRI đã nhận diện có trong truy vấn"
                )
            )
        else:
            out.append(
                _check(
                    "Dùng IRI ở bước 1", "warn", "LLM tự tìm thực thể theo nhãn thay vì dùng IRI đã nhận diện"
                )
            )
    for m in mentions:
        if len(m["candidates"]) > 1 and source != "cache":
            kept = _keeps_entity_column(sparql, [c["iri"] for c in m["candidates"]])
            if kept is not None:
                out.append(
                    _check(
                        "Phân biệt thực thể trùng tên",
                        "ok" if kept else "warn",
                        f"“{m['text']}” ứng với {len(m['candidates'])} thực thể; "
                        + (
                            "kết quả có cột cho biết dòng nào của ai"
                            if kept
                            else "kết quả gộp chung, không biết dòng nào của ai"
                        ),
                    )
                )
    return out


def _keeps_entity_column(sparql: str, iris: list[str]) -> bool | None:
    """Truy vấn có đưa biến của VALUES chứa các thực thể trùng tên ra SELECT không; None nếu không dùng VALUES."""
    select = SELECT_RE.search(sparql)
    for var, body in VALUES_RE.findall(sparql):
        if sum(f"<{i}>" in body for i in iris) >= 2:
            head = select.group(1) if select else ""
            return "*" in head or re.search(rf"\?{var}\b", head) is not None
    return None


# Bước ⑤: ghi chú đặt ở cuối prompt trả lời (LLM nhỏ dễ bỏ qua quy tắc nằm giữa một prompt dài)
EN_WORDS = {
    "what", "which", "who", "whom", "whose", "how", "when", "where", "why", "is", "are", "was", "were", "did",
    "does", "do", "the", "of", "in", "for", "to", "have", "has", "their", "many", "much", "most", "first", "and",
}  # fmt: skip
VI_WORDS = {
    "nao", "gi", "cua", "la", "co", "nhung", "bao", "nhieu", "cho", "duoc", "khong", "nhat", "o", "voi", "tung",
    "hien", "nay", "sau", "truoc", "thi", "va", "cac",
}  # fmt: skip


def question_language(question: str) -> str:
    """Trả "en" nếu câu hỏi viết bằng tiếng Anh (đếm từ chức năng, kể cả câu tiếng Việt gõ không dấu), còn lại "vi"."""
    words = [fold(w) for w in re.sub(r"[^\w\s]", " ", question).lower().split()]
    english = sum(w in EN_WORDS for w in words)
    vietnamese = sum(w in VI_WORDS for w in words)
    return "en" if english >= 2 and english > vietnamese else "vi"


def answer_notes(question: str, mentions: list[dict]) -> list[str]:
    """Ghi chú cho LLM viết câu trả lời: ngôn ngữ trả lời và các tên trùng nhiều thực thể."""
    notes = []
    for m in mentions:
        if len(m["candidates"]) > 1:
            names = "; ".join(c["label"] for c in m["candidates"])
            notes.append(
                f"Tên “{m['text']}” trong câu hỏi ứng với {len(m['candidates'])} thực thể khác nhau: {names}. "
                "Trả lời RIÊNG cho từng thực thể (cột chứa IRI của thực thể cho biết dòng nào của ai) và nêu điểm "
                "phân biệt có trong tên (ví dụ năm sinh); nếu bảng không có cột đó, nói rõ là kết quả gộp."
            )
    if question_language(question) == "en":
        notes.append(
            'IMPORTANT: the question is in English, so write both "answer" and "reasoning" in English '
            "(keep Vietnamese proper names as they are)."
        )
    return notes


def terms(view, graph, sparql: str) -> list[dict]:
    """Lớp và thuộc tính vio:/dbo: trong truy vấn, kèm số triple trong graph và bao nhiêu triple do suy luận."""
    out, seen = [], set()
    for prefix, local in TERM_RE.findall(sparql):
        iri = URIRef(PREFIXES[prefix] + local)
        if iri in seen:
            continue
        seen.add(iri)
        is_class = (iri, RDF.type, OWL.Class) in graph
        triples = graph.triples((None, RDF.type, iri)) if is_class else graph.triples((None, iri, None))
        total = inferred = 0
        for t in triples:
            total += 1
            inferred += t in view.inferred
        out.append(
            {
                "term": f"{prefix}:{local}",
                "iri": str(iri),
                "label": view.label(iri),
                "kind": "class" if is_class else "property",
                "total": total,
                "inferred": inferred,
            }
        )
        if len(out) == MAX_TERMS:
            break
    return out
