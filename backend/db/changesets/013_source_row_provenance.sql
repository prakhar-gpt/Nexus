-- Changeset 013: Source row provenance support in dynamic custom tables.
-- Ingest compiles source_row bigint into user_data.ds_* tables to map records directly
-- back to their original physical row in uploaded CSV/XLSX workbooks (matching quarantine.row_number).
-- Note: No backfill is applied to pre-existing datasets; source_row is populated dynamically
-- on newly approved datasets upon COPY ingest.

COMMENT ON SCHEMA user_data IS 'Isolated user dataset tables with RLS and physical file source_row tracking.';

