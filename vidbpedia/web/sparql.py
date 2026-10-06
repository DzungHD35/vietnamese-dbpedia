"""Nạp dataset và chạy truy vấn cho tab SPARQL."""

import os

import pandas as pd
from rdflib import Graph

from vidbpedia.common import read_json
from vidbpedia.vocab import PREFIXES

RDF_FORMATS = {".ttl": "turtle", ".nt": "nt", ".rdf": "xml"}
MAX_CELL = 100  # ký tự tối đa mỗi ô trong bảng kết quả


class SparqlService:
    def __init__(self, dataset_file):
        fmt = RDF_FORMATS.get(os.path.splitext(dataset_file)[1], "turtle")
        self.graph = Graph().parse(dataset_file, format=fmt)
        stats_file = os.path.splitext(dataset_file)[0] + "_stats.json"
        self.stats = (
            read_json(stats_file) if os.path.exists(stats_file) else {"total_triples": len(self.graph)}
        )

    def run(self, query, output="table"):
        """→ (kết quả, trạng thái); kết quả là DataFrame nếu output="table", chuỗi nếu "json" hoặc "csv"."""
        if not query or not query.strip():
            return None, "Truy vấn trống."
        try:
            result = self.graph.query(query, initNs=PREFIXES)
        except Exception as e:  # lỗi cú pháp hoặc lỗi khi thực thi
            return None, f"Lỗi: {e}"

        if result.type in ("CONSTRUCT", "DESCRIBE"):
            if output != "table":
                return result.graph.serialize(format="turtle"), f"{len(result.graph)} triple"
            rows = [{"s": str(s), "p": str(p), "o": str(o)} for s, p, o in result.graph]
        elif output != "table":
            return result.serialize(format=output).decode("utf-8"), _status(len(result))
        elif result.type == "ASK":
            rows = [{"answer": str(result.askAnswer).lower()}]
        else:
            columns = [str(v) for v in result.vars]
            rows = [{c: _cell(row[i]) for i, c in enumerate(columns)} for row in result]
        return (pd.DataFrame(rows) if rows else None), _status(len(rows))


def _cell(term):
    if term is None:
        return ""
    value = str(term)
    return value if len(value) <= MAX_CELL else value[: MAX_CELL - 3] + "..."


def _status(n):
    return f"Tìm thấy {n} kết quả" if n else "Không có kết quả"
