"""Test kiểm tra mâu thuẫn: triple sai loại bị reasoner bắt, triple đúng loại thì không."""

import pytest

from ui.api.presets import CONSISTENCY_PRESETS

CP = "Nguyễn_Công_Phượng"


def check(client, s, p, o):
    return client.post("/api/consistency", json={"subject": s, "predicate": p, "object": o})


def test_domain_violation_is_explained(client):
    d = check(client, CP, "vio:ground", "Sân_vận_động_Pleiku").json()
    assert not d["consistent"] and d["triples"] > 0
    [c] = d["conflicts"]
    assert c["individual"]["id"] == CP and {x["qname"] for x in c["classes"]} == {
        "vio:Person",
        "vio:Organisation",
    }
    assert d["axioms"]["domain"]["qname"] == "vio:Organisation"
    assert {(g["node"]["id"], g["cls"]["qname"]) for g in d["gained"]} == {(CP, "vio:Organisation")}


def test_type_triple_on_class(client):
    d = check(client, "Câu_lạc_bộ_bóng_đá_Hoàng_Anh_Gia_Lai", "rdf:type", "vio:Province").json()
    assert not d["consistent"] and d["conflicts"]


def test_wrong_fact_of_right_kind_is_consistent(client):
    d = check(client, CP, "vio:birthProvince", "Gia_Lai").json()
    assert d["consistent"] and not d["conflicts"] and not d["errors"]


@pytest.mark.parametrize(
    "s, p, o",
    [
        ("Không_có_thực_thể_này", "vio:ground", "Gia_Lai"),
        (CP, "vio:khongCo", "Gia_Lai"),
        (CP, "ground", "Gia_Lai"),
    ],
)
def test_bad_input_is_400(client, s, p, o):
    r = check(client, s, p, o)
    assert r.status_code == 400 and r.json()["detail"]


def test_presets_resolve(client):
    d = client.get("/api/consistency/presets").json()
    assert set(d) == set(CONSISTENCY_PRESETS)
    assert all(len(d[k]) == len(v) for k, v in CONSISTENCY_PRESETS.items())
