"""SPARQL: /api/sparql (cho giao diện), /api/sparql/examples và /sparql (endpoint chuẩn SPARQL 1.1 Protocol).

Phần chạy truy vấn, chặn FROM/SERVICE và chọn định dạng kết quả dùng lại `vidbpedia.kg.query` và
`vidbpedia.web.endpoint` của team, nên /sparql ở đây hành xử đúng như /sparql của máy chủ Gradio:
chỉ truy vấn đọc, không gửi request ra ngoài, `?format=` kiểu DBpedia hoặc header Accept.

rdflib không có timeout cho truy vấn: truy vấn nặng (nhiều biến tự do, không LIMIT) có thể chạy rất lâu.
"""

import os
import time
from urllib.parse import unquote

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from rdflib import Graph, URIRef

from ui.api.links import build_links
from ui.api.paths import WEB_INDEX
from ui.api.state import kg
from vidbpedia.kg.query import QueryError, execute, run
from vidbpedia.web.endpoint import MIME_FORMATS, USAGE, preferred_formats, read_query
from vidbpedia.web.examples import EXAMPLE_QUERIES

router = APIRouter()

MAX_ROWS = 1000
CORS = {"Access-Control-Allow-Origin": "*"}


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
        result = run(graph, query, allow_remote=False)
        if result.type == "ASK":
            columns, rows = ["answer"], [{"answer": str(bool(result.askAnswer)).lower()}]
        elif result.type in ("CONSTRUCT", "DESCRIBE"):
            columns = ["s", "p", "o"]
            rows = [dict(zip(columns, map(_cell, t), strict=True)) for t in result.graph]
        else:
            columns = [str(v) for v in result.vars]
            rows = [{c: _cell(row[i]) for i, c in enumerate(columns)} for row in result]
    except QueryError as e:  # sai cú pháp, FROM/SERVICE, hoặc lỗi khi chạy: báo cho người dùng, không trả 500
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


def _answer(query: str, formats: list[str], inference: bool) -> Response:
    graph, error = _graph(inference)
    if graph is None:
        return Response(error, status_code=503, media_type="text/plain; charset=utf-8", headers=CORS)
    try:
        body, mime = execute(graph, query, formats, allow_remote=False)
    except QueryError as e:
        return Response(str(e), status_code=400, media_type="text/plain; charset=utf-8", headers=CORS)
    return Response(body, media_type=f"{mime}; charset=utf-8", headers={**CORS, "Vary": "Accept"})


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
    query = await read_query(request)
    if not query or not query.strip():
        return Response(USAGE, status_code=400, media_type="text/plain; charset=utf-8", headers=CORS)
    formats = preferred_formats(request)
    explicit = accept.strip() and "*/*" not in accept and not request.query_params.get("format")
    if not formats and explicit:
        offered = ", ".join(sorted(MIME_FORMATS))
        return Response(f"Chỉ hỗ trợ: {offered}", status_code=406, media_type="text/plain", headers=CORS)
    inference = request.query_params.get("inference", "true").lower() != "false"
    # rdflib chạy đồng bộ và tốn CPU: đưa sang thread để không chặn các request khác
    return await run_in_threadpool(_answer, query, formats, inference)
