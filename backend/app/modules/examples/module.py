"""Module spec: Databricks API examples playground.

Small endpoints that each demonstrate one platform call (Model Serving
query, job trigger, Genie REST conversation, Volume upload) — including
the raw-REST Genie client that deliberately mirrors the SDK adapter
(duality register, DESIGN.md).
"""

from app.modules.examples.controller import router
from app.modules.registry import ModuleSpec

spec = ModuleSpec(
    name="examples",
    title="Databricks API examples",
    description=(
        "A playground of one-call-per-endpoint examples: Model Serving "
        "query, Jobs trigger, Genie via raw REST, and UC Volume upload."
    ),
    config_keys=("enable_databricks_integrations",),
    router=router,
)
