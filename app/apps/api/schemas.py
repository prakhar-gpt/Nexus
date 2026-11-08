"""Pydantic schemas for the Nexus API."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class MappingUpdate(BaseModel):
    decisions: dict[str, str]


class FeedbackRequest(BaseModel):
    rating: Literal["up", "down"]
    reason: str | None = None

