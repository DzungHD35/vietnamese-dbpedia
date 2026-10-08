"""Dữ liệu màn Thực thể: /api/search, /api/entity, /api/neighbors, /api/subgraph."""

from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query
from rdflib import Literal, URIRef
from rdflib.namespace import FOAF, OWL, RDF, RDFS, SKOS

from ui.api import adapters, serialize
from ui.api.state import kg, resolve_or_404
from vidbpedia.vocab import DBO, DBR, PROV, VIO, VIP, VRES, WD, WGS84
from vidbpedia.web.resource_page import LINK_PROPS, STATION_ORDER

router = APIRouter(prefix="/api")

MAX_VALUES = 40  # số giá trị tối đa mỗi thuộc tính / mỗi nhóm "được tham chiếu bởi"
MAX_SUBGRAPH_IDS = 60
STATION_KIND = {VIO.YouthStation: "youth", VIO.ClubStation: "club", VIO.NationalTeamStation: "national"}
WIKIPEDIA_LABEL = "vi.wikipedia.org"


@router.get("/search")
def search(q: str = "", limit: int = Query(10, ge=1, le=50)):
    view = kg.view
    results = []
    for _, local in view.search(q, limit):
        iri = view.resolve(local)
        if iri is not None:
            n = serialize.node(view, iri)
            results.append({k: n[k] for k in ("id", "label", "cls", "kind")})
    return results


@router.get("/entity/{name:path}")
def entity(name: str):
    iri = resolve_or_404(name)
    view, g = kg.view, kg.graph
    abstract = next((o for o in g.objects(iri, DBO.abstract) if o.language == "vi"), None)
    abstract = abstract if abstract is not None else g.value(iri, RDFS.comment)
    thumbnail = g.value(iri, DBO.thumbnail)
    own = list(g.predicate_objects(iri))
    return {
        "node": serialize.node(view, iri),
        "abstract": str(abstract) if abstract is not None else None,
        "thumbnail": str(thumbnail) if thumbnail is not None else None,
        "altLabels": sorted({str(o) for o in g.objects(iri, SKOS.altLabel)}),
        "classes": _classes(iri),
        "lod": _lod(iri),
        "career": _career(iri),
        "facts": _facts(iri, own),
        "incoming": _incoming(iri),
        "counts": {
            "asserted": sum(1 for p, o in own if (iri, p, o) not in view.inferred),
            "inferred": sum(1 for p, o in own if (iri, p, o) in view.inferred),
        },
    }


def _classes(iri) -> list[dict]:
    """Lớp vio:/dbo: của thực thể dạng cây phẳng (cha trước con); cha chính ưu tiên vio:."""
    view, g = kg.view, kg.graph
    types = {t for t in g.objects(iri, RDF.type) if str(t).startswith((str(VIO), str(DBO)))}
    supers = {
        t: sorted({s for s in g.objects(t, RDFS.subClassOf) if s in types and s != t}, key=str) for t in types
    }

    def primary(t):
        own = [s for s in supers[t] if str(s).startswith(str(VIO))]
        return (own or supers[t] or [None])[0]

    children, roots = defaultdict(list), []
    for t in sorted(types, key=str):
        p = primary(t)
        (children[p] if p is not None else roots).append(t)

    out = []

    def visit(t):
        p = primary(t)
        out.append(
            {
                "id": view.qname(t),
                "label": view.label(t),
                "inferred": (iri, RDF.type, t) in view.inferred,
                "parent": view.qname(p) if p is not None else None,
                "also": [view.qname(s) for s in supers[t] if s != p],
            }
        )
        for c in sorted(children[t], key=lambda c: (str(c).startswith(str(VIO)), str(c))):
            visit(c)

    for r in roots:
        visit(r)
    return out


def _lod(iri) -> dict:
    g = kg.graph
    same = sorted(str(o) for o in g.objects(iri, OWL.sameAs))
    wikipedia, derived = g.value(iri, FOAF.isPrimaryTopicOf), g.value(iri, PROV.wasDerivedFrom)
    lat = g.value(iri, VIO.latitude) or g.value(iri, WGS84.lat)
    lon = g.value(iri, VIO.longitude) or g.value(iri, WGS84["long"])
    return {
        "wikipedia": str(wikipedia) if wikipedia is not None else None,
        "dbpedia": [s for s in same if s.startswith(str(DBR))],
        "wikidata": [s for s in same if s.startswith(str(WD))],
        "derivedFrom": str(derived) if derived is not None else None,
        "lat": number(lat),
        "lon": number(lon),
        "linkedData": kg.view.href(iri),
    }


def number(term) -> float | None:
    try:
        return float(str(term))
    except (TypeError, ValueError):
        return None


def _career(iri) -> list[dict]:
    """Các chặng sự nghiệp theo thứ tự thời gian; chặng không rõ năm xếp cuối (frontend gom riêng)."""
    view, g = kg.view, kg.graph
    rows = []
    for st in g.objects(iri, VIO.careerStation):
        kinds = [t for t in g.objects(st, RDF.type) if t in STATION_ORDER]
        kind = STATION_KIND[min(kinds, key=STATION_ORDER.get)] if kinds else "club"
        team = g.value(st, VIO.team)  # chỉ đọc thuộc tính vio:, không đọc dbo: do suy luận thêm vào
        loan = g.value(st, VIO.onLoan)
        rows.append(
            {
                "station": view.local(st),
                "kind": kind,
                "team": serialize.node(view, team) if team is not None else None,
                "start": serialize.year(g.value(st, VIO.startYear)),
                "end": serialize.year(g.value(st, VIO.endYear)),
                "apps": serialize.integer(g.value(st, VIO.appearances)),
                "goals": serialize.integer(g.value(st, VIO.goals)),
                "onLoan": loan is not None and str(loan).lower() == "true",
            }
        )
    order = {"youth": 0, "club": 1, "national": 2}
    rows.sort(key=lambda r: (r["start"] is None, r["start"] or 0, order[r["kind"]], r["station"]))
    return rows


def _prop_ns(p) -> str:
    s = str(p)
    return (
        "vio"
        if s.startswith(str(VIO))
        else "dbo"
        if s.startswith(str(DBO))
        else "vip"
        if s.startswith(str(VIP))
        else "other"
    )


def _facts(iri, own) -> list[dict]:
    """Mọi (p, o) đi ra nhóm theo p (trừ vio:careerStation, đã có ở `career`), sắp như trang của team."""
    view = kg.view
    groups = defaultdict(list)
    for p, o in own:
        if p != VIO.careerStation:
            groups[p].append(o)

    def sort_value(o):
        return (isinstance(o, Literal), view.label(o) if isinstance(o, URIRef) else str(o))

    facts = []
    for p in sorted(groups, key=lambda p: adapters.prop_key(view, p)):
        values = sorted(groups[p], key=sort_value)
        facts.append(
            {
                "prop": view.qname(p),
                "label": view.label(p),
                "ns": _prop_ns(p),
                "values": [serialize.value(view, iri, p, o) for o in values[:MAX_VALUES]],
                "more": max(len(values) - MAX_VALUES, 0),
            }
        )
    return facts


def _incoming(iri) -> list[dict]:
    view, g = kg.view, kg.graph
    groups = defaultdict(set)
    for s, p in g.subject_predicates(iri):
        if str(s).startswith(str(VRES)):
            groups[p].add(s)
    out = []
    for p in sorted(groups, key=lambda p: (-len(groups[p]), view.qname(p))):
        subs = sorted(groups[p], key=view.label)
        items = [
            {**serialize.node(view, s), "inferred": (s, p, iri) in view.inferred} for s in subs[:MAX_VALUES]
        ]
        out.append({"prop": view.qname(p), "label": view.label(p), "count": len(subs), "items": items})
    return out


@router.get("/neighbors/{name:path}")
def neighbors(name: str, limit: int = Query(24, ge=1, le=100)):
    """Lân cận một bước của thực thể: `nodes` gồm cả node trung tâm; `hidden` là số node bị cắt theo `limit`."""
    iri = resolve_or_404(name)
    view, g = kg.view, kg.graph
    out, inc = adapters.neighbors(view, iri)

    # liên kết LOD luôn hiện, không tính vào limit
    page = g.value(iri, FOAF.isPrimaryTopicOf)
    lod = [(o, OWL.sameAs) for o in sorted(g.objects(iri, OWL.sameAs), key=str)]
    if page is not None:
        lod.append((page, FOAF.isPrimaryTopicOf))

    n_out = min(len(out), max(limit // 2, limit - len(inc)))
    n_in = min(len(inc), limit - n_out)
    picked_out, picked_in = adapters.round_robin(out, n_out), adapters.round_robin(inc, n_in)
    hidden = len(out) + len(inc) - len(picked_out) - len(picked_in)

    nodes = {serialize.node_id(view, iri): serialize.node(view, iri)}
    edges = []
    for other, props in picked_out:
        nodes.setdefault(serialize.node_id(view, other), serialize.node(view, other))
        edges += [serialize.edge(view, iri, p, other) for p in props]
    for other, props in picked_in:
        nodes.setdefault(serialize.node_id(view, other), serialize.node(view, other))
        edges += [serialize.edge(view, other, p, iri) for p in props]
    for other, prop in lod:
        n = serialize.node(view, other)
        if other == page:
            n["label"] = WIKIPEDIA_LABEL
        nodes.setdefault(n["id"], n)
        edges.append(serialize.edge(view, iri, prop, other))
    return {
        "center": nodes[serialize.node_id(view, iri)],
        "nodes": list(nodes.values()),
        "edges": edges,
        "hidden": hidden,
    }


@router.get("/subgraph")
def subgraph(ids: list[str] = Query([])):
    """Cạnh giữa một tập thực thể (đồ thị bằng chứng của màn Hỏi đáp): `?ids=a&ids=b`.

    Lặp tham số thay vì `ids=a,b` vì id có thể chứa dấu phẩy ("Nguyễn_Quang_Hải_(cầu_thủ_bóng_đá,_sinh_1985)").
    """
    names = [n for n in dict.fromkeys(i.strip() for i in ids) if n]
    if len(names) > MAX_SUBGRAPH_IDS:
        raise HTTPException(status_code=422, detail=f"Tối đa {MAX_SUBGRAPH_IDS} thực thể mỗi lần.")
    view, g = kg.view, kg.graph
    iris = [iri for iri in (view.resolve(n) for n in names) if iri is not None]
    members = set(iris)
    link_props = set(LINK_PROPS)

    def inverse_in_link_props(p):
        return {q for q in (*g.objects(p, OWL.inverseOf), *g.subjects(OWL.inverseOf, p)) if q in link_props}

    edges, seen = [], set()
    for s in iris:
        for p, o in g.predicate_objects(s):
            if o not in members or o == s or (s, p, o) in seen:
                continue
            if p not in link_props and p != OWL.sameAs and not str(p).startswith(str(VIO)):
                continue
            # vio:hasPlayer là nghịch đảo của vio:playedFor: giữ cạnh thuận, bỏ cạnh song song
            if p not in link_props and any((o, q, s) in g for q in inverse_in_link_props(p)):
                continue
            seen.add((s, p, o))
            edges.append(serialize.edge(view, s, p, o))
    return {"nodes": [serialize.node(view, iri) for iri in iris], "edges": edges}
