"""Gộp ontology và data/raw/rdf/*.ttl, kiểm tra, suy luận, mô tả bằng VoID rồi xuất dataset.

Ghi:
  data/vietnamese_dbpedia.{ttl,nt}                      ontology + khai báo + suy luận + VoID
  data/parts/{ontology.ttl, asserted.nt, inferred.nt}   tách theo nguồn gốc
  data/vietnamese_dbpedia_stats.json, data/validation_report.json

    python -m vidbpedia postprocess [--no-reason] [--reasoner owlrl|rdfs] [--strict] [--rdfxml]
"""

import argparse
import glob
import json
import logging
import os
import sys
from datetime import date

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, XSD

from vidbpedia.common import DATA_DIR, ONTOLOGY_FILE, RAW_DIR, setup_logging
from vidbpedia.kg import validation
from vidbpedia.kg.reasoning import materialize
from vidbpedia.vocab import DBO, DBR, VIO, VOID, VRES, WD, bind_prefixes

logger = logging.getLogger(__name__)

RAW_RDF_DIR = os.path.join(RAW_DIR, "rdf")
DUMP_BASE = "https://github.com/stephen-do/vietnamese-dbpedia/raw/main/data/"
DATASET = URIRef("http://vi.dbpedia.org/void/Dataset")
LICENSE = URIRef("https://creativecommons.org/licenses/by-sa/4.0/")


def load(paths):
    g = Graph()
    for p in paths:
        g.parse(p, format="turtle")
    return g


def class_counts(g):
    return {
        str(c).rsplit("/", 1)[-1]: len(set(g.subjects(RDF.type, c))) for c in sorted(validation.MAIN_CLASSES)
    }


def link_counts(g):
    pairs = [(s, o) for s, o in g.subject_objects(OWL.sameAs) if str(s).startswith(str(VRES))]
    return sum(str(o).startswith(str(DBR)) for _, o in pairs), sum(
        str(o).startswith(str(WD)) for _, o in pairs
    )


def void_description(ontology, asserted, inferred):
    """License, nguồn, subset theo nguồn gốc, phân lớp và linkset của dataset."""
    v = Graph()
    v.add((DATASET, RDF.type, VOID.Dataset))
    v.add((DATASET, DCTERMS.title, Literal("Vietnamese DBpedia", lang="en")))
    v.add(
        (
            DATASET,
            DCTERMS.description,
            Literal(
                "Dữ liệu có cấu trúc về cầu thủ, câu lạc bộ, sân vận động bóng đá, tỉnh thành và trường đại học "
                "Việt Nam, trích từ Wikipedia tiếng Việt và Wikidata.",
                lang="vi",
            ),
        )
    )
    v.add((DATASET, DCTERMS.license, LICENSE))
    v.add((DATASET, DCTERMS.source, URIRef("https://vi.wikipedia.org/")))
    v.add((DATASET, DCTERMS.source, URIRef("https://www.wikidata.org/")))
    v.add((DATASET, DCTERMS.created, Literal(date.today().isoformat(), datatype=XSD.date)))
    v.add((DATASET, VOID.uriSpace, Literal(str(VRES))))
    v.add((DATASET, VOID.vocabulary, URIRef(str(VIO))))
    v.add((DATASET, VOID.vocabulary, URIRef(str(DBO))))
    v.add((DATASET, VOID.dataDump, URIRef(DUMP_BASE + "vietnamese_dbpedia.nt")))
    for name, g, dump in (
        ("ontology", ontology, "parts/ontology.ttl"),
        ("asserted", asserted, "parts/asserted.nt"),
        ("inferred", inferred, "parts/inferred.nt"),
    ):
        sub = URIRef(f"http://vi.dbpedia.org/void/{name}")
        v.add((DATASET, VOID.subset, sub))
        v.add((sub, RDF.type, VOID.Dataset))
        v.add((sub, VOID.triples, Literal(len(g), datatype=XSD.integer)))
        v.add((sub, VOID.dataDump, URIRef(DUMP_BASE + dump)))
    for cls, n in class_counts(asserted).items():
        part = URIRef(f"http://vi.dbpedia.org/void/class/{cls}")
        v.add((DATASET, VOID.classPartition, part))
        v.add((part, VOID["class"], VIO[cls]))
        v.add((part, VOID.entities, Literal(n, datatype=XSD.integer)))
    dbr, wd = link_counts(asserted)
    for name, target, count in (
        ("DBpedia", "http://dbpedia.org/void/Dataset", dbr),
        ("Wikidata", "http://www.wikidata.org/", wd),
    ):
        ls = URIRef(f"http://vi.dbpedia.org/void/Linkset_{name}")
        v.add((DATASET, VOID.subset, ls))
        v.add((ls, RDF.type, VOID.Linkset))
        v.add((ls, VOID.subjectsTarget, DATASET))
        v.add((ls, VOID.objectsTarget, URIRef(target)))
        v.add((ls, VOID.linkPredicate, OWL.sameAs))
        v.add((ls, VOID.triples, Literal(count, datatype=XSD.integer)))
    return v


def write(g, path, fmt):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bind_prefixes(g)
    g.serialize(destination=path, format=fmt, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Gộp, kiểm tra, suy luận và xuất dataset Vietnamese DBpedia")
    ap.add_argument("--output", default=DATA_DIR)
    ap.add_argument("--no-reason", action="store_true", help="bỏ bước suy luận (chạy nhanh khi phát triển)")
    ap.add_argument("--reasoner", choices=["owlrl", "rdfs"], default="owlrl")
    ap.add_argument("--strict", action="store_true", help="thoát mã 1 nếu có lỗi kiểm tra")
    ap.add_argument("--rdfxml", action="store_true", help="xuất thêm RDF/XML")
    args = ap.parse_args()
    setup_logging()

    ontology = load([ONTOLOGY_FILE])
    raw_files = sorted(glob.glob(os.path.join(RAW_RDF_DIR, "*.ttl")))
    if not raw_files:
        sys.exit(f"Chưa có RDF trong {RAW_RDF_DIR}: chạy python -m vidbpedia build trước.")
    asserted = load(raw_files)
    logger.info(
        "Ontology %d triple; dữ liệu khai báo %d triple (%d file)",
        len(ontology),
        len(asserted),
        len(raw_files),
    )

    issues = validation.check_asserted(ontology, asserted)

    inferred, reason_errors, seconds = Graph(), [], 0.0
    if not args.no_reason:
        inferred, reason_errors, seconds = materialize(ontology, asserted, args.reasoner)
        logger.info("Suy luận %s: +%d triple trong %.1f s", args.reasoner, len(inferred), seconds)
        issues += [validation.Issue("error", "reasoner-inconsistency", "-", msg) for msg in reason_errors]

    voids = void_description(ontology, asserted, inferred)
    full = Graph()
    for g in (ontology, asserted, inferred, voids):
        for t in g:
            full.add(t)

    out = args.output
    base = os.path.join(out, "vietnamese_dbpedia")
    write(full, base + ".ttl", "turtle")
    write(full, base + ".nt", "nt")
    if args.rdfxml:
        write(full, base + ".rdf", "xml")
    write(ontology, os.path.join(out, "parts", "ontology.ttl"), "turtle")
    write(asserted, os.path.join(out, "parts", "asserted.nt"), "nt")
    write(inferred, os.path.join(out, "parts", "inferred.nt"), "nt")

    # đọc lại để chắc file ghi ra hợp lệ và đủ triple
    back = Graph().parse(base + ".nt", format="nt")
    if len(back) != len(full):
        issues.append(validation.Issue("error", "round-trip", base + ".nt", f"{len(back)} ≠ {len(full)}"))

    dbr, wd = link_counts(asserted)
    summary = validation.summarize(issues)
    stations = sum(
        len(set(asserted.subjects(RDF.type, c)))
        for c in (VIO.YouthStation, VIO.ClubStation, VIO.NationalTeamStation)
    )
    stats = {
        "total_triples": len(full),
        "asserted_triples": len(asserted),
        "inferred_triples": len(inferred),
        "ontology_triples": len(ontology),
        "entities": sum(class_counts(asserted).values()),
        "entities_by_class": class_counts(asserted),
        "career_stations": stations,
        "interlinks_to_dbpedia": dbr,
        "interlinks_to_wikidata": wd,
        "languages": sorted(
            {o.language for o in asserted.objects() if isinstance(o, Literal) and o.language}
        ),
        "reasoner": None if args.no_reason else args.reasoner,
        "reasoning_seconds": round(seconds, 1),
        "validation": {"errors": summary["errors"], "warnings": summary["warnings"]},
        "built": date.today().isoformat(),
    }
    with open(base + "_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out, "validation_report.json"), "w", encoding="utf-8") as f:
        json.dump({**summary, "issues": validation.as_dicts(issues)}, f, ensure_ascii=False, indent=1)

    logger.info(
        "Đã ghi %s.{ttl,nt}: %d triple (khai báo %d + suy luận %d + ontology %d), %d thực thể",
        base,
        len(full),
        len(asserted),
        len(inferred),
        len(ontology),
        stats["entities"],
    )
    logger.info(
        "Kiểm tra: %d lỗi, %d cảnh báo — %s", summary["errors"], summary["warnings"], summary["by_check"]
    )
    if args.strict and summary["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
