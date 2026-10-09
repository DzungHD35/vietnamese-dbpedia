"""Màn Hỏi đáp, theo từng bước để giao diện chỉ ra hệ thống làm gì:

① /api/ask/link     nhận diện thực thể trong câu hỏi (chỉ mục tên, không cần dấu)
②③④ /api/ask        sinh SPARQL (LLM, kèm các lần tự sửa) hoặc lấy SPARQL viết sẵn → kiểm tra → chạy trên graph,
                    kèm so sánh có / không suy luận
⑤ /api/ask/answer   LLM viết câu trả lời từ bảng kết quả
⑥ bằng chứng: frontend gọi /api/subgraph với các thực thể trong kết quả

Nguồn SPARQL (`mode`): "auto" dùng LLM khi có OPENAI_API_KEY, không có key thì dùng SPARQL viết sẵn của câu hỏi mẫu;
"llm" luôn gọi LLM; "cache" chỉ dùng SPARQL viết sẵn (demo không cần mạng). Ở "auto", gọi LLM lỗi mà câu hỏi có
SPARQL viết sẵn thì dùng bản đó và ghi lý do.
"""

import json
import os
import re
import time
from collections import OrderedDict
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ui.api import adapters, linking, llm_errors, qa
from ui.api.links import build_links
from ui.api.state import kg
from vidbpedia.kg.query import prepare
from vidbpedia.web.resource_page import fold

router = APIRouter(prefix="/api")

MAX_ROWS = 200
MAX_EVIDENCE = 60
CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demo_cache.json")
NO_LLM = "Chế độ demo: chưa có OPENAI_API_KEY nên chỉ trả lời được các câu hỏi mẫu."
# Kết quả LLM đã có trong phiên: hỏi lại cùng câu (bấm chip, nút Back, đổi công tắc) không tốn thêm request.
# Gói miễn phí của nhà cung cấp thường chỉ vài chục request mỗi ngày. Khoá có cả model để đổi model là hỏi lại.
MEMO_SIZE = 64
_runs: OrderedDict = OrderedDict()
_answers: OrderedDict = OrderedDict()


def clear_memo():
    _runs.clear()
    _answers.clear()


def _remember(store: OrderedDict, key, value):
    store[key] = value
    store.move_to_end(key)
    while len(store) > MEMO_SIZE:
        store.popitem(last=False)


class LinkBody(BaseModel):
    question: str


class AskBody(BaseModel):
    question: str
    mode: Literal["auto", "cache", "llm"] = "auto"
    fresh: bool = False  # bỏ qua kết quả LLM đã có trong phiên


class AnswerBody(BaseModel):
    question: str
    sparql: str
    rows: list[dict[str, str]]
    mode: Literal["auto", "cache", "llm"] = "auto"
    fresh: bool = False


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


def _question(text: str) -> str:
    question = text.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Câu hỏi đang trống.")
    return question


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


@router.post("/ask/link")
def ask_link(body: LinkBody):
    """Bước ①: thực thể nhắc tới trong câu hỏi; nhanh (vài ms) nên frontend hiện trước khi LLM chạy xong."""
    return linking.link(_question(body.question))


def _generate(question: str, mode: str, linked: dict, fresh: bool) -> dict:
    """Bước ②: → {source, sparql, columns, rows, error, attempts, prompt, fallback, reused}."""
    entry = None if mode == "llm" else _cached(question)
    use_llm = mode == "llm" or (mode == "auto" and kg.llm)
    fallback = None
    if use_llm:
        if not kg.llm:
            raise HTTPException(status_code=503, detail=NO_LLM)
        hints = linking.hint_text(linked["mentions"])
        key = (_norm(question), hints, kg.rag.model)
        if not fresh and key in _runs:
            _runs.move_to_end(key)
            return {**_runs[key], "reused": True}
        try:
            run = qa.generate(kg.rag, question, hints, linked["mentions"])
        except Exception as e:
            friendly = llm_errors.explain(e, kg.rag.model)
            if entry is None:
                raise friendly from e
            fallback = f"{friendly.detail} Câu này là câu mẫu nên dùng SPARQL viết sẵn."
        else:
            out = {
                **run,
                "source": "llm",
                "prompt": qa.prompt_text(kg.rag, question, hints),
                "fallback": None,
            }
            if not run["error"]:
                _remember(_runs, key, out)
            return {**out, "reused": False}
    if entry is None:
        if mode == "cache":
            raise HTTPException(status_code=404, detail="Câu hỏi này không có SPARQL viết sẵn trong demo.")
        raise HTTPException(status_code=503, detail=NO_LLM)
    run = qa.from_cache(kg.rag, entry["sparql"])
    return {**run, "source": "cache", "prompt": None, "fallback": fallback, "reused": False}


@router.post("/ask")
def ask(body: AskBody):
    question = _question(body.question)
    linked = linking.link(question)
    gen = _generate(question, body.mode, linked, body.fresh)
    sparql, rows, error = gen["sparql"], gen["rows"], gen["error"]
    ok = bool(sparql) and not error
    shown = rows[:MAX_ROWS] if ok else []
    links = build_links(shown)
    evidence = list({n["id"]: n for n in links.values()}.values())[:MAX_EVIDENCE]
    return {
        "question": question,
        "source": gen["source"],
        "sparql": sparql,
        "attempts": len(gen["attempts"]),
        "error": error,
        "columns": gen["columns"] if ok else [],
        "rows": shown,
        "rowsTotal": len(rows) if ok else 0,
        "links": links,
        "evidence": evidence,
        "asserted": asserted_rows(sparql) if ok else {"rows": None, "status": "error"},
        "steps": {
            "link": linked,
            "generate": {
                "source": gen["source"],
                "attempts": gen["attempts"],
                "prompt": gen["prompt"],
                "fallback": gen["fallback"],
                "reused": gen["reused"],
            },
            "checks": qa.checks(sparql, linked["mentions"], gen["source"], kg.graph) if sparql else [],
            "terms": qa.terms(kg.view, kg.graph, sparql) if ok else [],
            "run": {"ms": gen["attempts"][-1]["runMs"], "rows": len(rows) if ok else 0},
        },
    }


@router.post("/ask/asserted")
def ask_asserted(body: AssertedBody):
    """Hỏi lại số dòng khi chỉ dùng triple khai báo (frontend gọi khi /api/ask báo 'loading')."""
    return asserted_rows(body.sparql)


@router.post("/ask/answer")
def ask_answer(body: AnswerBody):
    """Bước ⑤: câu trả lời bằng chữ, chỉ dựa trên bảng kết quả."""
    entry = None if body.mode == "llm" else _cached(body.question)
    # câu trả lời viết sẵn chỉ hợp với đúng câu SPARQL viết sẵn; SPARQL do LLM sinh thì phải trả lời lại
    if entry is not None and entry.get("answer") and body.sparql.strip() == entry["sparql"].strip():
        return {
            "answer": entry["answer"],
            "reasoning": entry.get("reasoning", ""),
            "source": "cache",
            "ms": 0,
        }
    if not kg.llm:
        return {"answer": None, "reasoning": "", "source": "none", "note": NO_LLM, "ms": 0}
    shown = body.rows[: kg.rag.max_rows_for_answer]
    key = (_norm(body.question), body.sparql.strip(), json.dumps(shown, sort_keys=True), kg.rag.model)
    if not body.fresh and key in _answers:
        _answers.move_to_end(key)
        return {**_answers[key], "reused": True}
    # ngôn ngữ trả lời và tên trùng nhiều thực thể: báo thẳng cho LLM ở cuối prompt
    notes = qa.answer_notes(body.question, linking.link(body.question)["mentions"])
    t0 = time.perf_counter()
    try:
        answer, reasoning = adapters.answer(kg.rag, body.question, body.sparql, body.rows, notes)
    except Exception as e:
        raise llm_errors.explain(e, kg.rag.model) from e
    ms = round((time.perf_counter() - t0) * 1000, 1)
    out = {"answer": answer, "reasoning": reasoning, "source": "llm", "ms": ms}
    _remember(_answers, key, out)
    return {**out, "reused": False}
