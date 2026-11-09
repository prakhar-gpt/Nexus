from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class ColumnProposal(BaseModel):
    source_name: str
    column_name: str
    type: Literal["text", "integer", "numeric", "date", "boolean"]
    role: Literal["identifier", "date", "measure", "dimension", "other"]
    description: str
    unit: str | None = None
    nullable: bool = True
    date_format: str | None = None
    parse_success_rate: float = 1.0
    confidence: float = 1.0
    notes: str | None = None
    excluded: bool = False


class SchemaProposal(BaseModel):
    table_label: str
    grain: str
    grain_key_columns: list[str] = Field(default_factory=list)
    columns: list[ColumnProposal]
    warnings: list[str] = Field(default_factory=list)
    analysis_hints: list[str] = Field(default_factory=list)
    from_cache: bool = False

