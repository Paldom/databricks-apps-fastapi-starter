"""Module spec: DIY RAG via AI Gateway embeddings + Vector Search."""

from app.chat.registry import SpecialistSpec
from app.modules.knowledge_diy.tool import build_direct_vs_tool
from app.modules.registry import ModuleSpec

spec = ModuleSpec(
    name="knowledge-diy",
    title="DIY RAG (embed + Vector Search)",
    description=(
        "Answers knowledge questions by embedding the query via AI Gateway "
        "and searching a Vector Search index directly — the DIY counterpart "
        "of the managed Knowledge Assistant path (see DESIGN.md)."
    ),
    config_keys=(
        "ai_gateway_embedding_model",
        "vector_search_endpoint_name",
        "vector_search_index_name",
    ),
    specialist=SpecialistSpec(
        key="knowledge_diy",
        description=(
            "Search indexed documents, manuals, policies, or volume-backed "
            "knowledge via direct Vector Search."
        ),
        kind="knowledge_diy",
    ),
    tool_builder=build_direct_vs_tool,
)
