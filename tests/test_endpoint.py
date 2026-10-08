"""SPARQL endpoint /sparql (endpoint.py) và lệnh python -m vidbpedia query (kg/query.py).

pytest tests/test_endpoint.py -v
"""

import csv
import io
import json
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rdflib import RDF, Graph
from rdflib.query import Result

from vidbpedia.kg import query as cli
from vidbpedia.vocab import DBO
from vidbpedia.web.endpoint import add_routes

COUNT_PLAYERS = "SELECT (COUNT(?x) AS ?n) WHERE { ?x a dbo:SoccerPlayer }"
CONSTRUCT_CP = "CONSTRUCT { vres:Nguyễn_Công_Phượng ?p ?o } WHERE { vres:Nguyễn_Công_Phượng ?p ?o }"
JSON = {"Accept": "application/sparql-results+json"}


@pytest.fixture(scope="module")
def client(graph):
    return TestClient(add_routes(FastAPI(), graph))


def players(graph):
    return str(len(set(graph.subjects(RDF.type, DBO.SoccerPlayer))))


def count(resp):
    return int(resp.json()["results"]["bindings"][0]["n"]["value"])


def test_get_post_form_and_post_direct(client):
    get = client.get("/sparql", params={"query": COUNT_PLAYERS}, headers=JSON)
    form = client.post("/sparql", data={"query": COUNT_PLAYERS}, headers=JSON)
    direct = client.post(
        "/sparql",
        content=COUNT_PLAYERS.encode(),
        headers={**JSON, "Content-Type": "application/sparql-query"},
    )
    for resp in (get, form, direct):
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/sparql-results+json")
        assert resp.headers["access-control-allow-origin"] == "*"
        assert count(resp) >= 550


def test_result_format_by_accept_and_format_param(client):
    q = "SELECT ?s WHERE { ?s a vio:Stadium } LIMIT 3"
    as_csv = client.get("/sparql", params={"query": q}, headers={"Accept": "text/csv"})
    assert as_csv.headers["content-type"].startswith("text/csv")
    assert list(csv.reader(io.StringIO(as_csv.text)))[0] == ["s"]
    as_xml = client.get("/sparql", params={"query": q, "format": "xml"})
    assert as_xml.headers["content-type"].startswith("application/sparql-results+xml")
    ranked = client.get(
        "/sparql", params={"query": q}, headers={"Accept": "text/csv;q=0.5, application/json"}
    )
    assert ranked.headers["content-type"].startswith("application/sparql-results+json")
    default = client.get("/sparql", params={"query": q})
    assert len(default.json()["results"]["bindings"]) == 3


def test_xml_results_parse_back_with_falsy_values(client):
    q = 'SELECT ?zero ?no ?name WHERE { BIND(0 AS ?zero) BIND(false AS ?no) BIND("Hà Nội"@vi AS ?name) }'
    xml = client.get("/sparql", params={"query": q}, headers={"Accept": "application/sparql-results+xml"})
    row = list(Result.parse(io.BytesIO(xml.content), format="xml"))[0]
    assert (row.zero.toPython(), row.no.toPython(), row.name.language) == (0, False, "vi")
    ask = client.get("/sparql", params={"query": "ASK { ?x a vio:Nothing }", "format": "xml"})
    assert Result.parse(io.BytesIO(ask.content), format="xml").askAnswer is False


def test_ask_and_construct(client):
    ask = client.get("/sparql", params={"query": "ASK { vres:Nguyễn_Công_Phượng vio:playedFor ?t }"})
    assert ask.json()["boolean"] is True
    ttl = client.get("/sparql", params={"query": CONSTRUCT_CP}, headers={"Accept": "text/turtle"})
    assert ttl.headers["content-type"].startswith("text/turtle")
    assert len(Graph().parse(data=ttl.text, format="turtle")) > 20
    # định dạng kết quả bảng không áp được cho CONSTRUCT: trả Turtle mặc định
    fallback = client.get("/sparql", params={"query": CONSTRUCT_CP}, headers=JSON)
    assert fallback.headers["content-type"].startswith("text/turtle")


@pytest.mark.parametrize(
    "query",
    [
        "",
        "SELEC ?x WHERE { ?x ?p ?o }",
        "INSERT DATA { vres:A vio:b vres:C }",
        "SELECT * FROM <http://example.org/data.ttl> WHERE { ?s ?p ?o }",
        "SELECT * WHERE { SERVICE <https://dbpedia.org/sparql> { ?s ?p ?o } }",
    ],
)
def test_rejected_queries(client, query):
    assert client.get("/sparql", params={"query": query}).status_code == 400


def test_cli_table_and_formats(graph, monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_graph", lambda path: graph)
    monkeypatch.setattr(sys, "argv", ["query", COUNT_PLAYERS])
    cli.main()
    out = capsys.readouterr().out
    assert "(1 dòng)" in out and players(graph) in out

    monkeypatch.setattr(sys, "argv", ["query", "--format", "json", "﻿ASK { ?x a vio:Province }"])
    cli.main()
    assert json.loads(capsys.readouterr().out)["boolean"] is True

    monkeypatch.setattr(sys, "argv", ["query", "SELEC ?x"])
    with pytest.raises(SystemExit, match="Lỗi cú pháp"):
        cli.main()


def test_cli_against_endpoint(client, graph, monkeypatch, capsys):
    def post(url, data, headers, timeout):
        return client.post("/sparql", data=data, headers=headers)

    monkeypatch.setattr(cli.requests, "post", post)
    monkeypatch.setattr(sys, "argv", ["query", "--endpoint", "http://test/sparql", COUNT_PLAYERS])
    cli.main()
    assert players(graph) in capsys.readouterr().out

    ordered = 'SELECT ?x WHERE { VALUES ?x { "b" "c" "a" } } ORDER BY DESC(?x)'
    monkeypatch.setattr(sys, "argv", ["query", "--endpoint", "http://test/sparql", ordered])
    cli.main()
    assert capsys.readouterr().out.split("\n")[2:5] == ["c", "b", "a"]

    monkeypatch.setattr(
        sys, "argv", ["query", "--endpoint", "http://test/sparql", "--format", "nt", CONSTRUCT_CP]
    )
    cli.main()
    assert len(Graph().parse(data=capsys.readouterr().out, format="nt")) > 20
