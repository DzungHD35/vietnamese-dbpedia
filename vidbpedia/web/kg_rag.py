"""Hỏi đáp trên knowledge graph: LLM sinh SPARQL, rdflib thực thi, LLM trả lời từ kết quả.

câu hỏi → schema → SPARQL (chỉ SELECT/ASK) → chạy; lỗi hoặc rỗng thì gửi lại cho LLM sửa → câu trả lời.
"""

import json
import os
import re
from collections import Counter
from typing import Any

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS
from rdflib.plugins.sparql import prepareQuery

from vidbpedia.kg.query import ensure_local
from vidbpedia.vocab import PREFIXES, VIO, VIP

PREFIX_BLOCK = "\n".join(f"PREFIX {p}: <{ns}>" for p, ns in PREFIXES.items())

# lớp đưa vào schema của prompt và các thuộc tính ngoài vio: vẫn liệt kê
SCHEMA_CLASSES = [
    "FootballPlayer",
    "FootballClub",
    "NationalFootballTeam",
    "Stadium",
    "University",
    "Province",
    "Country",
    "ClubStation",
    "NationalTeamStation",
    "YouthStation",
]
SCHEMA_EXTRA_PREDICATES = {
    "http://www.w3.org/2000/01/rdf-schema#label",
    "http://www.w3.org/2000/01/rdf-schema#comment",
    "http://www.w3.org/2004/02/skos/core#altLabel",
    "http://dbpedia.org/ontology/abstract",
    "http://www.w3.org/2002/07/owl#sameAs",
    "http://xmlns.com/foaf/0.1/homepage",
    "http://purl.org/dc/terms/subject",
}

SPARQL_GENERATION_TEMPLATE = """\
Nhiệm vụ: viết MỘT truy vấn SPARQL 1.1 để trả lời câu hỏi trên knowledge graph Vietnamese DBpedia
(cầu thủ, câu lạc bộ, sân vận động bóng đá, tỉnh thành và trường đại học Việt Nam, trích từ Wikipedia
tiếng Việt và Wikidata; liên kết owl:sameAs sang DBpedia tiếng Anh và Wikidata).

Schema (lớp, thuộc tính, số triple và ví dụ giá trị):
{schema}

Quy tắc:
- Chỉ dùng lớp và thuộc tính có trong schema. Chỉ viết SELECT hoặc ASK.
- Các PREFIX sau đã được khai báo sẵn, không cần viết lại: {prefix_names}.
- KHÔNG đoán IRI. Tìm thực thể theo nhãn hoặc tên khác (redirect), luôn kèm lớp, và ĐẶT BƯỚC TÌM NÀY
  TRONG MỘT SUBQUERY để nó chạy trước (rdflib áp FILTER sau khi join cả nhóm; viết phẳng có thể chậm 50 lần):
  {{ SELECT DISTINCT ?x WHERE {{ ?x a vio:FootballPlayer ; rdfs:label|skos:altLabel ?n .
                                FILTER(CONTAINS(LCASE(STR(?n)), "công phượng")) }} }}
  Giữ nguyên dấu tiếng Việt; dùng phần tên đặc trưng nhất. Dùng SELECT DISTINCT vì một thực thể có nhiều tên.
- Khi hiển thị tên, SELECT cả biến thực thể lẫn nhãn (ví dụ ?p ?name): giao diện cần IRI để nối tới trang
  tài nguyên và vẽ đồ thị bằng chứng. Nhãn lấy bằng rdfs:label với FILTER(lang(?label) = "vi").
- Quá trình thi đấu: cầu thủ vio:careerStation ?st ; ?st a vio:ClubStation (hoặc vio:NationalTeamStation,
  vio:YouthStation) ; vio:team ?doi ; vio:startYear ; vio:endYear ; vio:appearances ; vio:goals.
  Lối tắt: ?cauthu vio:playedFor ?doi ; ?doi vio:hasPlayer ?cauthu (đã suy luận sẵn).
- Tỉnh: vio:Province gồm cả tỉnh cũ (vio:FormerProvince: đã giải thể, sáp nhập năm 2025, hoặc thuộc chế độ trước).
  Tỉnh, thành phố hiện hành: ?p a vio:Province . FILTER NOT EXISTS {{ ?p a vio:FormerProvince }}
- Địa điểm quy về tỉnh: vio:province (ĐH, sân, CLB), vio:birthProvince (cầu thủ).
- Mọi lớp/thuộc tính vio: cũng có bản dbo: tương ứng (đã suy luận), nhưng hãy dùng vio:.
- Thuộc tính tùy chọn để trong OPTIONAL. Luôn thêm LIMIT (tối đa 50) trừ khi là truy vấn đếm.
- Khi hỏi về MỘT thực thể cụ thể, lấy thêm OPTIONAL {{ ?x dbo:abstract ?abstract }}
  vì nhiều thông tin chỉ nằm trong phần tóm tắt.
- Liên kết sang DBpedia EN: owl:sameAs có STRSTARTS(STR(?o), "http://dbpedia.org/resource/").
- Chỉ trả về truy vấn, không giải thích, không markdown.

Ví dụ:
# Quá trình thi đấu ở câu lạc bộ của Công Phượng?
SELECT DISTINCT ?t ?team ?start ?end ?apps ?goals WHERE {{
  {{ SELECT DISTINCT ?p WHERE {{ ?p a vio:FootballPlayer ; rdfs:label|skos:altLabel ?n .
                                FILTER(CONTAINS(LCASE(STR(?n)), "công phượng")) }} }}
  ?p vio:careerStation ?st . ?st a vio:ClubStation ; vio:team ?t .
  ?t rdfs:label ?team . FILTER(lang(?team) = "vi")
  OPTIONAL {{ ?st vio:startYear ?start }} OPTIONAL {{ ?st vio:endYear ?end }}
  OPTIONAL {{ ?st vio:appearances ?apps }} OPTIONAL {{ ?st vio:goals ?goals }}
}} ORDER BY ?start LIMIT 50

# (Nhiều bước) Câu lạc bộ nào có sân nhà ở Hà Nội? -> CLB → sân → tỉnh
SELECT DISTINCT ?c ?club ?s ?stadium WHERE {{
  {{ SELECT DISTINCT ?p WHERE {{ ?p a vio:Province ; rdfs:label ?pl . FILTER(CONTAINS(LCASE(STR(?pl)), "hà nội")) }} }}
  ?s vio:province ?p ; rdfs:label ?stadium . ?c a vio:FootballClub ; vio:ground ?s ; rdfs:label ?club .
  FILTER(lang(?club) = "vi" && lang(?stadium) = "vi")
}} LIMIT 50

# (Tổng hợp) Tỉnh nào có nhiều cầu thủ quê quán nhất?
SELECT ?prov ?province (COUNT(DISTINCT ?p) AS ?n) WHERE {{
  ?p a vio:FootballPlayer ; vio:birthProvince ?prov . ?prov rdfs:label ?province . FILTER(lang(?province) = "vi")
}} GROUP BY ?prov ?province ORDER BY DESC(?n) LIMIT 10

# (Nhiều bước) Cầu thủ sinh ở Nghệ An từng khoác áo đội tuyển quốc gia và hiện đá cho CLB nào?
SELECT DISTINCT ?p ?name ?c ?club WHERE {{
  {{ SELECT DISTINCT ?prov WHERE {{ ?prov a vio:Province ; rdfs:label ?pl . FILTER(CONTAINS(LCASE(STR(?pl)), "nghệ an")) }} }}
  ?p vio:birthProvince ?prov ; a vio:NationalTeamPlayer ; rdfs:label ?name .
  OPTIONAL {{ ?p vio:currentClub ?c . ?c rdfs:label ?club . FILTER(lang(?club) = "vi") }}
  FILTER(lang(?name) = "vi")
}} LIMIT 50

# Hiện có bao nhiêu tỉnh, thành phố trực thuộc trung ương?
SELECT (COUNT(DISTINCT ?p) AS ?n) WHERE {{ ?p a vio:Province . FILTER NOT EXISTS {{ ?p a vio:FormerProvince }} }}

# Đại học Cần Thơ thành lập năm nào và tương ứng với tài nguyên nào trên DBpedia?
SELECT DISTINCT ?u ?label ?year ?dbpedia ?abstract WHERE {{
  {{ SELECT DISTINCT ?u WHERE {{ ?u a vio:University ; rdfs:label ?l . FILTER(CONTAINS(LCASE(STR(?l)), "đại học cần thơ")) }} }}
  ?u rdfs:label ?label . FILTER(lang(?label) = "vi")
  OPTIONAL {{ ?u vio:foundingYear ?year }} OPTIONAL {{ ?u dbo:abstract ?abstract }}
  OPTIONAL {{ ?u owl:sameAs ?dbpedia . FILTER(STRSTARTS(STR(?dbpedia), "http://dbpedia.org/resource/")) }}
}} LIMIT 10
{feedback}
Câu hỏi: {question}
"""

ANSWER_TEMPLATE = """Bạn là trợ lý hỏi đáp trên knowledge graph Vietnamese DBpedia.
Trả lời câu hỏi bằng tiếng Việt, CHỈ dựa trên kết quả truy vấn SPARQL bên dưới.
- Kết quả đã được lọc đúng theo câu hỏi; mỗi dòng là một kết quả hợp lệ.
- Cột abstract là đoạn tóm tắt Wikipedia của thực thể, được dùng làm nguồn thông tin.
- Nếu nhiều kết quả: nêu tổng số trước, rồi liệt kê tối đa 10 mục.
- Nếu kết quả rỗng: nói rõ là dữ liệu hiện chưa có thông tin này, không tự bịa.
- Không nhắc tới SPARQL hay URI trừ khi người dùng hỏi về liên kết.

Suy luận theo các bước:
1. XÁC ĐỊNH: câu hỏi cần thông tin gì (thực thể, thuộc tính, phép đếm/so sánh).
2. TÌM: thông tin đó nằm ở dòng/cột nào của kết quả (trích giá trị cụ thể).
3. TÍNH: nếu cần đếm, so sánh, sắp xếp thì làm từng bước.
4. KIỂM TRA: câu trả lời có khớp câu hỏi và có căn cứ trong kết quả không.

Trả về DUY NHẤT một JSON hợp lệ, không markdown:
{{"reasoning": "các bước 1-4, mỗi bước một dòng, bắt đầu bằng tên bước", "answer": "câu trả lời cuối cùng"}}

Câu hỏi: {question}
Truy vấn đã chạy:
{sparql}
Kết quả ({n_rows} dòng, hiển thị tối đa {shown}):
{rows}
"""


class SparqlBasedKGRAG:
    """Hỏi đáp ngôn ngữ tự nhiên trên rdflib.Graph bằng SPARQL do LLM sinh ra."""

    def __init__(
        self,
        graph: Graph,
        model: str | None = None,
        client: Any = None,
        max_rows_for_answer: int = 30,
        max_repairs: int = 1,
    ):
        self.graph = graph
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.5")
        self._client = client
        self.max_rows_for_answer = max_rows_for_answer
        self.max_repairs = max_repairs
        self._schema: str | None = None

    @property
    def client(self):
        if self._client is None:
            if not os.getenv("OPENAI_API_KEY"):
                raise RuntimeError("Chưa có OPENAI_API_KEY. Thêm vào file .env rồi khởi động lại endpoint.")
            from openai import OpenAI

            self._client = OpenAI()
        return self._client

    def _complete(self, prompt: str) -> str:
        kwargs = {}
        # gpt-5* và o-series chỉ nhận temperature mặc định
        if not re.match(r"(gpt-5|o\d)", self.model):
            kwargs["temperature"] = 0
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        return (resp.choices[0].message.content or "").strip()

    def _short(self, term) -> str:
        s = str(term)
        for p, ns in PREFIXES.items():
            if s.startswith(ns) and re.fullmatch(r"[\w\-]*", s[len(ns) :]):
                return f"{p}:{s[len(ns) :]}"
        return f"<{s}>"

    def _describe_value(self, o) -> str:
        if isinstance(o, Literal):
            text = str(o)[:40].replace("\n", " ")
            if o.language:
                return f'"{text}"@{o.language}'
            if o.datatype:
                return f'"{text}"^^{self._short(o.datatype)}'
            return f'"{text}"'
        label = self.graph.value(o, RDFS.label) if isinstance(o, URIRef) else None
        return f"{self._short(o)} ({label})" if label is not None else self._short(o)

    def get_schema(self) -> str:
        """Lớp chính, thuộc tính vio: theo lớp kèm số triple và một giá trị ví dụ; vip: chỉ ghi số lượng."""
        if self._schema is not None:
            return self._schema
        lines = ["Lớp (số thực thể):"]
        present = []
        for name in SCHEMA_CLASSES:
            n = len(set(self.graph.subjects(RDF.type, VIO[name])))
            if n:
                present.append(name)
                lines.append(f"  vio:{name}  ({n})")
        lines.append("Thuộc tính theo lớp (số triple; ví dụ giá trị):")
        vip_props = set()
        for name in present:
            pred_counts: Counter = Counter()
            examples: dict = {}
            for s in set(self.graph.subjects(RDF.type, VIO[name])):
                for p, o in self.graph.predicate_objects(s):
                    ps = str(p)
                    if ps.startswith(str(VIP)):
                        vip_props.add(p)
                        continue
                    if not (ps.startswith(str(VIO)) or ps in SCHEMA_EXTRA_PREDICATES):
                        continue
                    pred_counts[p] += 1
                    if p == OWL.sameAs:
                        if str(o).startswith(PREFIXES["dbr"]):
                            examples[p] = self._short(o)
                    elif p not in examples or (isinstance(o, Literal) and o.language == "vi"):
                        examples[p] = self._describe_value(o)
            lines.append(f"  vio:{name}:")
            for p, n in pred_counts.most_common():
                lines.append(f"    {self._short(p)}  ({n}; vd {examples.get(p, '')})")
        lines.append(
            f"Ngoài ra có {len(vip_props)} thuộc tính thô vip:* trích nguyên văn từ infobox (không cần dùng)."
        )
        self._schema = "\n".join(lines)
        return self._schema

    @staticmethod
    def _extract_query(text: str) -> str:
        m = re.search(r"```(?:sparql)?\s*(.*?)```", text, re.S | re.I)
        query = (m.group(1) if m else text).strip()
        # PREFIX_BLOCK đã khai báo mọi prefix; bỏ PREFIX do LLM tự thêm để không trùng
        return re.sub(r"(?im)^\s*PREFIX\s+\w*:\s*<[^>]*>\s*$", "", query).strip()

    def _validate(self, query: str) -> str:
        full = f"{PREFIX_BLOCK}\n{query}"
        prepared = prepareQuery(full)
        if prepared.algebra.name not in ("SelectQuery", "AskQuery"):
            raise ValueError("Chỉ cho phép truy vấn SELECT hoặc ASK.")
        ensure_local(prepared)  # LLM (hay prompt injection) không được làm máy chủ gửi request ra ngoài
        return full

    def get_explicit_sparql(self, question: str, feedback: str = "") -> str:
        prompt = SPARQL_GENERATION_TEMPLATE.format(
            schema=self.get_schema(),
            prefix_names=", ".join(PREFIXES),
            feedback=feedback,
            question=question,
        )
        return self._extract_query(self._complete(prompt))

    def run_sparql(self, query: str) -> tuple[list[str], list[dict[str, str]]]:
        full = self._validate(query)
        result = self.graph.query(full)
        if result.type == "ASK":
            return ["answer"], [{"answer": str(bool(result.askAnswer))}]
        columns = [str(v) for v in result.vars]
        rows = []
        for row in result:
            rows.append(
                {c: ("" if row[i] is None else self._format_cell(row[i])) for i, c in enumerate(columns)}
            )
        return columns, rows

    @staticmethod
    def _format_cell(term) -> str:
        if isinstance(term, URIRef):
            from urllib.parse import unquote

            return unquote(str(term))
        return str(term)

    @staticmethod
    def _parse_answer(text: str) -> tuple[str, str]:
        """Tách {"reasoning", "answer"} từ phản hồi LLM; nếu không phải JSON thì coi cả đoạn là câu trả lời."""
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                data = json.loads(m.group(0))
                return str(data.get("answer", "")).strip() or text, str(data.get("reasoning", "")).strip()
            except json.JSONDecodeError:
                pass
        return text, ""

    def generate_and_run(self, question: str) -> dict[str, Any]:
        """Sinh và chạy SPARQL, cho LLM sửa nếu lỗi hoặc rỗng; dùng cho SPARQL mode.

        → {sparql, columns, rows, attempts, error}
        """
        feedback = ""
        sparql, columns, rows, error = "", [], [], None
        attempts = 0
        for attempts in range(1, self.max_repairs + 2):
            sparql = self.get_explicit_sparql(question, feedback)
            try:
                columns, rows = self.run_sparql(sparql)
                error = None
            except Exception as e:
                error = str(e)
                feedback = f"\nLần trước bạn viết:\n{sparql}\nTruy vấn này lỗi: {error}\nHãy sửa lại.\n"
                continue
            if rows:
                break
            feedback = (
                f"\nLần trước bạn viết:\n{sparql}\nTruy vấn chạy được nhưng không có kết quả. "
                "Hãy thử nới điều kiện (từ khóa ngắn hơn, bỏ lọc ngôn ngữ, dùng OPTIONAL).\n"
            )

        return {
            "sparql": sparql,
            "columns": [] if error else columns,
            "rows": [] if error else rows,
            "attempts": attempts,
            "error": error,
        }

    def query(self, question: str) -> dict[str, Any]:
        """generate_and_run rồi để LLM trả lời: → {answer, reasoning, sparql, columns, rows, attempts, error}."""
        run = self.generate_and_run(question)
        if run["error"]:
            return {
                **run,
                "answer": f"Không tạo được truy vấn hợp lệ cho câu hỏi này. Lỗi cuối: {run['error']}",
                "reasoning": "",
            }

        sparql, rows = run["sparql"], run["rows"]
        shown = rows[: self.max_rows_for_answer]
        rows_text = "\n".join(" | ".join(f"{k}={v[:800]}" for k, v in r.items()) for r in shown) or "(rỗng)"
        answer, reasoning = self._parse_answer(
            self._complete(
                ANSWER_TEMPLATE.format(
                    question=question, sparql=sparql, n_rows=len(rows), shown=len(shown), rows=rows_text
                )
            )
        )
        return {**run, "answer": answer, "reasoning": reasoning}
