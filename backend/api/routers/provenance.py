"""Source provenance endpoints for audit inspection and line-level verification."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from api.dependencies import require_run_access
from api.services.provenance_service import (
    export_rows_behind_query_csv,
    get_rows_behind_query,
    get_source_record,
)
from db.models import Run

router = APIRouter()


@router.get("/runs/{run_id}/source/{query_id}")
def get_source_endpoint(
    run_id: str,
    query_id: str,
    claim_index: int | None = Query(default=None),
    run: Run = Depends(require_run_access),
):
    """Fetch stored call record for a specific query without executing any new queries."""
    return get_source_record(run, query_id, claim_index=claim_index)


@router.get("/runs/{run_id}/source/{query_id}/rows")
def get_source_rows_endpoint(
    run_id: str,
    query_id: str,
    claim_index: int | None = Query(default=None),
    row_index: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    run: Run = Depends(require_run_access),
):
    """View underlying raw rows behind a whitelisted single-table aggregate SQL query."""
    return get_rows_behind_query(run, query_id, limit=limit, claim_index=claim_index, row_index=row_index)


@router.get("/runs/{run_id}/source/{query_id}/rows/export")
def export_source_rows_endpoint(
    run_id: str,
    query_id: str,
    claim_index: int | None = Query(default=None),
    row_index: int | None = Query(default=None),
    run: Run = Depends(require_run_access),
) -> Response:
    """Download all raw rows behind an aggregate SQL claim as a formula-neutralized CSV."""
    return export_rows_behind_query_csv(run, query_id, claim_index=claim_index, row_index=row_index)

