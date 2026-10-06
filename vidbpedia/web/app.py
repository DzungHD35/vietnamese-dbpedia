"""Máy chủ: route Linked Data và giao diện Gradio trên cùng một ứng dụng FastAPI.

python -m vidbpedia serve [--host 127.0.0.1] [--port 7860] [--dataset data/vietnamese_dbpedia.nt]
"""

import argparse
import logging
import os
import sys

import gradio as gr
from dotenv import load_dotenv
from fastapi import FastAPI

from vidbpedia.common import DATASET, setup_logging
from vidbpedia.web.linked_data import add_routes
from vidbpedia.web.resource_page import ResourceView
from vidbpedia.web.sparql import SparqlService
from vidbpedia.web.theme import FAVICON
from vidbpedia.web.ui import create_interface

logger = logging.getLogger(__name__)


def create_app(dataset_file):
    service = SparqlService(dataset_file)
    view = ResourceView.from_files(service.graph, dataset_file)
    ui = create_interface(service, view)
    app = FastAPI(title="Vietnamese DBpedia", docs_url=None, redoc_url=None)
    add_routes(app, view)
    app = gr.mount_gradio_app(app, ui, path="/", show_api=False, show_error=True, favicon_path=FAVICON)
    return app, ui


def main():
    ap = argparse.ArgumentParser(description="Giao diện và Linked Data của Vietnamese DBpedia")
    ap.add_argument("--dataset", default=DATASET + ".nt")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7860)
    ap.add_argument("--share", action="store_true", help="link công khai của Gradio (chỉ có giao diện)")
    args = ap.parse_args()
    setup_logging()
    load_dotenv()
    if not os.path.exists(args.dataset):
        sys.exit(f"Chưa có {args.dataset}: chạy python -m vidbpedia postprocess trước.")

    logger.info("Nạp %s…", args.dataset)
    app, ui = create_app(args.dataset)
    if args.share:
        ui.launch(server_name=args.host, server_port=args.port, share=True, show_api=False)
        return
    import uvicorn

    logger.info(
        "Giao diện http://%s:%d/ · Linked Data http://%s:%d/resource/<tên>",
        args.host,
        args.port,
        args.host,
        args.port,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
