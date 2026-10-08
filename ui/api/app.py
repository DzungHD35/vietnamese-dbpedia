"""FastAPI của UI demo: nạp graph ở nền, gắn Linked Data của team, các route /api và phục vụ frontend đã build."""

import logging
import mimetypes
import os
import threading
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from ui.api.paths import WEB_DIST, WEB_INDEX
from ui.api.routes import ask, entity, overview, sparql
from ui.api.state import LazyView, kg
from vidbpedia.common import DATASET, setup_logging
from vidbpedia.web.linked_data import add_routes

logger = logging.getLogger(__name__)

# đường dẫn cần graph: chưa nạp xong thì trả 503 thay vì lỗi 500
NEEDS_GRAPH = ("/api/", "/sparql", "/resource/", "/data/", "/ontology/", "/page/")
# không bao giờ trả index.html cho các đường dẫn này (sai đường dẫn thì phải 404)
NOT_SPA = ("api/", "sparql", "resource/", "data/", "ontology/", "page/", "assets/")


def create_app(dataset_file: str = DATASET + ".nt") -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        load_dotenv()
        setup_logging()
        # nạp ở thread nền để server nhận request ngay và /api/health báo được tiến độ
        threading.Thread(target=kg.load, args=(dataset_file,), daemon=True).start()
        yield

    app = FastAPI(title="Vietnamese DBpedia UI API", docs_url="/api/docs", redoc_url=None, lifespan=lifespan)

    @app.middleware("http")
    async def wait_for_graph(request, call_next):
        path = request.url.path
        if not kg.ready and path.startswith(NEEDS_GRAPH) and path != "/api/health":
            body = {"error": kg.error or "Đang nạp graph, thử lại sau ít giây.", "ready": False}
            return JSONResponse(body, status_code=503, headers={"Retry-After": "5"})
        return await call_next(request)

    @app.get("/api/health")
    def health():
        return {
            "ready": kg.ready,
            "asserted_ready": kg.asserted_ready.is_set() and kg.asserted is not None,
            "llm": kg.llm,
            "message": kg.message,
            "error": kg.error,
        }

    app.include_router(overview.router)
    app.include_router(entity.router)
    app.include_router(ask.router)
    app.include_router(sparql.router)
    add_routes(app, LazyView())  # Linked Data của team: /resource, /page, /data, /ontology
    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI):
    """Phục vụ ui/web/dist (nếu đã build). Đăng ký cuối cùng để route catch-all không che route khác."""
    index = WEB_INDEX
    if not os.path.exists(index):

        @app.get("/", include_in_schema=False)
        def no_frontend():
            return PlainTextResponse(
                "Chưa build frontend. Chạy: cd ui/web && npm install && npm run build "
                "(hoặc dùng npm run dev ở cổng 5173).",
                status_code=404,
            )

        return

    app.mount("/assets", StaticFiles(directory=os.path.join(WEB_DIST, "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith(NOT_SPA):
            return PlainTextResponse("Không tìm thấy.", status_code=404)
        candidate = os.path.realpath(os.path.join(WEB_DIST, path))
        if path and candidate.startswith(os.path.realpath(WEB_DIST) + os.sep) and os.path.isfile(candidate):
            return FileResponse(candidate, media_type=mimetypes.guess_type(candidate)[0])
        return FileResponse(index)
