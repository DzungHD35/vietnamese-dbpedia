"""Ghép các module ontology/NNN-*.ttl thành ontology/vi-ontology.ttl.

python -m vidbpedia ontology
"""

import logging
import os
import re

from rdflib import Graph

from vidbpedia.common import ONTOLOGY_DIR, ONTOLOGY_FILE, setup_logging

logger = logging.getLogger(__name__)

PREFIX_FILE = "000-prefixes.ttl"
MODULE_RE = re.compile(r"^\d{3}-.+\.ttl$")
DIRECTIVE_RE = re.compile(r"^\s*@(prefix|base)\b[^\n]*\n", re.IGNORECASE | re.MULTILINE)


def _read(name):
    with open(os.path.join(ONTOLOGY_DIR, name), encoding="utf-8-sig") as f:
        return f.read()


def modules():
    return sorted(f for f in os.listdir(ONTOLOGY_DIR) if MODULE_RE.match(f) and f != PREFIX_FILE)


def merge():
    """Prefix khai báo một lần ở 000-prefixes.ttl, các module ghép theo thứ tự số."""
    parts = [_read(PREFIX_FILE)] + [DIRECTIVE_RE.sub("", _read(name)).strip() for name in modules()]
    return Graph().parse(data="\n\n".join(parts), format="turtle")


def main():
    setup_logging()
    graph = merge()
    graph.serialize(destination=ONTOLOGY_FILE, format="turtle", encoding="utf-8")
    logger.info("%d module → %s (%d triple)", len(modules()), ONTOLOGY_FILE, len(graph))


if __name__ == "__main__":
    main()
