"""python -m ui.api [--host 127.0.0.1] [--port 8000] [--dataset data/vietnamese_dbpedia.nt]"""

import argparse
import os
import sys

import uvicorn

from ui.api.app import create_app
from vidbpedia.common import DATASET


def main():
    ap = argparse.ArgumentParser(description="API JSON + giao diện demo của Vietnamese DBpedia")
    ap.add_argument("--dataset", default=DATASET + ".nt")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    if not os.path.exists(args.dataset):
        sys.exit(f"Chưa có {args.dataset}: chạy python -m vidbpedia postprocess trước.")
    uvicorn.run(create_app(args.dataset), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
