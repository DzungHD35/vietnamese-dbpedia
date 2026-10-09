"""Bản đồ: /api/map (điểm, quan hệ kế thừa), /api/map/shapes (ranh giới tỉnh), /api/map/provinces, /api/map/province/…"""

import json
import os
import re
from functools import lru_cache

from fastapi import APIRouter, HTTPException
from rdflib.namespace import RDF

from ui.api import serialize
from ui.api.routes.entity import number
from ui.api.state import kg, resolve_or_404
from vidbpedia.vocab import VIO, VRES, WGS84
from vidbpedia.web.resource_page import fold

router = APIRouter(prefix="/api")


def _coords(iri) -> tuple[float, float] | None:
    g = kg.graph
    lat = number(g.value(iri, VIO.latitude) or g.value(iri, WGS84.lat))
    lon = number(g.value(iri, VIO.longitude) or g.value(iri, WGS84["long"]))
    return (lat, lon) if lat is not None and lon is not None else None


@lru_cache(maxsize=1)
def _map() -> dict:
    view, g = kg.view, kg.graph
    located = {
        s for p in (VIO.latitude, WGS84.lat) for s in g.subjects(p, None) if str(s).startswith(str(VRES))
    }
    located -= set(g.subjects(RDF.type, VIO.Country))  # quốc gia có toạ độ nhưng không phải điểm cần chấm
    former = set(g.subjects(RDF.type, VIO.FormerProvince))
    points = []
    for s in sorted(located, key=str):
        xy = _coords(s)
        if xy is not None:
            points.append(
                {"node": serialize.node(view, s), "lat": xy[0], "lon": xy[1], "former": s in former}
            )
    on_map = {p["node"]["iri"] for p in points}

    # successor và predecessor là nghịch đảo: gộp thành các cặp (từ → đến) không trùng
    pairs: dict[tuple, bool] = {}  # (từ, đến) → có triple khai báo (không phải suy luận) hay không
    for s, o in g.subject_objects(VIO.successor):
        pairs[(s, o)] = pairs.get((s, o), False) or (s, VIO.successor, o) not in view.inferred
    for s, o in g.subject_objects(VIO.predecessor):
        pairs[(o, s)] = pairs.get((o, s), False) or (s, VIO.predecessor, o) not in view.inferred
    successions = [
        {
            "from": serialize.node_id(view, a),
            "to": serialize.node_id(view, b),
            "year": serialize.year(g.value(a, VIO.dissolutionYear)),
            "inferred": not asserted,
        }
        for (a, b), asserted in sorted(pairs.items(), key=lambda kv: str(kv[0]))
        if str(a) in on_map and str(b) in on_map
    ]
    return {"points": points, "successions": successions, "successionsTotal": len(pairs)}


@router.get("/map")
def map_data():
    return _map()


# ---- Ranh giới tỉnh: 63 tỉnh (geoBoundaries VNM ADM1, 2008, public domain; có Hoàng Sa, Trường Sa) ----
# Ranh giới sau sáp nhập 2025 KHÔNG tải từ ngoài: frontend gộp các tỉnh cũ theo `final` (vio:successor trong graph).
SHAPES_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "geo", "vn-provinces-2008.topo.json"
)
SHAPE_ALIASES = {"Côn Đảo": "Bà_Rịa_–_Vũng_Tàu"}  # huyện đảo, bộ ranh giới tách thành mảnh riêng
MAX_LIST = 12


def _key(label: str) -> str:
    """Tên tỉnh → khoá so khớp: bỏ dấu, bỏ phần trong ngoặc và tiền tố 'tỉnh'/'thành phố'."""
    t = re.sub(r"\(.*?\)", "", fold(label)).strip()
    t = re.sub(r"^(tinh|thanh pho)\s+", "", t)
    return re.sub(r"[^a-z]", "", t)


def _final(iri):
    """Tỉnh cũ → tỉnh hiện hành theo chuỗi vio:successor (Hà Tây → Hà Nội, Bình Định → Gia Lai…)."""
    g, seen = kg.graph, set()
    while (iri, RDF.type, VIO.FormerProvince) in g and iri not in seen:
        seen.add(iri)
        nxt = sorted(g.objects(iri, VIO.successor), key=str)
        if not nxt:
            break
        iri = nxt[0]
    return iri


def _members(g) -> dict:
    """{tỉnh: {"players", "clubs", "unis"}}: cầu thủ theo quê, CLB theo tỉnh hoặc tỉnh của sân nhà, trường ĐH."""
    out: dict = {}

    def add(p, kind, x):
        out.setdefault(p, {"players": set(), "clubs": set(), "unis": set()})[kind].add(x)

    for x, p in g.subject_objects(VIO.birthProvince):
        if (x, RDF.type, VIO.FootballPlayer) in g:
            add(p, "players", x)
    for x in g.subjects(RDF.type, VIO.FootballClub):
        for p in g.objects(x, VIO.province):
            add(p, "clubs", x)
        for st in g.objects(x, VIO.ground):
            for p in g.objects(st, VIO.province):
                add(p, "clubs", x)
    for x in g.subjects(RDF.type, VIO.University):
        for p in g.objects(x, VIO.province):
            add(p, "unis", x)
    return out


@lru_cache(maxsize=1)
def _provinces() -> dict:
    """{iri: {node, former, year, final, members}} cho mọi vio:Province."""
    view, g = kg.view, kg.graph
    members = _members(g)
    empty = {"players": set(), "clubs": set(), "unis": set()}
    return {
        p: {
            "node": serialize.node(view, p),
            "former": (p, RDF.type, VIO.FormerProvince) in g,
            "year": serialize.year(g.value(p, VIO.dissolutionYear)),
            "final": _final(p),
            "members": members.get(p, empty),
        }
        for p in sorted(g.subjects(RDF.type, VIO.Province), key=str)
    }


@lru_cache(maxsize=1)
def _shapes() -> dict:
    """TopoJSON 63 tỉnh, mỗi hình gắn `id` (local name trong vres:) khớp theo tên với tỉnh trong graph."""
    with open(SHAPES_FILE, encoding="utf-8") as f:
        topo = json.load(f)
    by_key: dict[str, list] = {}
    for p, info in _provinces().items():
        by_key.setdefault(_key(info["node"]["label"]), []).append((info["former"], p))
    for geom in topo["objects"]["provinces"]["geometries"]:
        name = geom["properties"]["name"]
        if name in SHAPE_ALIASES:
            iri = kg.view.resolve(SHAPE_ALIASES[name])
        else:
            cands = sorted(
                by_key.get(_key(name), []), key=lambda c: (c[0], str(c[1]))
            )  # ưu tiên tỉnh hiện hành
            iri = cands[0][1] if cands else None
        geom["id"] = serialize.node_id(kg.view, iri) if iri is not None else None
    return topo


@router.get("/map/shapes")
def map_shapes():
    return _shapes()


def _union(group) -> dict:
    provinces = _provinces()
    acc = {"players": set(), "clubs": set(), "unis": set()}
    for p in group:
        for k in acc:
            acc[k] |= provinces[p]["members"][k]
    return acc


@router.get("/map/provinces")
def map_provinces():
    """Mỗi tỉnh (kể cả tỉnh cũ): tỉnh hiện hành nó thuộc về, số liệu riêng (`counts`) và, với tỉnh hiện hành,
    số liệu sau khi gộp các tỉnh cũ (`groupCounts`, hợp tập hợp nên cầu thủ có hai quê không bị đếm hai lần)."""
    view, provinces = kg.view, _provinces()
    groups: dict = {}
    for p, info in provinces.items():
        groups.setdefault(info["final"], []).append(p)
    return [
        {
            "id": info["node"]["id"],
            "label": info["node"]["label"],
            "former": info["former"],
            "year": info["year"],
            "final": serialize.node_id(view, info["final"]),
            "counts": {k: len(v) for k, v in info["members"].items()},
            "groupCounts": None
            if info["former"]
            else {k: len(v) for k, v in _union(groups.get(p, [p])).items()},
        }
        for p, info in provinces.items()
    ]


def _top(nodes, key=None) -> list[dict]:
    view = kg.view
    ranked = sorted(nodes, key=key or (lambda x: view.label(x)))
    return [serialize.node(view, x) for x in ranked[:MAX_LIST]]


@router.get("/map/province/{name:path}")
def map_province(name: str, era: str = "after"):
    """Chi tiết một tỉnh. era=after: gộp mọi tỉnh cũ có `final` là tỉnh này; era=before: chỉ riêng nó."""
    iri = resolve_or_404(name)
    provinces = _provinces()
    if iri not in provinces:
        raise HTTPException(status_code=404, detail=f"“{name}” không phải tỉnh, thành phố.")
    group = [p for p, i in provinces.items() if i["final"] == iri] if era == "after" else [iri]
    acc = _union(group)
    g = kg.graph
    # cầu thủ nổi bật trước: nhiều chặng sự nghiệp hơn
    stations = lambda x: (-len(set(g.objects(x, VIO.careerStation))), kg.view.label(x))  # noqa: E731
    info = provinces[iri]
    values = " ".join(f"<{p}>" for p in group)
    sparql = (
        "SELECT ?tinh ?cau_thu WHERE {\n"
        f"  VALUES ?tinh {{ {values} }}\n"
        "  ?cau_thu a vio:FootballPlayer ; vio:birthProvince ?tinh .\n"
        "} ORDER BY ?tinh ?cau_thu"
    )
    return {
        "node": info["node"],
        "former": info["former"],
        "year": info["year"],
        "final": serialize.node(kg.view, info["final"]),
        "members": [provinces[p]["node"] for p in sorted(group, key=lambda p: (p != iri, kg.view.label(p)))],
        "counts": {k: len(v) for k, v in acc.items()},
        "players": _top(acc["players"], stations),
        "clubs": _top(acc["clubs"]),
        "unis": _top(acc["unis"]),
        "sparql": sparql,
    }
