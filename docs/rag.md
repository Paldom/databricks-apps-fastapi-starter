# Documents: ingestion into AI Search

Upload → file-arrival Lakeflow Job → AI Search index → knowledge specialist, filtered by the uploading user.

## Upload

`POST /api/knowledge/files` stores the file under a per-user path in the bundle volume
(`resources/rag_upload_volume.volume.yml`) and creates a `pending` document record first, so a failed upload
leaves nothing behind. The volume is bound with `WRITE_VOLUME`; with on-behalf-of on, the upload runs as the user.

## Ingestion job

`resources/rag_ingestion_job.job.yml` declares a serverless job with a file-arrival trigger on the upload folder
(paused by development mode unless overridden, which the `dev` target does). `notebooks/jobs/rag_ingestion_job.py`
parses new files with `ai_parse_document`, chunks them, writes `rag_raw_documents` and `rag_document_chunks`,
reconciles rows of deleted files, then creates the Delta Sync index on the first run or syncs it afterwards. The
index cannot be declared as a bundle resource because its source table must exist first; the job owns it and
tolerates "not ready to sync" while a new index provisions. Optionally the job registers the index with a
Knowledge Assistant (`knowledge_assistant_name`).

## Retrieval

`core/databricks/vector_search.py` queries the index through the SDK (hybrid search when a query text is given)
with `filters={"user_id": <caller>}`. AI Search has no row-level security; that filter is the isolation, and the
document status route (`GET /api/documents/{id}/status`) uses the same filter to detect when a document became
searchable. Deleting a document removes the file, starts the job (which drops the rows) and deletes the record.

## Grants

The app's service principal reads the index through `USE_SCHEMA` and `SELECT` on the bundle schema, granted by
the `postdeploy` hook because the index exists only after the first run. The job runs as the deployer, who owns
the schema.
