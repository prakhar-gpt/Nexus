"""Pydantic schemas for the Nexus API."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    thread_id: str | None = Field(default=None, max_length=100)


class ThreadCreate(BaseModel):
    title: str | None = Field(default="New Conversation", max_length=200)


class MappingUpdate(BaseModel):
    decisions: dict[str, str]


class FeedbackRequest(BaseModel):
    rating: Literal["up", "down"]
    reason: str | None = None
