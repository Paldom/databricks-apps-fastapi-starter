# Databricks notebook source
# RAG Document Ingestion Job
#
# Triggered by file arrival on the knowledge upload volume path.
# 1. Auto Loader streams new files into a raw Delta table (exactly-once).
# 2. Batch processes unprocessed raw docs: parse, extract metadata, chunk.
# 3. MERGEs chunks into the chunk Delta table (CDF enabled).
# 4. Creates/syncs a Delta Sync Vector Search index idempotently.

# COMMAND ----------

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from pyspark.sql import functions as F, types as T
from delta.tables import DeltaTable

# COMMAND ----------

dbutils.widgets.text("source_path", "")
dbutils.widgets.text("checkpoint_path", "")
dbutils.widgets.text("raw_table_name", "")
dbutils.widgets.text("chunk_table_name", "")
dbutils.widgets.text("vector_search_endpoint_name", "")
dbutils.widgets.text("vector_search_index_name", "")
dbutils.widgets.text("embedding_model_name", "databricks-gte-large-en")

SOURCE_PATH = dbutils.widgets.get("source_path").rstrip("/")
CHECKPOINT_PATH = dbutils.widgets.get("checkpoint_path").rstrip("/")
RAW_TABLE = dbutils.widgets.get("raw_table_name")
CHUNK_TABLE = dbutils.widgets.get("chunk_table_name")
VS_ENDPOINT = dbutils.widgets.get("vector_search_endpoint_name")
VS_INDEX = dbutils.widgets.get("vector_search_index_name")
EMBEDDING_MODEL = dbutils.widgets.get("embedding_model_name") or "databricks-gte-large-en"

print(f"Source: {SOURCE_PATH}")
print(f"Checkpoint: {CHECKPOINT_PATH}")
print(f"Raw table: {RAW_TABLE}")
print(f"Chunk table: {CHUNK_TABLE}")
print(f"VS endpoint: {VS_ENDPOINT}")
print(f"VS index: {VS_INDEX}")

# COMMAND ----------

# ── 1. Create tables ──────────────────────────────────────────────

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {RAW_TABLE} (
  document_id STRING,
  user_id STRING,
  path STRING,
  file_name STRING,
  file_extension STRING,
  content BINARY,
  file_size BIGINT,
  modification_time TIMESTAMP,
  ingested_at TIMESTAMP
)
""")

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

# COMMAND ----------

# ── 2. Ingest new files into raw table via Auto Loader ────────────
#
# Path convention: .../knowledge/uploads/<base64url_user_id>/<uuid>__<filename>

@F.udf("string")
def decode_user_id(encoded: str) -> str:
    """Decode base64url-encoded user_id (without padding)."""
    if not encoded:
        return ""
    padding = "=" * (-len(encoded) % 4)
    try:
        return base64.urlsafe_b64decode((encoded + padding).encode("utf-8")).decode("utf-8")
    except Exception:
        return encoded  # fallback: use raw value

incoming = (
    spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "binaryFile")
    .option("cloudFiles.schemaLocation", f"{CHECKPOINT_PATH}/schema")
    .load(SOURCE_PATH)
    .withColumn("_encoded_uid", F.regexp_extract("path", r"/knowledge/uploads/([^/]+)/", 1))
    .withColumn("user_id", decode_user_id("_encoded_uid"))
    .withColumn("document_id", F.regexp_extract("path", r"/([0-9a-fA-F-]{36})__", 1))
    .withColumn("file_name", F.regexp_extract("path", r"__([^/]+)$", 1))
    .withColumn("file_extension", F.lower(F.regexp_extract("path", r"\.([^.]+)$", 1)))
    .withColumn("file_size", F.col("length"))
    .withColumn("modification_time", F.col("modificationTime"))
    .withColumn("ingested_at", F.current_timestamp())
    .select(
        "document_id", "user_id", "path", "file_name", "file_extension",
        "content", "file_size", "modification_time", "ingested_at",
    )
)

(
    incoming.writeStream
    .option("checkpointLocation", f"{CHECKPOINT_PATH}/raw")
    .trigger(availableNow=True)
    .toTable(RAW_TABLE)
).awaitTermination()

raw_count = spark.table(RAW_TABLE).count()
print(f"Raw table total rows: {raw_count}")

# COMMAND ----------

# ── 3. Find raw documents not yet chunked ─────────────────────────

raw_df = spark.table(RAW_TABLE)
existing_doc_ids = spark.table(CHUNK_TABLE).select("document_id").distinct()

to_process = raw_df.join(existing_doc_ids, on="document_id", how="left_anti")
n_to_process = to_process.count()
print(f"New documents to process: {n_to_process}")

if n_to_process == 0:
    dbutils.notebook.exit(json.dumps({
        "status": "ok",
        "raw_rows": raw_count,
        "new_docs_processed": 0,
        "chunks_written": 0,
    }))

# COMMAND ----------

# ── 4. Parse with ai_parse_document and extract metadata ──────────

parsed_df = (
    to_process
    .withColumn("parsed", F.expr("ai_parse_document(content, map('version', '2.0'))"))
    .withColumn(
        "page_count",
        F.coalesce(
            F.size(F.expr("try_cast(parsed:document:pages AS ARRAY<VARIANT>)")),
            F.lit(0),
        ),
    )
    .withColumn(
        "document_text",
        F.coalesce(
            F.expr("""
                concat_ws('\n\n',
                    transform(
                        try_cast(parsed:document:elements AS ARRAY<VARIANT>),
                        x -> coalesce(try_cast(x:content AS STRING), '')
                    )
                )
            """),
            F.lit(""),
        ),
    )
    .withColumn(
        "document_title",
        F.coalesce(
            F.expr("""
                element_at(
                    transform(
                        filter(
                            try_cast(parsed:document:elements AS ARRAY<VARIANT>),
                            x -> try_cast(x:type AS STRING) = 'title'
                        ),
                        x -> try_cast(x:content AS STRING)
                    ),
                    1
                )
            """),
            F.col("file_name"),
        ),
    )
    .withColumn("parser_metadata", F.to_json(F.expr("parsed:metadata")))
    .withColumn("doc_uri", F.col("path"))
    .withColumn("document_summary", F.expr("ai_summarize(document_text)"))
    .withColumn(
        "extracted_entities",
        F.to_json(F.expr("ai_extract(document_text, array('people', 'organizations', 'products', 'dates'))")),
    )
    .filter(F.length(F.trim(F.col("document_text"))) > 0)
)

# COMMAND ----------

# ── 5. Chunk parsed documents ─────────────────────────────────────

def split_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> list[tuple[int, str]]:
    """Split text into overlapping chunks. Returns (index, text) pairs."""
    text = (text or "").strip()
    if not text:
        return []
    parts: list[tuple[int, str]] = []
    start = 0
    idx = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            parts.append((idx, chunk))
            idx += 1
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return parts

rows = parsed_df.select(
    "document_id", "user_id", "doc_uri", "file_name", "file_extension",
    "page_count", "document_title", "path", "ingested_at", "parser_metadata",
    "document_summary", "extracted_entities", "document_text",
).collect()

chunk_rows: list[dict[str, Any]] = []
for row in rows:
    for chunk_index, chunk_text in split_text(row["document_text"]):
        raw_id = f"{row['document_id']}::{chunk_index}"
        chunk_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()
        chunk_rows.append({
            "chunk_id": chunk_id,
            "document_id": row["document_id"],
            "user_id": row["user_id"],
            "doc_uri": row["doc_uri"],
            "file_name": row["file_name"],
            "file_extension": row["file_extension"],
            "chunk_index": chunk_index,
            "chunk_text": chunk_text,
            "page_count": row["page_count"],
            "document_title": row["document_title"],
            "source_path": row["path"],
            "ingested_at": row["ingested_at"],
            "parser_metadata": row["parser_metadata"],
            "document_summary": row["document_summary"],
            "extracted_entities": row["extracted_entities"],
        })

print(f"Chunks to write: {len(chunk_rows)}")

# COMMAND ----------

# ── 6. MERGE chunks into chunk table ──────────────────────────────

if chunk_rows:
    chunk_schema = T.StructType([
        T.StructField("chunk_id", T.StringType(), False),
        T.StructField("document_id", T.StringType(), False),
        T.StructField("user_id", T.StringType(), False),
        T.StructField("doc_uri", T.StringType(), False),
        T.StructField("file_name", T.StringType(), False),
        T.StructField("file_extension", T.StringType(), False),
        T.StructField("chunk_index", T.IntegerType(), False),
        T.StructField("chunk_text", T.StringType(), False),
        T.StructField("page_count", T.IntegerType(), True),
        T.StructField("document_title", T.StringType(), True),
        T.StructField("source_path", T.StringType(), False),
        T.StructField("ingested_at", T.TimestampType(), False),
        T.StructField("parser_metadata", T.StringType(), True),
        T.StructField("document_summary", T.StringType(), True),
        T.StructField("extracted_entities", T.StringType(), True),
    ])

    chunk_df = spark.createDataFrame(chunk_rows, schema=chunk_schema)

    target = DeltaTable.forName(spark, CHUNK_TABLE)
    (
        target.alias("t")
        .merge(chunk_df.alias("s"), "t.chunk_id = s.chunk_id")
        .whenNotMatchedInsertAll()
        .execute()
    )

print(f"Chunks written: {len(chunk_rows)}")

# COMMAND ----------

# ── 7. Sync Vector Search index (fallback: create if missing) ────────
#
# The bootstrap job (bootstrap_rag_resources.py) is the primary
# provisioning path for the VS endpoint and index. This block is a
# fallback safety net — it creates resources only if they are
# unexpectedly absent (e.g. bootstrap was skipped or failed).

from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient(disable_notice=True)

try:
    vsc.get_index(index_name=VS_INDEX)
    print(f"Index exists: {VS_INDEX}")
except Exception:
    print(f"WARNING: Index {VS_INDEX} not found — running fallback provisioning.")
    print("This should have been created by the bootstrap job.")
    try:
        vsc.create_endpoint(name=VS_ENDPOINT, endpoint_type="STANDARD")
    except Exception as e:
        print(f"Endpoint creation skipped (may already exist): {e}")

    vsc.create_delta_sync_index(
        endpoint_name=VS_ENDPOINT,
        source_table_name=CHUNK_TABLE,
        index_name=VS_INDEX,
        pipeline_type="TRIGGERED",
        primary_key="chunk_id",
        embedding_source_column="chunk_text",
        embedding_model_endpoint_name=EMBEDDING_MODEL,
        columns_to_sync=[
            "document_id", "user_id", "doc_uri", "file_name", "file_extension",
            "chunk_index", "chunk_text", "page_count", "document_title",
            "source_path", "ingested_at", "parser_metadata",
            "document_summary", "extracted_entities",
        ],
    )

# Trigger sync on the (now-existing) index
index = vsc.get_index(index_name=VS_INDEX)
index.sync()
print("Vector Search index sync triggered")

# COMMAND ----------

# ── 8. Summary ────────────────────────────────────────────────────

summary = {
    "status": "ok",
    "raw_rows": raw_count,
    "new_docs_processed": n_to_process,
    "chunks_written": len(chunk_rows),
    "vector_index": VS_INDEX,
}
print(json.dumps(summary, indent=2))
dbutils.notebook.exit(json.dumps(summary))
