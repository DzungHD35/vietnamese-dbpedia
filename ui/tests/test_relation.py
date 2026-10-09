"""Test /api/entity/{id}/tree: cây quan hệ 3 bước, cùng dữ liệu với mục Cây quan hệ của trang tài nguyên."""

from vidbpedia.web.resource_page import MAX_CHILDREN, MAX_DEPTH


def _depth(node, d=0):
    return max([d] + [_depth(c, d + 1) for g in node["groups"] for c in g["children"]])


def test_relation_tree_player(client):
    d = client.get("/api/entity/Nguyễn_Công_Phượng/tree").json()
    assert d["root"]["id"] == "Nguyễn_Công_Phượng" and d["maxDepth"] == MAX_DEPTH
    props = {g["prop"]: g for g in d["groups"]}
    career = props["vio:careerStation"]
    assert career["direction"] == "out" and career["total"] == 11
    assert career["more"] == max(0, 11 - MAX_CHILDREN[1]) and len(career["children"]) == min(
        11, MAX_CHILDREN[1]
    )
    first = career["children"][0]  # chặng đội trẻ xếp trước: có năm nhưng không có số trận
    assert first["node"]["kind"] == "club" and first["station"] and "đội trẻ" in first["note"]
    assert any("trận" in ch["note"] and "bàn" in ch["note"] for ch in career["children"])
    # đội → sân → tỉnh: không sâu hơn MAX_DEPTH
    assert 2 <= _depth({"groups": d["groups"]}) <= MAX_DEPTH
    assert (
        "vio:birthProvince" in props
        and props["vio:birthProvince"]["children"][0]["node"]["label"] == "Nghệ An"
    )


def test_relation_tree_club_has_incoming(client):
    d = client.get("/api/entity/Câu_lạc_bộ_bóng_đá_Hoàng_Anh_Gia_Lai/tree").json()
    incoming = [g for g in d["groups"] if g["direction"] == "in"]
    assert incoming and any(g["prop"] == "vio:playedFor" for g in incoming)
    ground = next(g for g in d["groups"] if g["prop"] == "vio:ground")
    stadium = ground["children"][0]
    assert stadium["node"]["kind"] == "stadium"
    assert any(g["prop"] == "vio:province" for g in stadium["groups"])  # sân → tỉnh


def test_relation_tree_404(client):
    assert client.get("/api/entity/Không_có_thực_thể_này/tree").status_code == 404


def test_static_graph_matches_gradio(client):
    from ui.api.state import kg

    d = client.get("/api/entity/Nguyễn_Công_Phượng/graph").json()
    iri = kg.view.resolve("Nguyễn_Công_Phượng")
    assert d["html"] == kg.view._graph_svg(iri)  # đúng HTML của trang Gradio
    assert "<svg" in d["html"] and "rv-edge-inf" in d["html"] and "rv-legend" in d["html"]
    asserted = client.get("/api/entity/Nguyễn_Công_Phượng/graph", params={"inferred": "false"}).json()["html"]
    assert "rv-edge-inf" not in asserted and "playedFor" not in asserted and "birthProvince" in asserted
    assert client.get("/api/entity/Không_có/graph").status_code == 404
