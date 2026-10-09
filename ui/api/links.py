"""Biến ô kết quả (chuỗi) thành Node để frontend vẽ link: dùng chung cho /api/ask và /api/sparql."""

from functools import lru_cache

from rdflib import URIRef

from ui.api import adapters, serialize
from ui.api.state import kg
from vidbpedia.vocab import VRES
from vidbpedia.web.resource_page import fold

MAX_LABEL_LEN = 120  # ô dài hơn thế không thể là tên thực thể


@lru_cache(maxsize=1)
def _index() -> dict:
    return adapters.label_index(kg.view)


def link_for(cell: str) -> dict | None:
    """Ô → Node, hoặc None. Thứ tự: IRI vres: → IRI ngoài → nhãn trùng nguyên văn đúng một thực thể."""
    view = kg.view
    if cell.startswith(str(VRES)):
        iri = view.resolve(cell[len(str(VRES)) :])
        return serialize.node(view, iri) if iri is not None else None
    if cell.startswith(("http://", "https://")) and " " not in cell:
        return serialize.node(view, URIRef(cell))
    if not cell or len(cell) > MAX_LABEL_LEN:
        return None
    found = _index().get(fold(cell), set())
    return serialize.node(view, next(iter(found))) if len(found) == 1 else None


def build_links(rows: list[dict[str, str]]) -> dict[str, dict]:
    """{giá trị ô: Node} cho mọi ô nhận ra được là thực thể."""
    links: dict[str, dict] = {}
    seen: set[str] = set()
    for row in rows:
        for cell in row.values():
            if cell in seen:
                continue
            seen.add(cell)
            node = link_for(cell)
            if node is not None:
                links[cell] = node
    return links
