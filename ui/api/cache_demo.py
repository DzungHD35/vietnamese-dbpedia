"""Sinh lại `demo_cache.json`: cho LLM trả lời từng câu trong DEMO_QUESTIONS (cần OPENAI_API_KEY).

    .venv/bin/python -m ui.api.cache_demo

Bản đang commit do tay viết (origin = "manual", answer = null) để demo chạy được khi không có key.
Chạy lệnh này khi có key để có thêm câu trả lời; kiểm tra kỹ SPARQL mới trước khi commit.
"""

import json
import os
import sys
from datetime import date

from dotenv import load_dotenv

from ui.api.presets import DEMO_QUESTIONS
from ui.api.routes.ask import CACHE_FILE
from vidbpedia.common import DATASET, setup_logging
from vidbpedia.web.kg_rag import SparqlBasedKGRAG
from vidbpedia.web.sparql import SparqlService


def main() -> int:
    load_dotenv()
    setup_logging()
    if not os.getenv("OPENAI_API_KEY"):
        print("Chưa có OPENAI_API_KEY (thêm vào .env). Giữ nguyên demo_cache.json hiện tại.", file=sys.stderr)
        return 1
    rag = SparqlBasedKGRAG(SparqlService(DATASET + ".nt").graph)
    entries = []
    for question in DEMO_QUESTIONS:
        result = rag.query(question)
        status = "LỖI" if result["error"] else f"{len(result['rows'])} dòng"
        print(f"- {question} → {status}")
        entries.append(
            {
                "question": question,
                "sparql": result["sparql"],
                "answer": result["answer"],
                "reasoning": result["reasoning"],
                "generated_at": date.today().isoformat(),
                "origin": "llm",
            }
        )
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Đã ghi {len(entries)} câu vào {CACHE_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
