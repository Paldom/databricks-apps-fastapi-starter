"""DIY RAG chat tool: AI Gateway embedding + direct Vector Search query.

Deliberately duplicates the managed Knowledge Assistant tool in
``app/chat/tools.py``: this is the DIY path shown alongside the Agent
Bricks path. See the intentional-duality register in DESIGN.md.
"""

from __future__ import annotations

import logging
from typing import Any

from openai import AsyncOpenAI

from app.chat.registry import SpecialistSpec
from app.core.config import Settings
from app.core.observability import get_tracer, safe_attr, tag_exception

_tracer = get_tracer()
_logger = logging.getLogger(__name__)


def build_direct_vs_tool(
    spec: SpecialistSpec,
    settings: Settings,
    *,
    ai_client: AsyncOpenAI,
    vector_index: Any | None = None,
    **_: Any,
) -> Any:
    """Build a knowledge tool backed by direct embed + vector search."""
    from langchain_core.tools import tool

    embedding_model = settings.ai_gateway_embedding_model or ""
    index_name = settings.vector_search_index_name or ""
    volume_root = settings.knowledge_volume_root or settings.volume_root

    @tool
    async def knowledge_search(question: str) -> str:
        """Search the knowledge base for relevant documents."""
        with _tracer.start_as_current_span(
            "tool.knowledge",
            attributes={
                "tool": "knowledge",
                "knowledge.mode": "direct_vs",
                "knowledge.index": safe_attr(index_name),
            },
        ) as span:
            try:
                from app.core.databricks.ai_gateway import AiGatewayAdapter
                from app.core.databricks.vector_search import VectorSearchAdapter

                ai_adapter = AiGatewayAdapter(ai_client, _logger)
                query_vector = await ai_adapter.embed(embedding_model, question)

                vs_adapter = VectorSearchAdapter(vector_index, _logger)
                results = await vs_adapter.similarity_search(
                    query_vector=query_vector,
                    columns=["text"],
                    num_results=5,
                    timeout=float(settings.vector_timeout_seconds),
                )

                formatted = format_knowledge_results(results, volume_root)
                span.set_attribute("result", "ok")
                return formatted if formatted else "No relevant documents found."
            except Exception as exc:
                tag_exception(span, exc)
                return f"Knowledge search error: {exc}"

    knowledge_search.__doc__ = spec.description
    return knowledge_search


def format_knowledge_results(results: Any, volume_root: str) -> str:
    """Normalize vector search results into a citation-rich string."""
    if results is None:
        return ""
    hits: list[dict[str, Any]] = []
    if isinstance(results, dict):
        data = results.get("result", {})
        if isinstance(data, dict):
            rows = data.get("data_array", [])
            columns = data.get("column_names", [])
            for row in rows:
                hit = (
                    dict(zip(columns, row, strict=False))
                    if columns
                    else {"text": str(row)}
                )
                hits.append(hit)
        elif isinstance(data, list):
            for item in data:
                hits.append(item if isinstance(item, dict) else {"text": str(item)})
    if not hits:
        return ""
    parts: list[str] = []
    for i, hit in enumerate(hits, 1):
        text = hit.get("text", "")
        score = hit.get("score", "")
        source = hit.get("source_path") or hit.get("metadata", {}).get("source", "")
        entry = f"[{i}] {text}"
        if source:
            entry += f"\n    Source: {source}"
        if score:
            entry += f" (score: {score})"
        parts.append(entry)
    return "\n\n".join(parts)
