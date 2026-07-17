import json
from pathlib import Path
import pytest

from app import generation


class FakeResponse:
    def __init__(self, content=None, provider_error=False):
        self.content = content
        self.provider_error = provider_error

    def raise_for_status(self):
        if self.provider_error:
            import httpx
            raise httpx.HTTPStatusError("bad gateway", request=None, response=None)

    def json(self):
        return {"choices": [{"message": {"content": self.content}}]}


def valid_payload(node_id="node-1"):
    case = {"title": "Case", "preconditions": [], "steps": ["Act"],
            "expected_result": "Expected", "source_node_ids": [node_id]}
    return json.dumps({"test_cases": [case, case, case]})


def test_live_generation_retries_invalid_structured_output(monkeypatch):
    responses = iter([FakeResponse("not json"), FakeResponse(valid_payload())])
    monkeypatch.setattr(generation, "LLM_MODE", "live")
    monkeypatch.setattr(generation, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(generation, "LLM_MAX_RETRIES", 1)
    monkeypatch.setattr(generation.httpx, "post", lambda *args, **kwargs: next(responses))
    cases, model = generation.request_cases("source", ["node-1"])
    assert len(cases.test_cases) == 3


def test_live_generation_rejects_unknown_citations(monkeypatch):
    monkeypatch.setattr(generation, "LLM_MODE", "live")
    monkeypatch.setattr(generation, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(generation, "LLM_MAX_RETRIES", 0)
    monkeypatch.setattr(generation.httpx, "post", lambda *args, **kwargs: FakeResponse(valid_payload("invented")))
    with pytest.raises(RuntimeError, match="invalid structured output"):
        generation.request_cases("source", ["node-1"])


def test_provider_failure_becomes_controlled_runtime_error(monkeypatch):
    monkeypatch.setattr(generation, "LLM_MODE", "live")
    monkeypatch.setattr(generation, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(generation.httpx, "post", lambda *args, **kwargs: FakeResponse(provider_error=True))
    with pytest.raises(RuntimeError, match="provider request failed"):
        generation.request_cases("source", ["node-1"])


def test_generation_store_is_readable_and_reports_corruption(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(generation, "GENERATION_STORE", tmp_path)
    record = {"selection_id": 7, "test_cases": []}
    generation.store_generation(record)
    assert generation.load_generation(7) == record
    (tmp_path / "selection-7.json").write_text("{")
    with pytest.raises(RuntimeError, match="unreadable"):
        generation.load_generation(7)
