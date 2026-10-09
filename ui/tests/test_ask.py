"""Test màn Hỏi đáp: dùng demo_cache.json và một LLM giả, không gọi LLM thật."""

import json

import pytest

from ui.api import adapters, linking, llm_errors, qa
from ui.api.presets import DEMO_QUESTIONS, NO_DIACRITICS_EXAMPLE
from ui.api.routes import ask
from ui.api.state import kg

THAN_QUESTION = DEMO_QUESTIONS[0]
QUANG_HAI_QUESTION = DEMO_QUESTIONS[1]
VAN_LAM_QUESTION = DEMO_QUESTIONS[5]
ASSERTED_TIMEOUT = 120  # giây
COUNT_PROVINCES = "SELECT (COUNT(DISTINCT ?p) AS ?n) WHERE { ?p a vio:Province }"
BROKEN = "SELECT ?x WHERE { ?x a vio:Province "  # thiếu dấu đóng


class FakeClient:
    """Giả `openai.OpenAI`: lần lượt trả các câu SPARQL cho trước (câu cuối dùng lại), hoặc JSON câu trả lời
    khi prompt là prompt trả lời; có `error` thì mọi lần gọi đều ném lỗi đó (mất mạng, hết hạn mức…)."""

    def __init__(self, sparqls=(COUNT_PROVINCES,), error=None):
        self.chat = self
        self.completions = self
        self.prompts: list[str] = []
        self.sparqls = list(sparqls)
        self.error = error

    def create(self, model, messages, **_):
        if self.error is not None:
            raise self.error
        prompt = messages[0]["content"]
        self.prompts.append(prompt)
        if prompt.startswith("Bạn là trợ lý hỏi đáp"):
            text = json.dumps({"reasoning": "1. XÁC ĐỊNH: đếm.", "answer": "Có 1 tỉnh."})
        else:
            text = self.sparqls.pop(0) if len(self.sparqls) > 1 else self.sparqls[0]
        message = type("M", (), {"content": text})
        return type("R", (), {"choices": [type("C", (), {"message": message})]})


class ProviderError(Exception):
    """Giống lỗi HTTP của openai SDK: có `status_code`."""

    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


GEMINI_429 = (
    "Error code: 429 - [{'error': {'code': 429, 'message': 'You exceeded your current quota. Please retry in "
    "9h15m29.026990912s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'retryDelay': '33329s'}]}}]"
)


def use_llm(monkeypatch, fake):
    ask.clear_memo()
    monkeypatch.setattr(kg.rag, "_client", fake)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    return fake


@pytest.fixture
def fake_llm(monkeypatch):
    return use_llm(monkeypatch, FakeClient())


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
        steps = d["steps"]
        assert steps["generate"]["source"] == "cache" and steps["generate"]["prompt"] is None, q
        assert [a["status"] for a in steps["generate"]["attempts"]] == ["ok"], q
        assert all(c["status"] != "fail" for c in steps["checks"]), q
        assert steps["run"]["rows"] == d["rowsTotal"], q


def test_cache_matches_without_diacritics_and_punctuation(client, no_llm):
    d = client.post("/api/ask", json={"question": "cau thu nao tung choi cho than quang ninh"}).json()
    assert d["source"] == "cache"


def test_link_without_diacritics_finds_both_quang_hai(client):
    d = client.post("/api/ask/link", json={"question": NO_DIACRITICS_EXAMPLE}).json()
    [mention] = d["mentions"]
    assert mention["text"] == "quang hai" and mention["match"] == "tail"
    assert [c["kind"] for c in mention["candidates"]] == ["player", "player"]
    assert {c["id"][-5:-1] for c in mention["candidates"]} == {"1985", "1997"}


def test_link_prefers_full_names_and_skips_class_words(client):
    def linked(question):
        return [
            (m["text"], [c["label"] for c in m["candidates"]])
            for m in client.post("/api/ask/link", json={"question": question}).json()["mentions"]
        ]

    assert linked("cong phuong da choi cho nhung clb nao") == [("cong phuong", ["Nguyễn Công Phượng"])]
    assert linked("Tỉnh Hà Tây hiện nay thuộc về đâu?") == [("Hà Tây", ["Hà Tây (tỉnh)"])]
    assert linked(THAN_QUESTION) == [("Than Quảng Ninh", ["Câu lạc bộ bóng đá Than Quảng Ninh"])]
    assert linked("Sân vận động nào có sức chứa lớn nhất ở đội tuyển quốc gia?") == []


def test_than_quang_ninh_inference_contrast(client, no_llm):
    wait_asserted()
    d = client.post("/api/ask", json={"question": THAN_QUESTION, "mode": "cache"}).json()
    assert d["rowsTotal"] == 39
    assert d["asserted"] == {"rows": 0, "status": "ok"}
    assert "vio:playedFor" in d["sparql"]
    # ô IRI cầu thủ biến thành link, đồ thị bằng chứng có cả CLB
    assert any(n["kind"] == "player" for n in d["evidence"])
    assert any(n["kind"] == "club" for n in d["evidence"])
    # bước ③: playedFor chỉ có trong phần suy luận
    played = next(t for t in d["steps"]["terms"] if t["term"] == "vio:playedFor")
    assert played["kind"] == "property" and played["total"] == played["inferred"] > 2000


def test_evidence_subgraph_is_star_of_inferred_edges(client, no_llm):
    d = client.post("/api/ask", json={"question": THAN_QUESTION}).json()
    ids = [n["id"] for n in d["evidence"]]
    sub = client.get("/api/subgraph", params={"ids": ids}).json()
    assert len(sub["edges"]) == 39 and all(e["inferred"] for e in sub["edges"])


def test_links_resolve_iris_and_external(client, no_llm):
    d = client.post("/api/ask", json={"question": VAN_LAM_QUESTION}).json()
    assert any(n.get("external") and n["kind"] == "lod" for n in d["links"].values())
    assert any(n["kind"] == "player" for n in d["links"].values())


def test_unknown_question_without_llm_is_503(client, no_llm):
    r = client.post("/api/ask", json={"question": "Câu hỏi lạ chưa có trong cache?"})
    assert r.status_code == 503 and "OPENAI_API_KEY" in r.json()["detail"]


def test_cache_mode_unknown_question_is_404(client, fake_llm):
    r = client.post("/api/ask", json={"question": "Câu hỏi lạ chưa có trong cache?", "mode": "cache"})
    assert r.status_code == 404


def test_empty_question_is_422(client):
    assert client.post("/api/ask", json={"question": "  "}).status_code == 422
    assert client.post("/api/ask/link", json={"question": ""}).status_code == 422


def test_llm_path_with_fake_client(client, fake_llm):
    d = client.post("/api/ask", json={"question": "Có bao nhiêu tỉnh?"}).json()
    assert d["source"] == "llm" and d["attempts"] == 1 and d["error"] is None
    assert d["rows"][0]["n"].isdigit()
    a = client.post(
        "/api/ask/answer", json={"question": d["question"], "sparql": d["sparql"], "rows": d["rows"]}
    ).json()
    assert {k: a[k] for k in ("answer", "reasoning", "source")} == {
        "answer": "Có 1 tỉnh.",
        "reasoning": "1. XÁC ĐỊNH: đếm.",
        "source": "llm",
    }
    assert a["ms"] >= 0
    answer_prompt = fake_llm.prompts[-1]
    assert "Có bao nhiêu tỉnh?" in answer_prompt and "n=" in answer_prompt
    assert adapters.CAREFUL_RULE in answer_prompt and adapters.TRUST_RULE not in answer_prompt
    # hỏi tiếng Anh thì trả lời tiếng Anh
    assert adapters.SAME_LANGUAGE in answer_prompt and adapters.VIETNAMESE_ONLY not in answer_prompt


INVENTED = "<http://vi.dbpedia.org/resource/Trường_Đại_học_Không_Có_Thật>"


def test_invented_iris_are_flagged_and_sent_back_to_the_llm(client, monkeypatch):
    invented_query = f"SELECT ?y WHERE {{ {INVENTED} vio:foundingYear ?y }} LIMIT 5"
    fake = use_llm(monkeypatch, FakeClient(sparqls=[invented_query, COUNT_PROVINCES]))
    d = client.post("/api/ask", json={"question": "Which university in Hue was founded first?"}).json()
    first, second = d["steps"]["generate"]["attempts"]
    assert first["status"] == "empty"
    assert "KHÔNG có trong graph" in second["feedback"] and INVENTED in second["feedback"]
    assert INVENTED in fake.prompts[1]
    flagged = {c["label"]: c for c in qa.checks(invented_query, [], "llm", kg.graph)}
    assert flagged["IRI có trong graph"]["status"] == "fail"
    real = "SELECT ?y WHERE { <http://vi.dbpedia.org/resource/Đại_học_Huế> vio:foundingYear ?y } LIMIT 5"
    assert {c["label"]: c["status"] for c in qa.checks(real, [], "llm", kg.graph)}[
        "IRI có trong graph"
    ] == "ok"


HUE = "<http://vi.dbpedia.org/resource/Huế>"
QUANG_HAI = [
    "<http://vi.dbpedia.org/resource/Nguyễn_Quang_Hải_(cầu_thủ_bóng_đá,_sinh_1985)>",
    "<http://vi.dbpedia.org/resource/Nguyễn_Quang_Hải_(cầu_thủ_bóng_đá,_sinh_1997)>",
]


def test_iri_in_the_wrong_role_is_flagged_and_explained(client, monkeypatch):
    # lỗi gpt-4o-mini đã mắc: lấy IRI của tỉnh Huế làm chính trường đại học → 0 dòng
    wrong = (
        f"SELECT ?u ?y WHERE {{ VALUES ?u {{ {HUE} }} ?u a vio:University ; vio:foundingYear ?y }} LIMIT 5"
    )
    right = f"SELECT ?u ?y WHERE {{ ?u a vio:University ; vio:province {HUE} ; vio:foundingYear ?y }} ORDER BY ?y LIMIT 5"
    statuses = {c["label"]: c["status"] for c in qa.checks(wrong, [], "llm", kg.graph)}
    assert statuses["IRI đúng vai trò"] == "fail"
    use_llm(monkeypatch, FakeClient(sparqls=[wrong, right]))
    d = client.post("/api/ask", json={"question": "Which university in Hue was founded first?"}).json()
    first, second = d["steps"]["generate"]["attempts"]
    assert first["status"] == "empty" and second["status"] == "ok"
    assert "vio:Province" in second["feedback"] and "không phải vio:University" in second["feedback"]
    assert d["rows"][0]["y"] == "1957"


def test_same_name_results_are_split_by_the_system(client, monkeypatch):
    merged = f"SELECT DISTINCT ?club WHERE {{ VALUES ?x {{ {' '.join(QUANG_HAI)} }} ?x vio:playedFor ?club }} LIMIT 50"
    use_llm(monkeypatch, FakeClient(sparqls=[merged]))
    d = client.post("/api/ask", json={"question": NO_DIACRITICS_EXAMPLE}).json()
    llm, system = d["steps"]["generate"]["attempts"]
    assert llm["by"] == "llm" and system["by"] == "system" and system["llmMs"] is None
    assert "?x" in system["feedback"] and d["columns"] == ["x", "club"]
    assert len({r["x"] for r in d["rows"]}) == 2
    checks = {c["label"]: c["status"] for c in d["steps"]["checks"]}
    assert checks["Phân biệt thực thể trùng tên"] == "ok"


def test_no_mention_prompt_searches_whole_phrase_first():
    hint = linking.hint_text([])
    assert "NGUYÊN cụm tên" in hint and "TỪNG từ" in hint


def test_empty_whole_phrase_search_is_split_into_words_on_retry(client, monkeypatch):
    lookup = "SELECT DISTINCT ?s ?cap WHERE {{ ?s a vio:Stadium ; rdfs:label ?n ; vio:capacity ?cap . FILTER({}) }} LIMIT 5"
    whole = lookup.format('CONTAINS(LCASE(STR(?n)), "sân thống nhất")')
    split = lookup.format(" && ".join(f'CONTAINS(LCASE(STR(?n)), "{w}")' for w in ("sân", "thống", "nhất")))
    fake = use_llm(monkeypatch, FakeClient(sparqls=[whole, split]))
    d = client.post("/api/ask", json={"question": "Sức chứa của sân thống nhất là bao nhiêu?"}).json()
    first, second = d["steps"]["generate"]["attempts"]
    assert first["status"] == "empty" and second["status"] == "ok" and d["rowsTotal"] == 1
    expected = 'CONTAINS(LCASE(STR(?n)), "sân") && CONTAINS(LCASE(STR(?n)), "thống") && CONTAINS(LCASE(STR(?n)), "nhất")'
    assert "TỪNG từ" in second["feedback"] and expected in second["feedback"]
    assert expected in fake.prompts[1]
    # hệ thống tự tìm thử nhãn chứa đủ từng từ và báo luôn thực thể, lớp cho LLM
    assert "Sân_vận_động_Thống_Nhất" in second["feedback"] and "vio:Stadium" in second["feedback"]
    assert qa.split_contains('FILTER(CONTAINS(LCASE(STR(?n)), "huế"))') == []  # một từ thì không tách


def test_split_search_reports_class_and_linking_property(client):
    # huấn luyện viên không thuộc lớp chính nên bước 1 không nhận ra; tìm nguyên cụm "kim sang sik" cũng không ra
    [coach] = qa.label_matches(kg.rag, ["kim", "sang", "sik"])
    assert coach["label"] == "Kim Sang-sik" and "vio:Person" in coach["classes"]
    assert ("vio:manager", "vio:NationalFootballTeam", "Đội tuyển bóng đá quốc gia Việt Nam") in coach[
        "links"
    ]
    assert (
        client.post("/api/ask/link", json={"question": "Kim Sang Sik đang dẫn dắt đội nào?"}).json()[
            "mentions"
        ]
        == []
    )


def test_question_language_detection():
    assert qa.question_language("Which clubs did Nguyễn Quang Hải play for?") == "en"
    assert qa.question_language("Which clubs have their home ground in Da Nang?") == "en"
    assert qa.question_language("quang hai da choi cho nhung clb nao") == "vi"
    assert qa.question_language("Câu lạc bộ nào có sân nhà ở Đà Nẵng?") == "vi"


def test_answer_prompt_notes_language_and_same_name_entities(client, fake_llm):
    question = "Which clubs did Nguyen Quang Hai play for?"
    body = {"question": question, "sparql": COUNT_PROVINCES, "rows": [{"n": "110"}]}
    client.post("/api/ask/answer", json=body)
    prompt = fake_llm.prompts[-1]
    assert "the question is in English" in prompt
    assert "ứng với 2 thực thể khác nhau" in prompt and "sinh 1985" in prompt and "sinh 1997" in prompt


def test_same_name_check_flags_merged_results():
    iris = [
        "http://vi.dbpedia.org/resource/Nguyễn_Quang_Hải_(cầu_thủ_bóng_đá,_sinh_1985)",
        "http://vi.dbpedia.org/resource/Nguyễn_Quang_Hải_(cầu_thủ_bóng_đá,_sinh_1997)",
    ]
    mention = [{"text": "quang hai", "match": "tail", "candidates": [{"iri": i} for i in iris]}]
    values = "VALUES ?x { " + " ".join(f"<{i}>" for i in iris) + " }"
    merged = f"SELECT ?club WHERE {{ {values} ?x vio:playedFor ?club }} LIMIT 50"
    split = f"SELECT ?x ?club WHERE {{ {values} ?x vio:playedFor ?club }} LIMIT 50"

    def status(sparql):
        return {c["label"]: c["status"] for c in qa.checks(sparql, mention, "llm")}[
            "Phân biệt thực thể trùng tên"
        ]

    assert status(merged) == "warn" and status(split) == "ok"


def test_english_question_links_english_labels(client):
    d = client.post(
        "/api/ask/link", json={"question": "What is the capacity of My Dinh National Stadium?"}
    ).json()
    assert [c["label"] for m in d["mentions"] for c in m["candidates"]] == ["Sân vận động Quốc gia Mỹ Đình"]


def test_auto_mode_with_key_asks_llm_even_for_demo_questions(client, fake_llm):
    d = client.post("/api/ask", json={"question": THAN_QUESTION}).json()
    assert d["source"] == "llm"
    gen = d["steps"]["generate"]
    # prompt hiển thị đúng prompt đã gửi, kèm IRI nhận diện ở bước ①
    assert gen["prompt"] == fake_llm.prompts[0]
    assert "Thực thể đã nhận diện" in gen["prompt"]
    assert "<http://vi.dbpedia.org/resource/Câu_lạc_bộ_bóng_đá_Than_Quảng_Ninh>" in gen["prompt"]


def test_repair_attempts_are_traced(client, monkeypatch):
    fake = use_llm(monkeypatch, FakeClient(sparqls=[BROKEN, COUNT_PROVINCES]))
    d = client.post("/api/ask", json={"question": "Có bao nhiêu tỉnh?"}).json()
    first, second = d["steps"]["generate"]["attempts"]
    assert first["status"] == "error" and first["error"] and first["feedback"] is None
    assert second["status"] == "ok" and "Truy vấn này lỗi" in second["feedback"]
    assert d["attempts"] == 2 and d["error"] is None
    assert "Truy vấn này lỗi" in fake.prompts[1]


def test_llm_error_falls_back_to_written_sparql(client, monkeypatch):
    use_llm(monkeypatch, FakeClient(error=ConnectionError("mất mạng")))
    d = client.post("/api/ask", json={"question": THAN_QUESTION}).json()
    assert d["source"] == "cache" and "mất mạng" in d["steps"]["generate"]["fallback"]
    assert d["rowsTotal"] == 39
    r = client.post("/api/ask", json={"question": "Câu hỏi lạ chưa có trong cache?"})
    assert r.status_code == 502


def test_checks_flag_unsafe_or_unbounded_queries():
    def status(sparql):
        return {c["label"]: c["status"] for c in qa.checks(sparql, [], "llm")}

    assert status("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }")["Chỉ đọc"] == "fail"
    assert (
        status("SELECT * WHERE { SERVICE <http://x.org/sparql> { ?s ?p ?o } }")["Không gọi dữ liệu bên ngoài"]
        == "fail"
    )
    assert status("SELECT ?s WHERE { ?s a vio:Stadium }")["Giới hạn số dòng"] == "warn"
    assert status(COUNT_PROVINCES)["Giới hạn số dòng"] == "ok"
    assert qa.checks(BROKEN, [], "llm")[0]["status"] == "fail"


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


def test_quang_hai_demo_lists_both_players(client, no_llm):
    d = client.post("/api/ask", json={"question": QUANG_HAI_QUESTION}).json()
    players = {r["player"] for r in d["rows"]}
    assert len(players) == 2


def test_same_question_reuses_llm_result_until_fresh(client, monkeypatch):
    fake = use_llm(monkeypatch, FakeClient())
    question = {"question": "Có bao nhiêu tỉnh thành?"}
    first = client.post("/api/ask", json=question).json()
    assert first["steps"]["generate"]["reused"] is False
    calls = len(fake.prompts)
    again = client.post("/api/ask", json=question).json()
    assert again["steps"]["generate"]["reused"] is True and len(fake.prompts) == calls
    assert again["sparql"] == first["sparql"] and again["rowsTotal"] == first["rowsTotal"]
    fresh = client.post("/api/ask", json={**question, "fresh": True}).json()
    assert fresh["steps"]["generate"]["reused"] is False and len(fake.prompts) == calls + 1

    body = {"question": question["question"], "sparql": first["sparql"], "rows": first["rows"]}
    a1 = client.post("/api/ask/answer", json=body).json()
    a2 = client.post("/api/ask/answer", json=body).json()
    assert a1["reused"] is False and a2["reused"] is True and a2["answer"] == a1["answer"]
    assert len(fake.prompts) == calls + 2


def test_quota_error_is_explained_and_demo_questions_fall_back(client, monkeypatch):
    use_llm(monkeypatch, FakeClient(error=ProviderError(429, GEMINI_429)))
    r = client.post("/api/ask", json={"question": "Câu hỏi lạ chưa có trong cache?"})
    detail = r.json()["detail"]
    assert r.status_code == 429 and "hết hạn mức" in detail and "9 giờ 15 phút" in detail
    assert "RESOURCE_EXHAUSTED" not in detail  # không đổ khối JSON của nhà cung cấp ra màn hình
    d = client.post("/api/ask", json={"question": THAN_QUESTION}).json()
    assert d["source"] == "cache" and "hết hạn mức" in d["steps"]["generate"]["fallback"]


def test_wrong_model_and_key_are_explained():
    model = llm_errors.explain(ProviderError(404, "The model `gpt-4o.0` does not exist"), "gpt-4o.0")
    assert model.status_code == 502 and "OPENAI_MODEL" in model.detail and "gpt-4o.0" in model.detail
    key = llm_errors.explain(ProviderError(401, "Incorrect API key provided"), "gpt-4o")
    assert "OPENAI_API_KEY" in key.detail
    assert llm_errors._wait("'retryDelay': '45s'") == "45 giây"
