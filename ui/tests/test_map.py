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
