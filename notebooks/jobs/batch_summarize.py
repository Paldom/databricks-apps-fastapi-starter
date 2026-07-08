# Databricks notebook source
# Batch document summarization — the job-level agentic pattern.
#
# The app level runs an interactive agent; the serving level hosts one; this
# task is the third leg: agentic batch inference INSIDE a job, using the
# `ai_query()` SQL function over Delta — no endpoint management, governed by
# Unity Catalog, scales with serverless compute. It runs after ingestion and
# writes a one-paragraph summary per document into a summaries table the app
# can read.

# COMMAND ----------

# MAGIC %pip install -q databricks-sdk
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("chunk_table_name", "")  # noqa: F821
dbutils.widgets.text("summary_table_name", "")  # noqa: F821
dbutils.widgets.text("summarize_model", "databricks-meta-llama-3-3-70b-instruct")  # noqa: F821

chunk_table = dbutils.widgets.get("chunk_table_name")  # noqa: F821
summary_table = dbutils.widgets.get("summary_table_name")  # noqa: F821
model = dbutils.widgets.get("summarize_model")  # noqa: F821
if not chunk_table or not summary_table:
    raise ValueError("chunk_table_name and summary_table_name are required")

print(f"Summarizing {chunk_table} -> {summary_table} via {model}")

# COMMAND ----------

# Ensure the target table exists so the MERGE below is idempotent from the
# first run onward.
spark.sql(  # noqa: F821
    f"""
    CREATE TABLE IF NOT EXISTS {summary_table} (
        source_path STRING,
        summary STRING,
        model STRING,
        summarized_at TIMESTAMP
    )
    """
)

# COMMAND ----------

# One ai_query() call per document (chunks concatenated, capped to keep the
# prompt bounded). MERGE keeps re-runs idempotent: only new or re-ingested
# documents are (re)summarized.
spark.sql(  # noqa: F821
    f"""
    MERGE INTO {summary_table} AS target
    USING (
        SELECT
            source_path,
            ai_query(
                '{model}',
                CONCAT(
                    'Summarize the following document in one short paragraph:\\n\\n',
                    SUBSTRING(CONCAT_WS('\\n', COLLECT_LIST(text)), 1, 16000)
                )
            ) AS summary,
            '{model}' AS model,
            CURRENT_TIMESTAMP() AS summarized_at
        FROM {chunk_table}
        GROUP BY source_path
    ) AS source
    ON target.source_path = source.source_path
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
    """
)

count = spark.sql(f"SELECT COUNT(*) AS n FROM {summary_table}").collect()[0]["n"]  # noqa: F821
print(f"Summaries in {summary_table}: {count}")
