"""Tab Tài nguyên và các route Linked Data (resource_page.py, linked_data.py).

pytest tests/test_resource_page.py -v
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDFS

from vidbpedia.common import DATASET
from vidbpedia.vocab import DBO, DBR, VIO, VRES
from vidbpedia.web.linked_data import add_routes, negotiate
from vidbpedia.web.resource_page import ResourceView

CP = VRES["Nguyễn_Công_Phượng"]


@pytest.fixture(scope="module")
def view(graph):
    return ResourceView.from_files(graph, DATASET + ".nt")


@pytest.fixture(scope="module")
def client(view):
    return TestClient(add_routes(FastAPI(), view))


def test_search_ignores_diacritics_and_uses_alt_labels(view):
    assert view.search("cong phuong")[0][1] == "Nguyễn_Công_Phượng"
    assert view.search("HÀNG ĐẪY")[0][1] == "Sân_vận_động_Hàng_Đẫy"
    assert view.search("") == []


def test_resolve_local_names(view):
    assert view.resolve("Nguyễn_Công_Phượng") == CP
    assert view.resolve("Nguyễn Công Phượng") == CP
    assert view.resolve(str(CP)) == CP
    assert view.resolve("Hà_Tây_(tỉnh)") is not None
    assert view.resolve("Không_có_trang_này") is None


def test_page_like_dbpedia(view):
    page = view.render(CP, "http://127.0.0.1:7860")
    assert "Nguyễn Công Phượng" in page
    # liên kết LOD ra ngoài và dữ liệu tải về
    assert f'href="{DBR["Nguyễn_Công_Phượng"]}"' in page
    assert 'href="http://www.wikidata.org/entity/Q18045362"' in page
    assert "/data/Nguy%E1%BB%85n_C%C3%B4ng_Ph%C6%B0%E1%BB%A3ng.ttl" in page
    # cây phân lớp có cả lớp khai báo và lớp DBpedia suy ra
    assert "vio:FootballPlayer" in page and "dbo:SoccerPlayer" in page and "suy luận" in page
    # cây quan hệ: chặng thi đấu hiện thành đội kèm năm, số trận
    assert "Mito HollyHock" in page and "2016–2016" in page
    # đồ thị lân cận và bảng thuộc tính
    assert "<svg" in page and "rv-edge-inf" in page  # playedFor có được nhờ suy luận
    assert "dbo:abstract" in page and "vip:" in page


def test_class_tree_marks_asserted_and_inferred(view):
    tree = view._class_tree(CP)
    assert tree.index("dbo:Person") < tree.index("vio:Person") < tree.index("vio:FootballPlayer")
    assert "khai báo" in tree


def test_reverse_links_of_province(view):
    page = view.render(VRES["Nghệ_An"])
    assert "là " in page and "vio:birthProvince" in page
    assert "Nguyễn Công Phượng" in page


def test_unknown_resource(view):
    assert "Không tìm thấy" in view.render(None)


def test_content_negotiation():
    assert negotiate("text/turtle") == "ttl"
    assert negotiate("application/ld+json, */*;q=0.1") == "jsonld"
    assert negotiate("text/html,application/xhtml+xml") is None
    assert negotiate(None) is None


def test_dereference_redirects(client):
    r = client.get("/resource/Nguyễn_Công_Phượng", headers={"Accept": "text/turtle"}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].endswith(".ttl") and r.headers["location"].startswith("/data/")
    r = client.get("/resource/Nguyễn_Công_Phượng", headers={"Accept": "text/html"}, follow_redirects=False)
    assert r.status_code == 303 and "resource=" in r.headers["location"]
    assert client.get("/resource/Không_có_trang_này").status_code == 404


@pytest.mark.parametrize("ext, fmt", [("ttl", "turtle"), ("nt", "nt"), ("jsonld", "json-ld"), ("rdf", "xml")])
def test_data_formats_parse_back(client, ext, fmt):
    r = client.get(f"/data/Nguyễn_Công_Phượng.{ext}")
    assert r.status_code == 200
    g = Graph().parse(data=r.text, format=fmt)
    assert (CP, OWL.sameAs, DBR["Nguyễn_Công_Phượng"]) in g
    assert (CP, RDFS.label, None) in g
    assert any(True for _ in g.triples((None, VIO.birthProvince, None)))


def test_data_follows_redirect_and_includes_inferred(client):
    r = client.get("/resource/Nguyễn_Công_Phượng", headers={"Accept": "text/turtle"})
    g = Graph().parse(data=r.text, format="turtle")
    assert (CP, URIRef(str(DBO) + "wikiPageID"), None) in g
    assert any(True for _ in g.triples((CP, VIO.playedFor, None)))


def test_ontology_term(client):
    r = client.get("/ontology/FootballPlayer")
    assert r.status_code == 200
    g = Graph().parse(data=r.text, format="turtle")
    assert (VIO.FootballPlayer, RDFS.subClassOf, DBO.SoccerPlayer) in g
    assert client.get("/ontology/KhongCo").status_code == 404
