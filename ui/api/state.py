"""Trạng thái dùng chung của API: graph, view, cây lớp, RAG; nạp một lần ở thread nền.

`kg` là singleton. Graph chính (khai báo + suy luận + ontology) nạp trước để API sẵn sàng; graph "chỉ khai báo"
nạp sau ở thread riêng, endpoint nào cần thì tự kiểm tra `asserted_ready`.
"""

import logging
import os
import threading

from fastapi import HTTPException
from rdflib import Graph

from vidbpedia.common import DATASET, PARTS_DIR
from vidbpedia.web.kg_rag import SparqlBasedKGRAG
from vidbpedia.web.resource_page import ResourceView
from vidbpedia.web.resource_tree import ResourceTree
from vidbpedia.web.sparql import SparqlService

logger = logging.getLogger(__name__)


class KG:
    def __init__(self):
        self.ready = False
        self.error: str | None = None
        self.message = "Chưa bắt đầu nạp graph."
        self.service: SparqlService | None = None
        self.graph: Graph | None = None
        self.view: ResourceView | None = None
        self.tree: ResourceTree | None = None
        self.rag: SparqlBasedKGRAG | None = None
        self.stats: dict = {}
        self.asserted: Graph | None = None
        self.asserted_error: str | None = None
        self.asserted_ready = threading.Event()

    @property
    def llm(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def load(self, dataset_file: str = DATASET + ".nt"):
        """Nạp toàn bộ dữ liệu (~1 phút); lỗi thì ghi vào `error` thay vì làm sập server."""
        try:
            self.message = "Đang nạp graph…"
            self.service = SparqlService(dataset_file)
            self.graph = self.service.graph
            self.stats = self.service.stats
            self.message = "Đang dựng chỉ mục và đánh dấu triple suy luận…"
            self.view = ResourceView.from_files(self.graph, dataset_file)
            self.tree = ResourceTree(self.view)
            self.rag = SparqlBasedKGRAG(self.graph)
            self.ready = True
            self.message = "Sẵn sàng."
            logger.info("Graph sẵn sàng: %d triple", len(self.graph))
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            self.message = "Nạp graph thất bại."
            logger.exception("Nạp graph thất bại")
            return
        threading.Thread(target=self._load_asserted, daemon=True).start()

    def _load_asserted(self):
        try:
            g = Graph()
            g.parse(os.path.join(PARTS_DIR, "asserted.nt"), format="nt")
            g.parse(os.path.join(PARTS_DIR, "ontology.ttl"), format="turtle")
            self.asserted = g
            logger.info("Graph chỉ khai báo sẵn sàng: %d triple", len(g))
        except Exception as e:
            self.asserted_error = f"{type(e).__name__}: {e}"
            logger.exception("Nạp graph chỉ khai báo thất bại")
        finally:
            self.asserted_ready.set()


kg = KG()


class LazyView:
    """Đưa cho `add_routes` của team khi graph chưa nạp xong: mọi truy cập chuyển tiếp tới `kg.view`."""

    def __getattr__(self, name):
        if kg.view is None:
            raise RuntimeError("Graph chưa nạp xong")
        return getattr(kg.view, name)


def resolve_or_404(name: str):
    """Local name hoặc IRI → URIRef có trong graph; không có thì 404 (tiếng Việt)."""
    iri = kg.view.resolve(name)
    if iri is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy thực thể “{name}” trong dataset.")
    return iri
