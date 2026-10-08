"""SPARQL: /api/sparql (cho giao diện), /api/sparql/examples và /sparql (endpoint chuẩn SPARQL 1.1 Protocol).

rdflib không có timeout cho truy vấn: truy vấn nặng (nhiều biến tự do, không LIMIT) có thể chạy rất lâu.
"""

import os
import time
from urllib.parse import parse_qs, unquote

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from rdflib import Graph, URIRef
from rdflib.query import Result

from ui.api.links import build_links
from ui.api.paths import WEB_INDEX
from ui.api.state import kg
from vidbpedia.vocab import PREFIXES
from vidbpedia.web.examples import EXAMPLE_QUERIES

router = APIRouter()

MAX_ROWS = 1000
CORS = {"Access-Control-Allow-Origin": "*"}
# Accept → (định dạng của rdflib, Content-Type); thứ tự là thứ tự ưu tiên khi Accept không nói rõ
TABLE_FORMATS = {
    "application/sparql-results+json": "json",
    "application/sparql-results+xml": "xml",
    "text/csv": "csv",
}
GRAPH_FORMATS = {
    "text/turtle": "turtle",
    "application/rdf+xml": "xml",
    "application/n-triples": "nt",
}


class SparqlBody(BaseModel):
    query: str
    inference: bool = True


def _cell(term) -> str:
    """Ô kết quả: IRI giải mã %XX để khớp với id thực thể, literal giữ nguyên chuỗi."""
    if term is None:
        return ""
    return unquote(str(term)) if isinstance(term, URIRef) else str(term)


def _graph(inference: bool) -> tuple[Graph | None, str | None]:
    if inference:
        return kg.graph, None
    if not kg.asserted_ready.is_set():
        return None, "Graph chỉ khai báo đang được nạp, thử lại sau ít giây."
    if kg.asserted is None:
        return None, kg.asserted_error or "Chưa nạp được graph chỉ khai báo."
    return kg.asserted, None


def _run(query: str, inference: bool) -> dict:
    out = {"type": None, "columns": [], "rows": [], "links": {}, "total": 0, "ms": 0, "error": None}
    if not query.strip():
        return {**out, "error": "Truy vấn trống."}
    graph, error = _graph(inference)
    if graph is None:
        return {**out, "error": error}
    start = time.perf_counter()
    try:
        result = graph.query(query, initNs=PREFIXES)
        if result.type == "ASK":
            columns, rows = ["answer"], [{"answer": str(bool(result.askAnswer)).lower()}]
        elif result.type in ("CONSTRUCT", "DESCRIBE"):
            columns = ["s", "p", "o"]
            rows = [dict(zip(columns, map(_cell, t), strict=True)) for t in result.graph]
        else:
            columns = [str(v) for v in result.vars]
            rows = [{c: _cell(row[i]) for i, c in enumerate(columns)} for row in result]
    except Exception as e:  # lỗi cú pháp hoặc lỗi khi thực thi: báo cho người dùng chứ không trả 500
        return {**out, "error": str(e), "ms": round((time.perf_counter() - start) * 1000)}
    ms = round((time.perf_counter() - start) * 1000)
    shown = rows[:MAX_ROWS]
    return {
        "type": result.type,
        "columns": columns,
        "rows": shown,
        "links": build_links(shown),
        "total": len(rows),
        "ms": ms,
        "error": None,
    }


@router.get("/api/sparql/examples")
def examples():
    return [{"name": name, "query": query} for name, query in EXAMPLE_QUERIES.items()]


@router.post("/api/sparql")
def sparql_ui(body: SparqlBody):
    return _run(body.query, body.inference)


def _negotiate(accept: str, formats: dict[str, str]) -> tuple[str, str] | None:
    """Chọn (Content-Type, định dạng rdflib) theo Accept; không nói rõ thì lấy định dạng đầu tiên."""
    wanted = []
    for part in accept.split(","):
        mime, *params = (x.strip() for x in part.split(";"))
        q = next(
            (float(p[2:]) for p in params if p.startswith("q=") and p[2:].replace(".", "").isdigit()), 1.0
        )
        wanted.append((q, mime.lower()))
    first = next(iter(formats))
    for _, mime in sorted(wanted, key=lambda w: -w[0]):
        if mime in formats:
            return mime, formats[mime]
        if mime in ("*/*", ""):
            return first, formats[first]
    return None


async def _read_query(request: Request) -> str | None:
    if request.method == "GET":
        return request.query_params.get("query")
    body = (await request.body()).decode("utf-8")
    ctype = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if ctype == "application/sparql-query":
        return body
    return (parse_qs(body).get("query") or [None])[0]


def _answer(query: str, accept: str, inference: bool) -> Response:
    graph, error = _graph(inference)
    if graph is None:
        return Response(error, status_code=503, media_type="text/plain", headers=CORS)
    try:
        result: Result = graph.query(query, initNs=PREFIXES)
        is_graph = result.type in ("CONSTRUCT", "DESCRIBE")
        chosen = _negotiate(accept, GRAPH_FORMATS if is_graph else TABLE_FORMATS)
        if chosen is None:
            offered = ", ".join(GRAPH_FORMATS if is_graph else TABLE_FORMATS)
            return Response(f"Chỉ hỗ trợ: {offered}", status_code=406, headers=CORS)
        mime, fmt = chosen
        payload = result.serialize(format=fmt)
    except Exception as e:
        return Response(f"Lỗi truy vấn: {e}", status_code=400, media_type="text/plain", headers=CORS)
    return Response(payload, media_type=mime, headers=CORS)


@router.api_route("/sparql", methods=["GET", "POST", "OPTIONS"], include_in_schema=False)
async def sparql_endpoint(request: Request):
    """Endpoint SPARQL chuẩn: `GET ?query=…`, `POST` form hoặc `application/sparql-query`.

    `?inference=false` chạy trên triple khai báo (ngoài chuẩn, để tải đúng kết quả đang xem ở trang SPARQL).
    """
    if request.method == "OPTIONS":
        headers = {
            **CORS,
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
        return Response(status_code=204, headers=headers)
    accept = request.headers.get("accept", "")
    if request.method == "GET" and "text/html" in accept and os.path.exists(WEB_INDEX):
        return FileResponse(WEB_INDEX)  # trình duyệt mở /sparql?query=… thì thấy trang SPARQL của UI
    query = await _read_query(request)
    if not query or not query.strip():
        return Response("Thiếu tham số query.", status_code=400, media_type="text/plain", headers=CORS)
    inference = request.query_params.get("inference", "true").lower() != "false"
    return await run_in_threadpool(_answer, query, accept, inference)
