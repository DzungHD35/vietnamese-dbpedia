"""Fixture dùng chung: nạp dataset đầy đủ (khai báo + suy luận + ontology) một lần cho cả phiên test."""

import logging
import os

import pytest
from rdflib import Graph

from vidbpedia.common import DATASET
from vidbpedia.vocab import PREFIXES

logging.getLogger("rdflib.term").setLevel(logging.CRITICAL)
DATASET_NT = DATASET + ".nt"


@pytest.fixture(scope="session")
def graph():
    if not os.path.exists(DATASET_NT):
        pytest.skip("Chưa có data/vietnamese_dbpedia.nt: chạy python -m vidbpedia postprocess trước.")
    return Graph().parse(DATASET_NT, format="nt")


@pytest.fixture(scope="session")
def run(graph):
    """Chạy SPARQL với các prefix khai báo sẵn, trả list dict {biến: giá trị}."""

    def _run(query):
        result = graph.query(query, initNs=PREFIXES)
        if result.type == "ASK":
            return result.askAnswer
        return [{str(v): row[i] for i, v in enumerate(result.vars)} for row in result]

    return _run
