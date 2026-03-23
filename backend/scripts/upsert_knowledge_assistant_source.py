"""One-time bootstrap: register the RAG vector index as a Knowledge Assistant source.

Usage:
    KNOWLEDGE_ASSISTANT_NAME=my-assistant \
    VECTOR_SEARCH_INDEX_NAME=main.starter_rag.rag_document_chunks_index \
    python backend/scripts/upsert_knowledge_assistant_source.py

Idempotent — safe to run multiple times.
"""

from __future__ import annotations

import os
import sys

assistant_name = os.environ.get("KNOWLEDGE_ASSISTANT_NAME", "").strip()
index_name = os.environ.get("VECTOR_SEARCH_INDEX_NAME", "").strip()

if not assistant_name:
    print("KNOWLEDGE_ASSISTANT_NAME not set; skipping bootstrap")
    sys.exit(0)

if not index_name:
    print("VECTOR_SEARCH_INDEX_NAME not set; skipping bootstrap")
    sys.exit(0)

from databricks.sdk import WorkspaceClient  # noqa: E402

w = WorkspaceClient()

# Check if this index source is already registered
try:
    existing_sources = list(
        w.knowledge_assistants.list_knowledge_sources(parent=assistant_name)
    )
    for source in existing_sources:
        idx = getattr(source, "index", None)
        if idx and getattr(idx, "index_name", None) == index_name:
            print(f"Knowledge source already present for index: {index_name}")
            sys.exit(0)
except Exception as exc:
    print(f"WARNING: Could not list existing sources: {exc}")
    print("Attempting to create the source anyway...")

# Register the vector index as a knowledge source
try:
    from databricks.sdk.service.knowledgeassistants import IndexSpec, KnowledgeSource

    source = KnowledgeSource(
        display_name="Uploaded knowledge files",
        description="Documents uploaded via the FastAPI app and indexed by the RAG ingestion job.",
        source_type="index",
        index=IndexSpec(
            index_name=index_name,
            text_col="chunk_text",
            doc_uri_col="doc_uri",
        ),
    )

    created = w.knowledge_assistants.create_knowledge_source(
        parent=assistant_name,
        knowledge_source=source,
    )
    print(f"Created knowledge source: {getattr(created, 'name', created)}")

except ImportError:
    print(
        "WARNING: Knowledge Assistants SDK not available in this databricks-sdk version. "
        "Register the index source manually in the Knowledge Assistant UI:\n"
        f"  Index: {index_name}\n"
        f"  Text column: chunk_text\n"
        f"  Doc URI column: doc_uri\n"
    )
except Exception as exc:
    print(f"WARNING: Could not create knowledge source: {exc}")
    print(
        "Register the index source manually in the Knowledge Assistant UI:\n"
        f"  Index: {index_name}\n"
        f"  Text column: chunk_text\n"
        f"  Doc URI column: doc_uri\n"
    )
