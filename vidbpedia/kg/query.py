"""Chạy truy vấn SPARQL từ terminal; phần chạy và xuất kết quả dùng chung với route /sparql.

python -m vidbpedia query "SELECT ..."                     # nạp data/vietnamese_dbpedia.nt rồi chạy
python -m vidbpedia query -f truy_van.rq --format csv
echo "ASK { ... }" | python -m vidbpedia query -
python -m vidbpedia query --endpoint http://127.0.0.1:7860/sparql "SELECT ..."
"""

import argparse
import io
import sys
import xml.etree.ElementTree as ET

import requests
from rdflib import BNode, Graph, URIRef
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.parserutils import CompValue
from rdflib.query import Result

from vidbpedia.common import DATASET
from vidbpedia.vocab import PREFIXES, bind_prefixes

# tên định dạng → (định dạng của rdflib, MIME)
RESULT_FORMATS = {  # SELECT, ASK
    "json": ("json", "application/sparql-results+json"),
    "xml": ("xml", "application/sparql-results+xml"),
    "csv": ("csv", "text/csv"),
}
GRAPH_FORMATS = {  # CONSTRUCT, DESCRIBE
    "turtle": ("turtle", "text/turtle"),
    "nt": ("nt", "application/n-triples"),
    "json-ld": ("json-ld", "application/ld+json"),
    "rdf": ("xml", "application/rdf+xml"),
}


class QueryError(ValueError):
    """Truy vấn sai cú pháp, lỗi khi chạy, hoặc dùng mệnh đề không được phép."""


def execute(graph, text, formats=(), allow_remote=True):
    """→ (bytes, MIME). formats: tên định dạng theo thứ tự ưu tiên; không cái nào hợp thì JSON hoặc Turtle."""
    return serialize(run(graph, text, allow_remote), formats)


def run(graph, text, allow_remote=True):
    """allow_remote=False chặn FROM và SERVICE, hai mệnh đề khiến rdflib gửi request ra ngoài."""
    query = prepare(text, allow_remote)
    try:
        result = graph.query(query)
        if result.type == "SELECT":
            result.bindings  # rdflib chạy SELECT lười; ép chạy ở đây để lỗi rơi vào QueryError
        return result
    except Exception as e:
        raise QueryError(f"Lỗi khi chạy truy vấn: {e}") from e


def prepare(text, allow_remote=True):
    try:
        # BOM: PowerShell thêm vào khi pipe sang stdin, Notepad thêm vào đầu file
        query = prepareQuery(text.lstrip("﻿"), initNs=PREFIXES)
    except Exception as e:
        raise QueryError(f"Lỗi cú pháp: {e}") from e
    return query if allow_remote else ensure_local(query)


def ensure_local(query):
    """Chặn FROM và SERVICE trên truy vấn đã prepare: hai mệnh đề khiến rdflib gửi request ra ngoài."""
    if query.algebra.get("datasetClause"):
        raise QueryError("Không hỗ trợ FROM / FROM NAMED: endpoint chỉ có một graph mặc định.")
    if _uses_service(query.algebra):
        raise QueryError("Không hỗ trợ SERVICE (truy vấn liên kết sang endpoint khác).")
    return query


def serialize(result, formats=()):
    if result.type in ("CONSTRUCT", "DESCRIBE"):
        name = next((f for f in formats if f in GRAPH_FORMATS), "turtle")
        fmt, mime = GRAPH_FORMATS[name]
        return bind_prefixes(result.graph).serialize(format=fmt, encoding="utf-8"), mime
    usable = [f for f in formats if f in RESULT_FORMATS and not (f == "csv" and result.type == "ASK")]
    name = usable[0] if usable else "json"
    fmt, mime = RESULT_FORMATS[name]
    if name == "xml":
        return results_xml(result), mime
    return result.serialize(format=fmt, encoding="utf-8"), mime


def results_xml(result):
    """SPARQL Query Results XML Format. Serializer XML của rdflib 7.6 ghi literal 0 và false thành rỗng."""
    root = ET.Element("sparql", xmlns="http://www.w3.org/2005/sparql-results#")
    head = ET.SubElement(root, "head")
    if result.type == "ASK":
        ET.SubElement(root, "boolean").text = str(result.askAnswer).lower()
    else:
        for var in result.vars:
            ET.SubElement(head, "variable", name=str(var))
        results = ET.SubElement(root, "results")
        for row in result:
            item = ET.SubElement(results, "result")
            for var, term in zip(result.vars, row):
                if term is None:
                    continue
                binding = ET.SubElement(item, "binding", name=str(var))
                if isinstance(term, URIRef):
                    ET.SubElement(binding, "uri").text = str(term)
                elif isinstance(term, BNode):
                    ET.SubElement(binding, "bnode").text = str(term)
                elif term.language:
                    ET.SubElement(binding, "literal", {"xml:lang": term.language}).text = str(term)
                elif term.datatype:
                    ET.SubElement(binding, "literal", datatype=str(term.datatype)).text = str(term)
                else:
                    ET.SubElement(binding, "literal").text = str(term)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _uses_service(node):
    if isinstance(node, CompValue):
        return node.name == "ServiceGraphPattern" or any(_uses_service(v) for v in node.values())
    if isinstance(node, (list, tuple)):
        return any(_uses_service(v) for v in node)
    return False


def as_table(result):
    """Kết quả dạng chữ cho terminal: bảng cho SELECT, true/false cho ASK, Turtle cho CONSTRUCT/DESCRIBE."""
    if result.type in ("CONSTRUCT", "DESCRIBE"):
        return bind_prefixes(result.graph).serialize(format="turtle")
    if result.type == "ASK":
        return str(result.askAnswer).lower()
    nm = bind_prefixes(Graph()).namespace_manager
    names = [str(v) for v in result.vars]
    # tự in bảng vì serializer "txt" của rdflib sắp xếp lại các dòng, làm mất ORDER BY
    rows = [
        ["" if t is None else t.n3(nm) if isinstance(t, URIRef) else str(t) for t in row] for row in result
    ]
    widths = [max([len(n), *(len(r[i]) for r in rows)]) for i, n in enumerate(names)]

    def line(cells):
        return " | ".join(c.ljust(w) for c, w in zip(cells, widths)).rstrip()

    return "\n".join(
        [line(names), "-+-".join("-" * w for w in widths), *map(line, rows), f"({len(rows)} dòng)"]
    )


def ask_endpoint(url, text, fmt):
    """Gửi truy vấn tới endpoint theo SPARQL 1.1 Protocol (POST dạng form) → chuỗi để in ra."""
    if fmt == "table":
        accept = "application/sparql-results+json, text/turtle;q=0.9"
    else:
        accept = {**RESULT_FORMATS, **GRAPH_FORMATS}[fmt][1]
    resp = requests.post(url, data={"query": text}, headers={"Accept": accept}, timeout=120)
    if resp.status_code >= 400:
        raise QueryError(f"HTTP {resp.status_code}: {resp.text.strip()[:500]}")
    ctype = resp.headers.get("content-type", "")
    if fmt == "table" and ctype.startswith("application/sparql-results+json"):
        return as_table(Result.parse(io.BytesIO(resp.content), format="json"))
    return resp.content.decode("utf-8")


def load_graph(path):
    return Graph().parse(path, format="nt" if path.endswith(".nt") else "turtle")


def read_query(args):
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            return f.read()
    if args.query == "-":
        return sys.stdin.read()
    return args.query


def main():
    ap = argparse.ArgumentParser(description="Chạy truy vấn SPARQL trên Vietnamese DBpedia")
    ap.add_argument("query", nargs="?", help='truy vấn SPARQL, hoặc "-" để đọc từ stdin')
    ap.add_argument("-f", "--file", help="đọc truy vấn từ file")
    ap.add_argument("--format", default="table", choices=["table", *RESULT_FORMATS, *GRAPH_FORMATS])
    ap.add_argument("--dataset", default=DATASET + ".nt")
    ap.add_argument(
        "--endpoint", help="gửi tới SPARQL endpoint thay vì nạp dataset, ví dụ http://127.0.0.1:7860/sparql"
    )
    args = ap.parse_args()
    text = read_query(args)
    if not text or not text.strip():
        ap.error("chưa có truy vấn")

    try:
        if args.endpoint:
            out = ask_endpoint(args.endpoint, text, args.format)
        elif args.format == "table":
            out = as_table(run(load_graph(args.dataset), text))
        else:
            out = execute(load_graph(args.dataset), text, [args.format])[0].decode("utf-8")
    except (QueryError, requests.RequestException) as e:
        sys.exit(str(e))
    print(out)


if __name__ == "__main__":
    main()
