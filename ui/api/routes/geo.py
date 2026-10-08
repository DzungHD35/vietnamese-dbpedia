"""Bản đồ: /api/map (điểm có toạ độ và quan hệ kế thừa giữa các tỉnh)."""

from functools import lru_cache

from fastapi import APIRouter
from rdflib.namespace import RDF

from ui.api import serialize
from ui.api.routes.entity import number
from ui.api.state import kg
from vidbpedia.vocab import VIO, VRES, WGS84

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
