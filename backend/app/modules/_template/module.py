"""Module spec template — copy, rename, and fill in (see README.md here).

This file is not imported anywhere; it becomes live only when you add the
spec to ``ALL_MODULES`` in ``app/modules/__init__.py``.
"""

from app.modules.registry import ModuleSpec

spec = ModuleSpec(
    name="my-module",  # must match the folder and resources/modules/<name>.yml
    title="My capability",
    description="One sentence on what this showcases (capability-matrix row).",
    config_keys=("my_setting_field",),  # Settings fields gating activation
    # router=my_router,                 # optional: from .controller import router
    # specialist=SpecialistSpec(...),   # optional chat tool contribution
    # tool_builder=build_my_tool,       # required when specialist is set
)
