"""Màn Hỏi đáp: /api/ask (SPARQL + kết quả + so sánh suy luận), /api/ask/answer (câu trả lời của LLM)."""

import json
import os
import re
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ui.api import adapters
from ui.api.links import build_links
from ui.api.state import kg
from vidbpedia.kg.query import prepare
from vidbpedia.web.resource_page import fold

router = APIRouter(prefix="/api")

MAX_ROWS = 200
MAX_EVIDENCE = 60
CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demo_cache.json")
NO_LLM = "Chế độ demo: chưa có OPENAI_API_KEY nên chỉ trả lời được các câu hỏi mẫu."


class AskBody(BaseModel):
    question: str
    mode: Literal["auto", "cache", "llm"] = "auto"


class AnswerBody(BaseModel):
    question: str
    sparql: str
    rows: list[dict[str, str]]
    mode: Literal["auto", "cache", "llm"] = "auto"


class AssertedBody(BaseModel):
    sparql: str


def _norm(question: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", fold(question)).split())


@lru_cache(maxsize=1)
def _cache() -> dict[str, dict]:
    with open(CACHE_FILE, encoding="utf-8") as f:
        return {_norm(e["question"]): e for e in json.load(f)}


def _cached(question: str) -> dict | None:
    return _cache().get(_norm(question))


def asserted_rows(sparql: str) -> dict:
    """Chạy lại câu SPARQL chỉ trên triple khai báo → {rows, status, error?}; chưa nạp xong thì 'loading'."""
    if not kg.asserted_ready.is_set():
        return {"rows": None, "status": "loading"}
    if kg.asserted is None:
        return {
            "rows": None,
            "status": "error",
            "error": kg.asserted_error or "Chưa nạp được graph khai báo.",
        }
    try:
        result = kg.asserted.query(prepare(sparql, allow_remote=False))
        n = int(bool(result.askAnswer)) if result.type == "ASK" else len(result)
    except Exception as e:
        return {"rows": None, "status": "error", "error": str(e)}
    return {"rows": n, "status": "ok"}


@router.post("/ask")
def ask(body: AskBody):
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Câu hỏi đang trống.")
    entry = None if body.mode == "llm" else _cached(question)
    if entry is not None:
        source, sparql, attempts = "cache", entry["sparql"], 1
        try:
            columns, rows = kg.rag.run_sparql(sparql)
            error = None
        except Exception as e:
            columns, rows, error = [], [], str(e)
    else:
        if body.mode == "cache":
            raise HTTPException(status_code=404, detail="Câu hỏi này không có trong bộ nhớ đệm của demo.")
        if not kg.llm:
            raise HTTPException(status_code=503, detail=NO_LLM)
        try:
            run = kg.rag.generate_and_run(question)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Không gọi được LLM: {e}") from e
        source, sparql, attempts = "llm", run["sparql"], run["attempts"]
        columns, rows, error = run["columns"], run["rows"], run["error"]

    shown = rows[:MAX_ROWS]
    links = build_links(shown)
    evidence = list({n["id"]: n for n in links.values()}.values())[:MAX_EVIDENCE]
    return {
        "question": question,
        "source": source,
        "sparql": sparql,
        "attempts": attempts,
        "error": error,
        "columns": columns,
        "rows": shown,
        "rowsTotal": len(rows),
        "links": links,
        "evidence": evidence,
        "asserted": asserted_rows(sparql) if sparql and not error else {"rows": None, "status": "error"},
    }


@router.post("/ask/asserted")
def ask_asserted(body: AssertedBody):
    """Hỏi lại số dòng khi chỉ dùng triple khai báo (frontend gọi khi /api/ask báo 'loading')."""
    return asserted_rows(body.sparql)


@router.post("/ask/answer")
def ask_answer(body: AnswerBody):
    entry = None if body.mode == "llm" else _cached(body.question)
    if entry is not None and entry.get("answer"):
        return {"answer": entry["answer"], "reasoning": entry.get("reasoning", ""), "source": "cache"}
    if not kg.llm:
        return {"answer": None, "reasoning": "", "source": "none", "note": NO_LLM}
    try:
        answer, reasoning = adapters.answer(kg.rag, body.question, body.sparql, body.rows)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Không gọi được LLM: {e}") from e
    return {"answer": answer, "reasoning": reasoning, "source": "llm"}
