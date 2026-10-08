"""SPARQL endpoint theo SPARQL 1.1 Protocol.

GET /sparql?query=…, POST dạng form (query=…) hoặc POST thân là truy vấn (application/sparql-query).
Định dạng kết quả chọn theo tham số format (như DBpedia: format=json, csv, turtle…) hoặc header Accept:
JSON, XML, CSV cho SELECT/ASK; Turtle, N-Triples, JSON-LD, RDF/XML cho CONSTRUCT/DESCRIBE. Các prefix của
dự án được khai báo sẵn. Chỉ nhận truy vấn đọc; FROM và SERVICE bị chặn để máy chủ không gửi request ra ngoài.
"""

from urllib.parse import parse_qs

from fastapi import Request
from fastapi.responses import PlainTextResponse, Response
from starlette.concurrency import run_in_threadpool

from vidbpedia.kg.query import GRAPH_FORMATS, RESULT_FORMATS, QueryError, execute

MIME_FORMATS = {
    mime: name for formats in (RESULT_FORMATS, GRAPH_FORMATS) for name, (_, mime) in formats.items()
}
MIME_FORMATS.update({"application/json": "json", "application/xml": "xml", "application/x-turtle": "turtle"})

USAGE = """Thiếu tham số query. Ví dụ:
  curl -H "Accept: text/csv" --data-urlencode "query=SELECT ?x WHERE { ?x a dbo:Stadium } LIMIT 5" \\
       http://127.0.0.1:7860/sparql
"""


def preferred_formats(request):
    """Tên định dạng theo thứ tự ưu tiên, lấy từ tham số format hoặc từ q của header Accept."""
    fmt = request.query_params.get("format")
    if fmt:
        return [MIME_FORMATS.get(fmt.lower(), fmt.lower())]
    ranked = []
    for i, part in enumerate((request.headers.get("accept") or "").split(",")):
        mime, *params = [x.strip().lower() for x in part.split(";")]
        q = 1.0
        for p in params:
            if p.startswith("q="):
                try:
                    q = float(p[2:])
                except ValueError:
                    q = 0.0
        if mime in MIME_FORMATS and q > 0:
            ranked.append((-q, i, MIME_FORMATS[mime]))
    return [name for _, _, name in sorted(ranked)]


async def read_query(request):
    if request.method == "GET":
        return request.query_params.get("query")
    ctype = request.headers.get("content-type", "").split(";")[0].strip().lower()
    body = (await request.body()).decode("utf-8")
    if ctype == "application/sparql-query":
        return body
    if ctype == "application/x-www-form-urlencoded":
        return parse_qs(body).get("query", [None])[0]
    return request.query_params.get("query")


def add_routes(app, graph):
    @app.api_route("/sparql", methods=["GET", "POST"], include_in_schema=False)
    async def sparql(request: Request):
        text = await read_query(request)
        if not text or not text.strip():
            return PlainTextResponse(USAGE, status_code=400)
        try:
            # rdflib chạy đồng bộ và tốn CPU: đưa sang thread để không chặn giao diện
            body, mime = await run_in_threadpool(
                execute, graph, text, preferred_formats(request), allow_remote=False
            )
        except QueryError as e:
            return PlainTextResponse(str(e), status_code=400)
        return Response(
            body,
            media_type=f"{mime}; charset=utf-8",
            headers={"Access-Control-Allow-Origin": "*", "Vary": "Accept"},
        )

    return app
