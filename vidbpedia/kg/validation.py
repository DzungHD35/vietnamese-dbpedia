"""Kiểm tra chất lượng ontology và dữ liệu. Mỗi hàm check_* trả list[Issue]."""

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass

from rdflib import Literal, URIRef
from rdflib.namespace import FOAF, OWL, RDF, RDFS, XSD

from vidbpedia.vocab import DBO, DBR, VIO, VRES, WD

MAIN_CLASSES = {
    VIO.FootballPlayer,
    VIO.FootballClub,
    VIO.NationalFootballTeam,
    VIO.Stadium,
    VIO.University,
    VIO.Province,
    VIO.Country,
}


@dataclass
class Issue:
    severity: str  # "error" | "warning"
    check: str
    subject: str
    detail: str


def as_dicts(issues):
    return [asdict(i) for i in issues]


def _kinds(ontology):
    kinds = {}
    for p in ontology.subjects(RDF.type, OWL.ObjectProperty):
        kinds[p] = "object"
    for p in ontology.subjects(RDF.type, OWL.DatatypeProperty):
        kinds[p] = "datatype"
    return kinds


def _superclasses(ontology):
    sup = defaultdict(set)
    for c in set(ontology.subjects(RDF.type, OWL.Class)):
        sup[c] = set(ontology.transitive_objects(c, RDFS.subClassOf))
    return sup


def check_tbox(ontology):
    """Lint ontology: subPropertyOf cùng loại, lớp vio: có tổ tiên dbo:, thuật ngữ vio: đủ nhãn vi/en."""
    issues, kinds = [], _kinds(ontology)
    for a, b in ontology.subject_objects(RDFS.subPropertyOf):
        if a in kinds and b in kinds and kinds[a] != kinds[b]:
            issues.append(Issue("error", "tbox-subproperty-kind", str(a), f"{kinds[a]} ⊑ {kinds[b]} ({b})"))
    sup = _superclasses(ontology)
    for c in ontology.subjects(RDF.type, OWL.Class):
        if str(c).startswith(str(VIO)) and not any(str(s).startswith(str(DBO)) for s in sup[c]):
            issues.append(Issue("error", "tbox-dbo-alignment", str(c), "lớp vio: không có tổ tiên dbo:"))
    terms = [
        t
        for t in set(ontology.subjects(RDF.type, None))
        if str(t).startswith(str(VIO)) and t != URIRef(str(VIO))
    ]
    for t in terms:
        langs = {lbl.language for lbl in ontology.objects(t, RDFS.label)}
        if not {"vi", "en"} <= langs:
            issues.append(
                Issue("error", "tbox-labels", str(t), f"thiếu nhãn: {sorted({'vi', 'en'} - langs)}")
            )
    return issues


def check_property_kinds(ontology, data):
    """ObjectProperty có đối tượng là IRI; DatatypeProperty có đối tượng là literal."""
    issues, kinds = [], _kinds(ontology)
    for p, kind in kinds.items():
        if not str(p).startswith(str(VIO)):
            continue
        for s, o in data.subject_objects(p):
            if kind == "object" and isinstance(o, Literal):
                issues.append(Issue("error", "object-property-literal", str(s), f"{p} = {o!r}"))
            elif kind == "datatype" and not isinstance(o, Literal):
                issues.append(Issue("error", "datatype-property-iri", str(s), f"{p} = {o}"))
    return issues


def check_datatype_ranges(ontology, data):
    """Literal phải đúng range khai báo và không ill-typed (rdflib kiểm cú pháp theo XSD)."""
    issues = []
    for p in ontology.subjects(RDF.type, OWL.DatatypeProperty):
        rng = ontology.value(p, RDFS.range)
        for s, o in data.subject_objects(p):
            if not isinstance(o, Literal):
                continue
            if getattr(o, "ill_typed", False):
                issues.append(Issue("error", "literal-ill-typed", str(s), f"{p} = {o!r}"))
            if rng is None:
                continue
            if rng == RDF.langString:
                ok = o.language is not None
            else:
                ok = o.language is None and (o.datatype or XSD.string) == rng
            if not ok:
                got = f"@{o.language}" if o.language else (o.datatype or XSD.string)
                issues.append(Issue("error", "literal-range", str(s), f"{p}: cần {rng}, có {got}"))
    for s, p, o in data:
        if isinstance(o, Literal) and getattr(o, "ill_typed", False) and not str(p).startswith(str(VIO)):
            issues.append(Issue("error", "literal-ill-typed", str(s), f"{p} = {o!r}"))
    return issues


def check_required(data):
    """Mỗi thực thể chính có: đúng một lớp chính, nhãn @vi, trang nguồn, page ID, owl:sameAs tới Wikidata."""
    issues = []
    for e in {s for c in MAIN_CLASSES for s in data.subjects(RDF.type, c)}:
        main = [c for c in data.objects(e, RDF.type) if c in MAIN_CLASSES]
        if len(main) != 1:
            issues.append(Issue("error", "required-main-class", str(e), f"{len(main)} lớp chính: {main}"))
        if not any(lbl.language == "vi" for lbl in data.objects(e, RDFS.label)):
            issues.append(Issue("error", "required-label-vi", str(e), "thiếu rdfs:label @vi"))
        if data.value(e, FOAF.isPrimaryTopicOf) is None:
            issues.append(Issue("error", "required-source", str(e), "thiếu foaf:isPrimaryTopicOf"))
        if data.value(e, DBO.wikiPageID) is None:
            issues.append(Issue("warning", "required-page-id", str(e), "thiếu dbo:wikiPageID"))
        if not any(str(o).startswith(str(WD)) for o in data.objects(e, OWL.sameAs)):
            issues.append(Issue("error", "required-wikidata-link", str(e), "thiếu owl:sameAs wd:"))
    return issues


def check_functional(ontology, data):
    issues = []
    for p in ontology.subjects(RDF.type, OWL.FunctionalProperty):
        counts = Counter(s for s, _ in data.subject_objects(p))
        for s, n in counts.items():
            if n > 1:
                values = sorted(str(o) for o in data.objects(s, p))
                issues.append(Issue("error", "functional", str(s), f"{p} có {n} giá trị: {values[:3]}"))
    return issues


def check_object_ranges(ontology, data):
    """Giả định đóng: nếu đối tượng là thực thể đã mô tả (có lớp vio: khai báo) thì lớp đó phải hợp với range."""
    issues, sup = [], _superclasses(ontology)
    asserted_type = {}
    for s, c in data.subject_objects(RDF.type):
        if str(c).startswith(str(VIO)):
            asserted_type.setdefault(s, set()).add(c)
    for p in ontology.subjects(RDF.type, OWL.ObjectProperty):
        rng = ontology.value(p, RDFS.range)
        if rng is None or not str(p).startswith(str(VIO)):
            continue
        for s, o in data.subject_objects(p):
            types = asserted_type.get(o)
            if types and not any(t == rng or rng in sup.get(t, ()) for t in types):
                issues.append(
                    Issue(
                        "error",
                        "object-range",
                        str(s),
                        f"{p} → {o} có lớp {sorted(map(str, types))}, cần {rng}",
                    )
                )
    return issues


def check_sameas(data):
    issues, targets = [], defaultdict(set)
    for s, o in data.subject_objects(OWL.sameAs):
        if not str(s).startswith(str(VRES)):
            continue
        targets[o].add(s)
        if str(o).startswith(str(DBR)) and any(
            k in str(o) for k in ("List_of", "Danh_sách", "(disambiguation)")
        ):
            issues.append(Issue("error", "sameas-list-page", str(s), f"owl:sameAs {o}"))
    for o, subjects in targets.items():
        if len(subjects) > 1:
            issues.append(
                Issue(
                    "error",
                    "sameas-shared-target",
                    str(o),
                    f"{len(subjects)} tài nguyên cùng trỏ tới: {sorted(map(str, subjects))[:3]}",
                )
            )
    return issues


def check_plausibility(data):
    issues = []
    located = {
        s
        for c in (VIO.Province, VIO.Stadium, VIO.University, VIO.FootballClub)
        for s in data.subjects(RDF.type, c)
    }
    for e in located:
        lat, lon = data.value(e, VIO.latitude), data.value(e, VIO.longitude)
        if lat is not None and lon is not None and not (8 <= float(lat) <= 24 and 102 <= float(lon) <= 110):
            issues.append(Issue("warning", "coordinates-outside-vn", str(e), f"({lat}, {lon})"))
    for e in data.subjects(RDF.type, VIO.FootballPlayer):
        for p in (VIO.birthDate, VIO.birthYear):
            v = data.value(e, p)
            if v is not None and not (1900 <= int(str(v)[:4]) <= 2015):
                issues.append(Issue("warning", "birth-year-range", str(e), f"{p} = {v}"))
    for p, low, high in (
        (VIO.capacity, 300, 200_000),
        (VIO.population, 1_000, 200_000_000),
        (VIO.height, 1.4, 2.2),
    ):
        for s, o in data.subject_objects(p):
            if not (low <= float(o) <= high):
                issues.append(Issue("warning", "value-range", str(s), f"{p} = {o}"))
    return issues


def check_asserted(ontology, data):
    return (
        check_tbox(ontology)
        + check_property_kinds(ontology, data)
        + check_datatype_ranges(ontology, data)
        + check_required(data)
        + check_functional(ontology, data)
        + check_object_ranges(ontology, data)
        + check_sameas(data)
        + check_plausibility(data)
    )


def summarize(issues):
    by = Counter((i.severity, i.check) for i in issues)
    return {
        "errors": sum(n for (sev, _), n in by.items() if sev == "error"),
        "warnings": sum(n for (sev, _), n in by.items() if sev == "warning"),
        "by_check": {f"{sev}:{chk}": n for (sev, chk), n in sorted(by.items())},
    }
