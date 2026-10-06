"""Suy luận OWL 2 RL (owlrl) để có thêm các triple dbo:, vio: suy ra từ ontology.

Reasoner chỉ chạy trên phần khung của dữ liệu (rdf:type và triple vio:). Ontology đưa vào bỏ owl:sameAs,
FunctionalProperty và cardinality: OWL RL sinh `x owl:sameAs x` cho mọi nút và luật prp-fp sẽ gộp các
giá trị khác nhau thành một. Các ràng buộc functional được kiểm tra riêng trong validation.py.
"""

import time

import owlrl
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from vidbpedia.vocab import DBO, VIO, VRES, WGS84

ERR = URIRef("http://www.daml.org/2002/03/agents/agent-ont#ErrorMessage")
ERR_TEXT = URIRef("http://www.daml.org/2002/03/agents/agent-ont#error")
DROP_TBOX_TYPES = {OWL.FunctionalProperty, OWL.InverseFunctionalProperty}
DROP_TBOX_PREDICATES = {
    OWL.maxCardinality,
    OWL.maxQualifiedCardinality,
    OWL.cardinality,
    OWL.qualifiedCardinality,
    OWL.sameAs,
}
KEEP_PROPERTY_NS = (str(VIO), str(DBO), str(WGS84))
TRIVIAL_TYPES = {OWL.Thing, RDFS.Resource, OWL.NamedIndividual, OWL.Class, RDFS.Class}


def reasoner_tbox(ontology):
    tbox = Graph()
    for s, p, o in ontology:
        if (p == RDF.type and o in DROP_TBOX_TYPES) or p in DROP_TBOX_PREDICATES:
            continue
        tbox.add((s, p, o))
    return tbox


def skeleton(asserted):
    """rdf:type và triple vio: của tài nguyên vres:, phần duy nhất ảnh hưởng tới kết quả suy luận."""
    abox = Graph()
    for s, p, o in asserted:
        if (
            isinstance(s, URIRef)
            and str(s).startswith(str(VRES))
            and (p == RDF.type or str(p).startswith(str(VIO)))
        ):
            abox.add((s, p, o))
    return abox


def materialize(ontology, asserted, semantics="owlrl"):
    """→ (inferred, errors, seconds); inferred chỉ gồm triple mới: lớp vio:/dbo: và thuộc tính vio:/dbo:/wgs84:."""
    tbox = reasoner_tbox(ontology)
    abox = skeleton(asserted)
    work = Graph()
    work += tbox
    work += abox
    sem = owlrl.OWLRL_Semantics if semantics == "owlrl" else owlrl.RDFS_Semantics
    t0 = time.perf_counter()
    owlrl.DeductiveClosure(sem, rdfs_closure=False, axiomatic_triples=False, datatype_axioms=False).expand(
        work
    )
    seconds = time.perf_counter() - t0

    errors = sorted(str(o) for s in work.subjects(RDF.type, ERR) for o in work.objects(s, ERR_TEXT))
    tbox_terms = set(tbox.subjects())
    inferred = Graph()
    for s, p, o in work:
        if (s, p, o) in abox or (s, p, o) in tbox:
            continue
        if not isinstance(s, URIRef) or s in tbox_terms or p == OWL.sameAs:
            continue
        if p == RDF.type:
            if isinstance(o, URIRef) and o not in TRIVIAL_TYPES and str(o).startswith((str(VIO), str(DBO))):
                inferred.add((s, p, o))
        elif str(p).startswith(KEEP_PROPERTY_NS):
            inferred.add((s, p, o))
    return inferred, errors, seconds
