"""Test màn Hỏi đáp: dùng demo_cache.json và một LLM giả, không gọi LLM thật."""

import json

import pytest

from ui.api.presets import DEMO_QUESTIONS
from ui.api.state import kg

THAN_QUESTION = DEMO_QUESTIONS[0]
ASSERTED_TIMEOUT = 120  # giây


class FakeClient:
    """Giả `openai.OpenAI`: trả câu SPARQL cố định, hoặc JSON câu trả lời khi prompt là ANSWER_TEMPLATE."""

    def __init__(self):
        self.chat = self
        self.completions = self
        self.prompts: list[str] = []

    def create(self, model, messages, **_):
        prompt = messages[0]["content"]
        self.prompts.append(prompt)
        if prompt.startswith("Bạn là trợ lý hỏi đáp"):
            text = json.dumps({"reasoning": "1. XÁC ĐỊNH: đếm.", "answer": "Có 1 tỉnh."})
        else:
            text = "SELECT (COUNT(DISTINCT ?p) AS ?n) WHERE { ?p a vio:Province }"
        message = type("M", (), {"content": text})
        return type("R", (), {"choices": [type("C", (), {"message": message})]})


@pytest.fixture
def fake_llm(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(kg.rag, "_client", fake)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    return fake


@pytest.fixture
def no_llm(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def wait_asserted():
    assert kg.asserted_ready.wait(ASSERTED_TIMEOUT), "Graph chỉ khai báo chưa nạp xong"
    assert kg.asserted is not None, kg.asserted_error


def test_all_demo_questions_run_from_cache(client, no_llm):
    for q in DEMO_QUESTIONS:
        d = client.post("/api/ask", json={"question": q}).json()
        assert d["source"] == "cache" and d["error"] is None, q
        assert d["rowsTotal"] > 0 and d["columns"], q
        assert d["evidence"], q


def test_cache_matches_without_diacritics_and_punctuation(client, no_llm):
    d = client.post("/api/ask", json={"question": "cau thu nao tung choi cho than quang ninh"}).json()
    assert d["source"] == "cache"


def test_than_quang_ninh_inference_contrast(client, no_llm):
    wait_asserted()
    d = client.post("/api/ask", json={"question": THAN_QUESTION, "mode": "cache"}).json()
    assert d["rowsTotal"] == 39
    assert d["asserted"] == {"rows": 0, "status": "ok"}
    assert "vio:playedFor" in d["sparql"]
    # ô IRI cầu thủ biến thành link, đồ thị bằng chứng có cả CLB
    assert any(n["kind"] == "player" for n in d["evidence"])
    assert any(n["kind"] == "club" for n in d["evidence"])


def test_evidence_subgraph_is_star_of_inferred_edges(client, no_llm):
    d = client.post("/api/ask", json={"question": THAN_QUESTION}).json()
    ids = [n["id"] for n in d["evidence"]]
    sub = client.get("/api/subgraph", params={"ids": ids}).json()
    assert len(sub["edges"]) == 39 and all(e["inferred"] for e in sub["edges"])


def test_links_resolve_iris_and_external(client, no_llm):
    d = client.post("/api/ask", json={"question": DEMO_QUESTIONS[4]}).json()
    assert any(n.get("external") and n["kind"] == "lod" for n in d["links"].values())
    assert any(n["kind"] == "uni" for n in d["links"].values())


def test_unknown_question_without_llm_is_503(client, no_llm):
    r = client.post("/api/ask", json={"question": "Câu hỏi lạ chưa có trong cache?"})
    assert r.status_code == 503 and "OPENAI_API_KEY" in r.json()["detail"]


def test_cache_mode_unknown_question_is_404(client, fake_llm):
    r = client.post("/api/ask", json={"question": "Câu hỏi lạ chưa có trong cache?", "mode": "cache"})
    assert r.status_code == 404


def test_empty_question_is_422(client):
    assert client.post("/api/ask", json={"question": "  "}).status_code == 422


def test_llm_path_with_fake_client(client, fake_llm):
    d = client.post("/api/ask", json={"question": "Có bao nhiêu tỉnh?"}).json()
    assert d["source"] == "llm" and d["attempts"] == 1 and d["error"] is None
    assert d["rows"][0]["n"].isdigit()
    a = client.post(
        "/api/ask/answer", json={"question": d["question"], "sparql": d["sparql"], "rows": d["rows"]}
    ).json()
    assert a == {"answer": "Có 1 tỉnh.", "reasoning": "1. XÁC ĐỊNH: đếm.", "source": "llm"}
    assert "Có bao nhiêu tỉnh?" in fake_llm.prompts[-1] and "n=" in fake_llm.prompts[-1]


def test_answer_without_llm_or_cached_answer_is_null(client, no_llm):
    d = client.post("/api/ask", json={"question": THAN_QUESTION}).json()
    a = client.post(
        "/api/ask/answer", json={"question": THAN_QUESTION, "sparql": d["sparql"], "rows": d["rows"]}
    ).json()
    assert a["answer"] is None and a["source"] == "none"


def test_asserted_endpoint_matches(client, no_llm):
    wait_asserted()
    d = client.post("/api/ask", json={"question": THAN_QUESTION}).json()
    r = client.post("/api/ask/asserted", json={"sparql": d["sparql"]}).json()
    assert r["rows"] == 0 and r["status"] == "ok"


def test_health_reports_llm_flag(client, no_llm):
    assert client.get("/api/health").json()["llm"] is False
