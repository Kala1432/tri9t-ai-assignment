import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import httpx
from pydantic import ValidationError
from .config import GENERATION_STORE, LLM_API_KEY, LLM_BASE_URL, LLM_MAX_RETRIES, LLM_MODE, LLM_MODEL
from .schemas import TestCaseEnvelope

SYSTEM_PROMPT = """You are a medical-device QA analyst. Return only JSON matching:
{"test_cases":[{"title":"...","preconditions":["..."],"steps":["..."],"expected_result":"...","source_node_ids":["uuid"]}]}
Create 3-5 concrete, executable ideas. Use only supplied requirements. Every case must cite at least one supplied node ID."""

def _mock(node_ids: list[str]) -> dict:
    cases = [
        ("Verify stated normal operation", ["Prepare the device as specified"], ["Follow the selected operating instructions", "Observe the displayed result"], "The device completes the operation exactly as specified."),
        ("Reject unsafe or contraindicated use", ["Prepare a condition prohibited by the selected text"], ["Attempt to start a measurement", "Observe warnings and device behavior"], "The unsafe condition is prevented or clearly warned about."),
        ("Verify boundary and safety response", ["Configure a simulator at the documented boundary"], ["Trigger the boundary condition", "Measure response time and displayed error"], "The documented protective response and timing occur."),
    ]
    return {"test_cases": [{"title": a, "preconditions": b, "steps": c, "expected_result": d, "source_node_ids": node_ids} for a,b,c,d in cases]}

def request_cases(context: str, node_ids: list[str]) -> tuple[TestCaseEnvelope, str]:
    if LLM_MODE == "mock":
        return TestCaseEnvelope.model_validate(_mock(node_ids)), "mock"
    if not LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY is required unless LLM_MODE=mock")
    prompt = f"Selected nodes: {', '.join(node_ids)}\n\nSOURCE:\n{context}"
    error = ""
    for attempt in range(LLM_MAX_RETRIES + 1):
        try:
            response = httpx.post(f"{LLM_BASE_URL}/chat/completions", headers={"Authorization": f"Bearer {LLM_API_KEY}"}, json={
                "model": LLM_MODEL, "temperature": 0.2,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt + (f"\nPrevious output was invalid: {error}. Correct it." if error else "")}],
                "response_format": {"type": "json_object"},
            }, timeout=45)
            response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError(f"LLM provider request failed: {exc}") from exc
        try:
            parsed = TestCaseEnvelope.model_validate_json(raw)
            allowed = set(node_ids)
            if any(not set(case.source_node_ids) <= allowed for case in parsed.test_cases):
                raise ValueError("output cited node IDs outside the selection")
            return parsed, LLM_MODEL
        except (ValidationError, ValueError) as exc:
            error = str(exc)
    raise RuntimeError(f"LLM returned invalid structured output after retries: {error}")

def store_generation(record: dict):
    GENERATION_STORE.mkdir(parents=True, exist_ok=True)
    path = GENERATION_STORE / f"selection-{record['selection_id']}.json"
    handle, temporary = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=GENERATION_STORE)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(record, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def load_generation(selection_id: int):
    path = GENERATION_STORE / f"selection-{selection_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Stored generation {selection_id} is unreadable: {exc}") from exc

def list_generations():
    if not GENERATION_STORE.exists():
        return []
    records = []
    for path in sorted(GENERATION_STORE.glob("selection-*.json")):
        try:
            selection_id = int(path.stem.removeprefix("selection-"))
        except ValueError:
            continue
        records.append(load_generation(selection_id))
    return records

def now_iso():
    return datetime.now(timezone.utc).isoformat()
