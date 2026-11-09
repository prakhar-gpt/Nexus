"""Ingestion module: workbook parsing, schema mapping, database storage, and pipeline execution."""

from ingest.custom_table import (
    build_create_table_ddl,
    create_and_load_custom_table,
)
from ingest.mapping import (
    CANONICAL,
    Proposal,
    compute_capabilities,
    domain_gap,
    normalize,
    normalize_to_snake,
    propose_columns,
)
from ingest.pipeline import (
    IngestResult,
    confirm_mappings,
    ingest,
    reserve_upload,
)
from ingest.reader import (
    RejectedFile,
    TableRejected,
    find_header,
    inspect,
    make_inert,
    parse_date,
    parse_number,
    read_rows,
    stored_name,
)
from ingest.schema_validation import (
    check_column_parse_success,
    validate_schema_proposal,
)
from ingest.store import StoreError, execute, get_writer_connection, sql_literal

__all__ = [
    "CANONICAL",
    "IngestResult",
    "Proposal",
    "RejectedFile",
    "StoreError",
    "TableRejected",
    "build_create_table_ddl",
    "check_column_parse_success",
    "compute_capabilities",
    "confirm_mappings",
    "create_and_load_custom_table",
    "domain_gap",
    "execute",
    "find_header",
    "get_writer_connection",
    "ingest",
    "inspect",
    "make_inert",
    "normalize",
    "normalize_to_snake",
    "parse_date",
    "parse_number",
    "propose_columns",
    "read_rows",
    "reserve_upload",
    "sql_literal",
    "stored_name",
    "validate_schema_proposal",
]
