"""Kiểm tra mâu thuẫn: thêm thử một triple vào phần graph quanh thực thể rồi chạy reasoner OWL 2 RL.

Không ghi vào graph thật: lấy các triple khai báo quanh chủ ngữ và tân ngữ (kèm chặng sự nghiệp) thành một graph
nhỏ, thêm triple thử, gọi `materialize` của team. Graph vài trăm triple nên reasoner chạy dưới 1 giây.
"""

import os
import re
import time
from functools import lru_cache

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, RDFS

from ui.api.presets import CONSISTENCY_PRESETS
from ui.api.serialize import node
from ui.api.state import kg
from vidbpedia.common import PARTS_DIR
from vidbpedia.kg.reasoning import materialize
from vidbpedia.vocab import PREFIXES, VIO

router = APIRouter(prefix="/api/consistency")

DISJOINT = re.compile(r"Disjoint classes (\S+) and (\S+) have a common individual (\S+)")


class TripleBody(BaseModel):
    subject: str
    predicate: str  # qname, ví dụ "vio:ground" hoặc "rdf:type"
    object: str  # local name trong vres: hoặc qname của lớp


@lru_cache(maxsize=1)
def _ontology() -> Graph:
    return Graph().parse(os.path.join(PARTS_DIR, "ontology.ttl"), format="turtle")


def _expand(qname: str) -> URIRef | None:
    prefix, sep, local = qname.strip().partition(":")
    if qname.strip() == "a":
        return RDF.type
    if not sep or prefix not in PREFIXES or not local:
        return None
    return URIRef(PREFIXES[prefix] + local)


def _term(term: str, what: str) -> URIRef:
    """Thực thể (local name/IRI) hoặc thuật ngữ schema (qname có trong ontology) → URIRef; không có thì 400."""
    iri = kg.view.resolve(term)
    if iri is None:
        iri = _expand(term)
        if iri is None or (iri, None, None) not in _ontology():
            raise HTTPException(status_code=400, detail=f"Không nhận ra {what} “{term}”.")
    return iri


def _schema(iri) -> dict:
    """Lớp/thuộc tính → {qname, label}; nhãn tiếng Việt lấy từ ontology."""
    return {"qname": kg.view.qname(iri), "label": kg.view.label(iri)}


def _ref(iri) -> dict:
    return node(kg.view, iri) if (iri, None, None) not in _ontology() else _schema(iri)


def _neighbourhood(asserted: Graph, roots) -> Graph:
    """Triple khai báo của các nút gốc và chặng sự nghiệp của chúng: đủ để reasoner biết kiểu của mỗi nút."""
    g = Graph()
    for r in roots:
        for t in asserted.triples((r, None, None)):
            g.add(t)
        for st in asserted.objects(r, VIO.careerStation):
            for t in asserted.triples((st, None, None)):
                g.add(t)
    return g


def _axioms(p) -> dict:
    ont = _ontology()
    domain, rng = ont.value(p, RDFS.domain), ont.value(p, RDFS.range)
    return {"domain": _schema(domain) if domain else None, "range": _schema(rng) if rng else None}


def _conflict(a, b, x, s, p, o) -> dict:
    """Vi phạm disjoint → lớp x đã có trong graph thật (`known`), lớp mới do triple thử (`inferred`) và lý do."""
    known, new = (b, a) if (x, RDF.type, a) not in kg.graph and (x, RDF.type, b) in kg.graph else (a, b)
    if p == RDF.type:
        reason = "khai báo trong triple thử"
    else:
        reason = f"{'domain' if x == s else 'range'} của “{kg.view.label(p)}”"
    return {
        "individual": node(kg.view, x),
        "isSubject": x == s,
        "known": _schema(known),
        "inferred": _schema(new),
        "reason": reason,
    }


@router.get("/presets")
def presets():
    """{id thực thể: [{subject, predicate, object, note}]}; bỏ preset có term không resolve được."""
    out = {}
    for name, items in CONSISTENCY_PRESETS.items():
        rows = []
        for s, p, o, note in items:
            try:
                s_iri, o_iri, p_iri = _term(s, "chủ ngữ"), _term(o, "tân ngữ"), _expand(p)
            except HTTPException:
                continue
            rows.append(
                {
                    "subject": s,
                    "predicate": p,
                    "object": o,
                    "note": note,
                    "s": _ref(s_iri),
                    "p": _schema(p_iri),
                    "o": _ref(o_iri),
                }
            )
        out[name] = rows
    return out


@router.post("")
def check(body: TripleBody):
    """Thêm thử triple (s, p, o) → {consistent, conflicts, gained, axioms, triples, ms}."""
    s, o = _term(body.subject, "chủ ngữ"), _term(body.object, "tân ngữ")
    p = _expand(body.predicate)
    if p is None or (p != RDF.type and (p, None, None) not in _ontology()):
        raise HTTPException(status_code=400, detail=f"Không nhận ra thuộc tính “{body.predicate}”.")
    if not kg.asserted_ready.wait(60) or kg.asserted is None:
        raise HTTPException(status_code=503, detail="Graph chỉ khai báo chưa nạp xong, thử lại sau ít giây.")

    roots = [s] if p == RDF.type else [s, o]
    g = _neighbourhood(kg.asserted, roots)
    g.add((s, p, o))
    t0 = time.perf_counter()
    inferred, errors, _ = materialize(_ontology(), g)
    ms = round((time.perf_counter() - t0) * 1000)

    conflicts, other = [], []
    for msg in errors:
        m = DISJOINT.search(msg)
        if m:
            conflicts.append(_conflict(*(URIRef(v) for v in m.groups()), s, p, o))
        else:
            other.append(msg)
    # lớp vio: mới có của chủ ngữ/tân ngữ so với graph thật: hệ quả trực tiếp của triple vừa thêm
    gained = []
    for x in roots:
        new = set(inferred.objects(x, RDF.type)) | ({o} if p == RDF.type else set())
        for c in sorted(new, key=str):
            if str(c).startswith(str(VIO)) and (x, RDF.type, c) not in kg.graph:
                gained.append({"node": node(kg.view, x), "cls": _schema(c)})
    return {
        "triple": {"s": _ref(s), "p": _schema(p), "o": _ref(o)},
        "consistent": not errors,
        "conflicts": conflicts,
        "errors": other,
        "gained": gained,
        "axioms": _axioms(p),
        "triples": len(g),
        "ms": ms,
    }
