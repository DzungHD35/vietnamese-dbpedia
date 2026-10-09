"""Test SPARQL: /api/sparql cho giao diện và /sparql theo SPARQL 1.1 Protocol."""

import json

import pytest

from ui.api.presets import SPARQL_LADDER
from ui.api.state import kg
from vidbpedia.web.examples import EXAMPLE_QUERIES

COUNT_PLAYED = "SELECT (COUNT(*) AS ?n) WHERE { ?s vio:playedFor ?o }"


def run(client, query, inference=True):
    return client.post("/api/sparql", json={"query": query, "inference": inference}).json()


def test_inference_switch_changes_count(client):
    assert kg.asserted_ready.wait(120) and kg.asserted is not None
    assert int(run(client, COUNT_PLAYED)["rows"][0]["n"]) > 0
    d = run(client, COUNT_PLAYED, inference=False)
    assert d["error"] is None and d["rows"][0]["n"] == "0"


def test_ui_result_shape_and_links(client):
    d = run(client, "SELECT ?s WHERE { ?s a vio:University } LIMIT 5")
    assert d["type"] == "SELECT" and d["columns"] == ["s"] and d["total"] == 5 and d["ms"] >= 0
    assert all(cell in d["links"] for cell in (r["s"] for r in d["rows"]))
    assert {n["kind"] for n in d["links"].values()} == {"uni"}


def test_ask_and_construct(client):
    assert run(client, "ASK { ?s ?p ?o }")["rows"] == [{"answer": "true"}]
    d = run(client, "CONSTRUCT { ?s a vio:Stadium } WHERE { ?s a vio:Stadium } LIMIT 3")
    assert d["type"] == "CONSTRUCT" and d["columns"] == ["s", "p", "o"] and d["total"] == 3


def test_syntax_error_is_reported_not_raised(client):
    r = client.post("/api/sparql", json={"query": "SELEC broken"})
    assert r.status_code == 200 and r.json()["error"] and r.json()["rows"] == []
    assert run(client, "  ")["error"] == "Truy vấn trống."


def test_row_limit(client):
    d = run(client, "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 1500")
    assert d["total"] == 1500 and len(d["rows"]) == 1000


def test_examples_all_run(client):
    examples = client.get("/api/sparql/examples").json()
    assert len(examples) == len(SPARQL_LADDER) + len(EXAMPLE_QUERIES)
    for e in examples:
        d = run(client, e["query"])
        assert d["error"] is None and d["total"] > 0, e["name"]


def test_standard_endpoint_ask_json(client):
    r = client.get(
        "/sparql", params={"query": "ASK{?s ?p ?o}"}, headers={"Accept": "application/sparql-results+json"}
    )
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/sparql-results+json")
    assert r.headers["access-control-allow-origin"] == "*"
    assert json.loads(r.text)["boolean"] is True


def test_standard_endpoint_default_is_json(client):
    r = client.get("/sparql", params={"query": "SELECT ?s WHERE { ?s a vio:Stadium } LIMIT 2"})
    assert len(r.json()["results"]["bindings"]) == 2


@pytest.mark.parametrize(
    ("accept", "marker"),
    [
        ("application/sparql-results+xml", "<sparql"),
        ("text/csv", "s\r\n"),
    ],
)
def test_standard_endpoint_formats(client, accept, marker):
    r = client.get(
        "/sparql",
        params={"query": "SELECT ?s WHERE { ?s a vio:Stadium } LIMIT 2"},
        headers={"Accept": accept},
    )
    assert r.status_code == 200 and marker in r.text


def test_standard_endpoint_post_forms(client):
    q = "ASK{?s ?p ?o}"
    form = client.post("/sparql", data={"query": q})
    assert form.json()["boolean"] is True
    direct = client.post("/sparql", content=q, headers={"Content-Type": "application/sparql-query"})
    assert direct.json()["boolean"] is True


def test_standard_endpoint_construct_is_turtle(client):
    r = client.get(
        "/sparql", params={"query": "CONSTRUCT { ?s a vio:Stadium } WHERE { ?s a vio:Stadium } LIMIT 2"}
    )
    assert r.headers["content-type"].startswith("text/turtle") and "Stadium" in r.text


def test_standard_endpoint_errors(client):
    assert client.get("/sparql").status_code == 400
    assert client.get("/sparql", params={"query": "SELEC"}).status_code == 400
    r = client.get("/sparql", params={"query": "ASK{?s ?p ?o}"}, headers={"Accept": "image/png"})
    assert r.status_code == 406
    assert client.options("/sparql").status_code == 204


def test_standard_endpoint_inference_off(client):
    assert kg.asserted_ready.wait(120) and kg.asserted is not None
    r = client.get("/sparql", params={"query": COUNT_PLAYED, "inference": "false"})
    assert r.json()["results"]["bindings"][0]["n"]["value"] == "0"
    r = client.get("/sparql", params={"query": COUNT_PLAYED})
    assert int(r.json()["results"]["bindings"][0]["n"]["value"]) > 0


SERVICE_QUERY = "SELECT * WHERE { SERVICE <http://127.0.0.1:9/sparql> { ?s ?p ?o } } LIMIT 1"
FROM_QUERY = "SELECT * FROM <http://127.0.0.1:9/x.ttl> WHERE { ?s ?p ?o } LIMIT 1"


def test_remote_queries_are_blocked_everywhere(client):
    """FROM và SERVICE khiến rdflib gửi HTTP ra ngoài: chặn ở cả endpoint chuẩn, API giao diện và Hỏi đáp."""
    for query in (SERVICE_QUERY, FROM_QUERY):
        r = client.get("/sparql", params={"query": query})
        assert r.status_code == 400 and "Không hỗ trợ" in r.text
        assert "Không hỗ trợ" in run(client, query)["error"]
        assert client.post("/api/ask/asserted", json={"sparql": query}).json()["status"] == "error"
    with pytest.raises(ValueError):
        kg.rag.run_sparql(SERVICE_QUERY)  # đường LLM sinh SPARQL dùng cùng lớp chặn


def test_xml_keeps_zero_and_false(client):
    """Serializer XML của rdflib 7.6 ghi literal 0/false thành rỗng; dùng results_xml của team thì không."""
    r = client.get(
        "/sparql",
        params={"query": 'SELECT ?z ?f WHERE { BIND(0 AS ?z) BIND("false"^^xsd:boolean AS ?f) }'},
        headers={"Accept": "application/sparql-results+xml"},
    )
    assert r.status_code == 200 and ">0<" in r.text and ">false<" in r.text


def test_csv_for_ask_falls_back_to_json(client):
    r = client.get("/sparql", params={"query": "ASK{?s ?p ?o}"}, headers={"Accept": "text/csv"})
    assert r.status_code == 200 and r.json()["boolean"] is True


def test_format_param_like_dbpedia(client):
    q = "SELECT ?s WHERE { ?s a vio:Stadium } LIMIT 2"
    r = client.get("/sparql", params={"query": q, "format": "csv"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv") and "vary" in r.headers
    r = client.get("/sparql", params={"query": q, "format": "xml"})
    assert r.headers["content-type"].startswith("application/sparql-results+xml")


def test_examples_put_ladder_first(client):
    ex = client.get("/api/sparql/examples").json()
    assert [e["name"] for e in ex[: len(SPARQL_LADDER)]] == [n for n, _ in SPARQL_LADDER]
    assert len({e["group"] for e in ex}) == 2
