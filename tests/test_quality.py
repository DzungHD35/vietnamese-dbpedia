"""Chất lượng dataset: mọi kiểm tra của validation.py ra 0 lỗi; phần suy luận không chứa owl:sameAs."""

import json
import os

from rdflib import Graph
from rdflib.namespace import OWL

from vidbpedia.common import DATASET, PARTS_DIR
from vidbpedia.kg import validation

PARTS = PARTS_DIR


def test_validation_has_no_errors():
    ontology = Graph().parse(os.path.join(PARTS, "ontology.ttl"))
    asserted = Graph().parse(os.path.join(PARTS, "asserted.nt"), format="nt")
    errors = [i for i in validation.check_asserted(ontology, asserted) if i.severity == "error"]
    assert not errors, errors[:5]


def test_inferred_part_has_no_sameas():
    inferred = Graph().parse(os.path.join(PARTS, "inferred.nt"), format="nt")
    assert len(inferred) > 10_000
    assert not list(inferred.triples((None, OWL.sameAs, None)))


def test_stats_report_consistent():
    with open(DATASET + "_stats.json", encoding="utf-8") as f:
        stats = json.load(f)
    assert stats["validation"]["errors"] == 0
    assert stats["entities_by_class"]["FootballPlayer"] >= 550
    assert stats["total_triples"] > stats["asserted_triples"] + stats["inferred_triples"]
    assert stats["interlinks_to_dbpedia"] >= 700
