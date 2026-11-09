-- Changeset 009: Retire completely unused legacy tables.
-- Purges column_mapping, upload_attribute_schema, and eval_results.
-- Preserves quarantine (active for bad row lineage & CSV downloads) and sales_clean view (active for Superstore benchmarks).

DROP TABLE IF EXISTS public.column_mapping CASCADE;
DROP TABLE IF EXISTS public.upload_attribute_schema CASCADE;
DROP TABLE IF EXISTS public.eval_results CASCADE;

