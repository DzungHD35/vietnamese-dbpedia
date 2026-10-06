"""URI dereference được theo mẫu của DBpedia.

/resource/{tên} trả 303 tới trang HTML (/?resource={tên}) hoặc tới /data/{tên}.ttl|nt|jsonld|rdf tuỳ header
Accept; /ontology/{thuật ngữ} trả định nghĩa của lớp hoặc thuộc tính vio:.
"""

from urllib.parse import quote

from fastapi import Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from rdflib import Graph

from vidbpedia.crawl.iri import URL_SAFE
from vidbpedia.vocab import VIO, bind_prefixes

RDF_FORMATS = {
    "ttl": ("turtle", "text/turtle"),
    "nt": ("nt", "application/n-triples"),
    "jsonld": ("json-ld", "application/ld+json"),
    "rdf": ("xml", "application/rdf+xml"),
}
ACCEPT = [
    ("text/turtle", "ttl"),
    ("application/x-turtle", "ttl"),
    ("application/n-triples", "nt"),
    ("application/ld+json", "jsonld"),
    ("application/rdf+xml", "rdf"),
]
MAX_INCOMING = 2000


def negotiate(accept):
    """Header Accept → phần mở rộng RDF; None nghĩa là trình duyệt, trả trang HTML."""
    accept = (accept or "").lower()
    return next((ext for mime, ext in ACCEPT if mime in accept), None)


def describe(graph, iri):
    """Mọi triple có iri là chủ ngữ, cùng tối đa MAX_INCOMING triple có iri là tân ngữ."""
    out = bind_prefixes(Graph())
    for p, o in graph.predicate_objects(iri):
        out.add((iri, p, o))
    for i, (s, p) in enumerate(graph.subject_predicates(iri)):
        if i >= MAX_INCOMING:
            break
        out.add((s, p, iri))
    return out


def add_routes(app, view):
    """Gắn route vào FastAPI; gọi trước khi mount Gradio ở '/' để không bị route của Gradio che."""

    def not_found():
        return PlainTextResponse("Không tìm thấy tài nguyên.", status_code=404)

    def page_url(iri):
        return "/?resource=" + quote(view.local(iri), safe=URL_SAFE)

    @app.get("/resource/{name:path}", include_in_schema=False)
    def resource(name: str, request: Request):
        iri = view.resolve(name)
        if iri is None:
            return not_found()
        ext = negotiate(request.headers.get("accept"))
        target = f"/data/{quote(view.local(iri), safe=URL_SAFE)}.{ext}" if ext else page_url(iri)
        return RedirectResponse(target, status_code=303, headers={"Vary": "Accept"})

    @app.get("/page/{name:path}", include_in_schema=False)
    def page(name: str):
        iri = view.resolve(name)
        return RedirectResponse(page_url(iri), status_code=303) if iri is not None else not_found()

    @app.get("/data/{name:path}", include_in_schema=False)
    def data(name: str):
        base, _, ext = name.rpartition(".")
        iri = view.resolve(base) if ext in RDF_FORMATS else None
        if iri is None:
            return not_found()
        fmt, mime = RDF_FORMATS[ext]
        body = describe(view.g, iri).serialize(format=fmt)
        return Response(
            body.encode("utf-8"),
            media_type=f"{mime}; charset=utf-8",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    @app.get("/ontology/{term}", include_in_schema=False)
    def ontology(term: str):
        iri = VIO[term]
        out = bind_prefixes(Graph())
        for p, o in view.g.predicate_objects(iri):
            out.add((iri, p, o))
        if not len(out):
            return PlainTextResponse("Không có thuật ngữ này trong ontology vio:.", status_code=404)
        return Response(
            out.serialize(format="turtle").encode("utf-8"), media_type="text/turtle; charset=utf-8"
        )

    return app
