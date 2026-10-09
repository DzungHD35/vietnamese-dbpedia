"""Test /api/map."""


def test_map_points_and_successions(client):
    d = client.get("/api/map").json()
    kinds = {p["node"]["kind"] for p in d["points"]}
    assert {"prov", "uni", "stadium"} <= kinds
    assert not any(p["node"]["cls"] == "Quốc gia" for p in d["points"])  # nước không phải điểm trên bản đồ
    assert any(p["former"] for p in d["points"]) and any(not p["former"] for p in d["points"])
    assert all(8 < p["lat"] < 24 and 102 < p["lon"] < 110 for p in d["points"] if p["node"]["kind"] == "prov")
    ids = {p["node"]["id"] for p in d["points"]}
    assert d["successions"] and all(s["from"] in ids and s["to"] in ids for s in d["successions"])
    assert len({(s["from"], s["to"]) for s in d["successions"]}) == len(d["successions"])  # đã gộp nghịch đảo
    assert any(s["year"] == 2025 for s in d["successions"])


def test_shapes_match_provinces_and_merge_into_34(client):
    geoms = client.get("/api/map/shapes").json()["objects"]["provinces"]["geometries"]
    assert len(geoms) == 64 and all(
        g["id"] for g in geoms
    )  # 63 tỉnh + Côn Đảo (mảnh riêng của Bà Rịa – Vũng Tàu)
    stats = {p["id"]: p for p in client.get("/api/map/provinces").json()}
    finals = {stats[g["id"]]["final"] for g in geoms}
    assert len(finals) == 34 and not any(stats[f]["former"] for f in finals)
    assert stats["Bình_Định_(tỉnh)"]["final"] == "Gia_Lai" and stats["Hà_Tây_(tỉnh)"]["final"] == "Hà_Nội"


def test_group_counts_are_unions(client):
    stats = {p["id"]: p for p in client.get("/api/map/provinces").json()}
    hn = stats["Hà_Nội"]
    assert hn["groupCounts"]["players"] >= hn["counts"]["players"]
    assert all(p["groupCounts"] is None for p in stats.values() if p["former"])


def test_province_detail_after_and_before(client):
    d = client.get("/api/map/province/Gia_Lai", params={"era": "after"}).json()
    assert {m["id"] for m in d["members"]} >= {"Gia_Lai", "Bình_Định_(tỉnh)"}
    assert len(d["players"]) == min(d["counts"]["players"], 12)
    assert "Bình_Định_(tỉnh)" in d["sparql"]
    b = client.get("/api/map/province/Bình_Định_(tỉnh)", params={"era": "before"}).json()
    assert (
        b["former"]
        and b["final"]["id"] == "Gia_Lai"
        and [m["id"] for m in b["members"]] == ["Bình_Định_(tỉnh)"]
    )
    assert client.get("/api/map/province/Nguyễn_Công_Phượng").status_code == 404
