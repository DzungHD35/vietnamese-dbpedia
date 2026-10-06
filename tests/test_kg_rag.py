"""Luồng hỏi đáp (vidbpedia/web/kg_rag.py) với LLM giả lập, không cần API key.

pytest tests/test_kg_rag.py -v
"""

import json
import logging
from types import SimpleNamespace

import pytest

from vidbpedia.web.kg_rag import SparqlBasedKGRAG

logging.getLogger("rdflib.term").setLevel(logging.CRITICAL)


BROKEN_SPARQL = "SELECT ?x WHERE { ?x a vio:University "  # thiếu dấu đóng
CAN_THO_SPARQL = """SELECT ?label ?abstract WHERE {
  ?u a vio:University ; rdfs:label ?label .
  FILTER(?label = "Đại học Cần Thơ"@vi)
  OPTIONAL { ?u dbo:abstract ?abstract }
} LIMIT 5"""


class FakeClient:
    """Giả lập openai client: trả lần lượt các phản hồi cho trước, ghi lại prompt đã nhận."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, messages, **kwargs):
        self.prompts.append(messages[0]["content"])
        content = self.replies.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def test_generate_and_run_repairs_and_skips_answer_call(graph):
    """SPARQL mode: lỗi lần 1 được sửa ở lần 2, và không gọi LLM viết câu trả lời."""
    fake = FakeClient([BROKEN_SPARQL, f"```sparql\n{CAN_THO_SPARQL}\n```"])
    result = SparqlBasedKGRAG(graph, client=fake).generate_and_run("Đại học Cần Thơ thành lập năm nào?")

    assert result["error"] is None
    assert result["attempts"] == 2
    assert result["columns"] == ["label", "abstract"]
    assert "1966" in result["rows"][0]["abstract"]
    assert len(fake.prompts) == 2  # chỉ 2 lần sinh SPARQL, không có bước trả lời
    assert "Truy vấn này lỗi" in fake.prompts[1]
    assert "answer" not in result


def test_query_returns_answer_and_reasoning(graph):
    """Chế độ thường: LLM trả JSON trong khối ```json, tách được answer và reasoning."""
    cot = json.dumps(
        {
            "reasoning": "1. XÁC ĐỊNH: cần năm thành lập.\n2. TÌM: abstract ghi 1966.",
            "answer": "Đại học Cần Thơ được thành lập năm 1966.",
        },
        ensure_ascii=False,
    )
    fake = FakeClient([CAN_THO_SPARQL, f"```json\n{cot}\n```"])
    result = SparqlBasedKGRAG(graph, client=fake).query("Đại học Cần Thơ thành lập năm nào?")

    assert result["answer"] == "Đại học Cần Thơ được thành lập năm 1966."
    assert result["reasoning"].startswith("1. XÁC ĐỊNH")
    assert result["attempts"] == 1
    assert len(fake.prompts) == 2  # 1 lần sinh SPARQL + 1 lần trả lời


def test_query_reports_error_after_failed_repair(graph):
    """Hai lần đều sai cú pháp: trả lỗi, không gọi bước trả lời."""
    fake = FakeClient([BROKEN_SPARQL, BROKEN_SPARQL])
    result = SparqlBasedKGRAG(graph, client=fake).query("câu hỏi bất kỳ")

    assert result["error"]
    assert result["rows"] == []
    assert result["answer"].startswith("Không tạo được truy vấn hợp lệ")
    assert len(fake.prompts) == 2


def test_parse_answer_falls_back_to_plain_text():
    assert SparqlBasedKGRAG._parse_answer("Câu trả lời thường") == ("Câu trả lời thường", "")


def test_rejects_write_queries(graph):
    rag = SparqlBasedKGRAG(graph, client=FakeClient([]))
    for bad in ["CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }", "DELETE WHERE { ?s ?p ?o }"]:
        with pytest.raises(Exception):
            rag.run_sparql(bad)
