"""Typed request and result contracts for evidence_brief_v1."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EvidenceBriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=32_768)
    files: list[str] = Field(min_length=1, max_length=20)
    write_artifacts: bool = False


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    quote: str = Field(min_length=1)


class EvidenceBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    citations: list[Citation]
    uncertainties: list[str]
    next_decisions: list[str]


class EvidenceBriefResponse(EvidenceBrief):
    request_digest: str
    workflow_id: str
    markdown: str
