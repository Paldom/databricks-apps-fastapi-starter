# Databricks notebook source
# Bootstrap RAG Resources
#
# One-time idempotent setup: chunk table, Vector Search endpoint/index,
# and Knowledge Assistant knowledge source. Run once after bundle deploy
# so the first real user upload does not pay provisioning cost.

# COMMAND ----------

from __future__ import annotations

# COMMAND ----------

dbutils.widgets.text("chunk_table_name", "")
dbutils.widgets.text("vector_search_endpoint_name", "")
dbutils.widgets.text("vector_search_index_name", "")
dbutils.widgets.text("embedding_model_name", "databricks-gte-large-en")
dbutils.widgets.text("knowledge_assistant_name", "")

CHUNK_TABLE = dbutils.widgets.get("chunk_table_name")
VS_ENDPOINT = dbutils.widgets.get("vector_search_endpoint_name")
VS_INDEX = dbutils.widgets.get("vector_search_index_name")
EMBEDDING_MODEL = dbutils.widgets.get("embedding_model_name") or "databricks-gte-large-en"
KA_NAME = dbutils.widgets.get("knowledge_assistant_name").strip()

print(f"Chunk table: {CHUNK_TABLE}")
print(f"VS endpoint: {VS_ENDPOINT}")
print(f"VS index:    {VS_INDEX}")
print(f"Embedding:   {EMBEDDING_MODEL}")
print(f"KA name:     {KA_NAME or '(not configured)'}")

# COMMAND ----------

# ── 1. Create chunk table with CDF ──────────────────────────────────

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CHUNK_TABLE} (
  chunk_id STRING,
  document_id STRING,
  user_id STRING,
  doc_uri STRING,
  file_name STRING,
  file_extension STRING,
  chunk_index INT,
  chunk_text STRING,
  page_count INT,
  document_title STRING,
  source_path STRING,
  ingested_at TIMESTAMP,
  parser_metadata STRING,
  document_summary STRING,
  extracted_entities STRING
)
TBLPROPERTIES (delta.enableChangeDataFeed = true)
""")
print(f"Chunk table ready: {CHUNK_TABLE}")

# COMMAND ----------

# ── 2. Create Vector Search endpoint if missing ─────────────────────

from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient(disable_notice=True)

try:
    vsc.get_endpoint(name=VS_ENDPOINT)
    print(f"VS endpoint already exists: {VS_ENDPOINT}")
except Exception:
    print(f"Creating VS endpoint: {VS_ENDPOINT}")
    try:
        vsc.create_endpoint(name=VS_ENDPOINT, endpoint_type="STANDARD")
        print(f"VS endpoint created: {VS_ENDPOINT}")
    except Exception as e:
        # May race with another process; check it exists now
        print(f"Endpoint creation note: {e}")

# COMMAND ----------

# ── 3. Create Delta Sync index if missing ────────────────────────────

SYNC_COLUMNS = [
    "document_id", "user_id", "doc_uri", "file_name", "file_extension",
    "chunk_index", "chunk_text", "page_count", "document_title",
    "source_path", "ingested_at", "parser_metadata",
    "document_summary", "extracted_entities",
]

try:
    vsc.get_index(index_name=VS_INDEX)
    print(f"VS index already exists: {VS_INDEX}")
except Exception:
    print(f"Creating Delta Sync index: {VS_INDEX}")
    vsc.create_delta_sync_index(
        endpoint_name=VS_ENDPOINT,
        source_table_name=CHUNK_TABLE,
        index_name=VS_INDEX,
        pipeline_type="TRIGGERED",
        primary_key="chunk_id",
        embedding_source_column="chunk_text",
        embedding_model_endpoint_name=EMBEDDING_MODEL,
        columns_to_sync=SYNC_COLUMNS,
    )
    print(f"VS index created: {VS_INDEX}")

# COMMAND ----------

# ── 4. Register KA knowledge source if configured ───────────────────

if KA_NAME:
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient()
    try:
        existing = list(
            w.knowledge_assistants.list_knowledge_sources(parent=KA_NAME)
        )
        already_present = any(
            getattr(getattr(src, "index", None), "index_name", None) == VS_INDEX
            for src in existing
        )
        if already_present:
            print(f"KA source already registered for index: {VS_INDEX}")
        else:
            from databricks.sdk.service.knowledgeassistants import (
                IndexSpec,
                KnowledgeSource,
            )

            created = w.knowledge_assistants.create_knowledge_source(
                parent=KA_NAME,
                knowledge_source=KnowledgeSource(
                    display_name="Uploaded knowledge files",
                    description="RAG starter uploaded-document index",
                    source_type="index",
                    index=IndexSpec(
                        index_name=VS_INDEX,
                        text_col="chunk_text",
                        doc_uri_col="doc_uri",
                    ),
                ),
            )
            print(f"KA source created: {getattr(created, 'name', created)}")
    except ImportError:
        print(
            "WARNING: Knowledge Assistants SDK not available. "
            "Register the index source manually."
        )
    except Exception as exc:
        print(f"WARNING: KA source registration failed: {exc}")
        print("Register manually if needed.")
else:
    print("No Knowledge Assistant configured; skipping source registration.")

# COMMAND ----------

print("Bootstrap complete.")
