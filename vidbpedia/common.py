"""Đường dẫn, logging và đọc/ghi JSON dùng chung."""

import json
import logging
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PARTS_DIR = os.path.join(DATA_DIR, "parts")
CACHE_PATH = os.path.join(DATA_DIR, "cache", "http.sqlite")
DATASET = os.path.join(DATA_DIR, "vietnamese_dbpedia")  # + .nt / .ttl / _stats.json
ONTOLOGY_DIR = os.path.join(ROOT, "ontology")
ONTOLOGY_FILE = os.path.join(ONTOLOGY_DIR, "vi-ontology.ttl")


def utf8_console():
    # console Windows mặc định cp1252, không in được tiếng Việt
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def setup_logging(verbose=False):
    utf8_console()
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    # rdflib log traceback cho mỗi năm trước Công nguyên (xsd:gYear âm); giá trị literal vẫn giữ nguyên
    logging.getLogger("rdflib.term").setLevel(logging.CRITICAL)


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
