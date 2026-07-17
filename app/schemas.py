from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class IngestRequest(BaseModel):
    path: str
    document_key: str = "ct-200"

class SelectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    node_ids: list[str] = Field(min_length=1)
    version: Optional[int] = None
    document_key: str = Field(default="ct-200", min_length=1, max_length=100)

class TestCase(BaseModel):
    title: str
    preconditions: list[str]
    steps: list[str] = Field(min_length=1)
    expected_result: str
    source_node_ids: list[str] = Field(min_length=1)

class TestCaseEnvelope(BaseModel):
    test_cases: list[TestCase] = Field(min_length=3, max_length=5)

class GenerateRequest(BaseModel):
    force: bool = False
