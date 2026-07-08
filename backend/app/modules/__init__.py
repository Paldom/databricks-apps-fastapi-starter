"""Optional-capability modules (see DESIGN.md).

To remove a module: delete its folder, its ``resources/modules/<name>.yml``
(if any), and its line in ``ALL_MODULES`` below. To add one: copy
``app/modules/_template``.
"""

from __future__ import annotations

from app.core.config import Settings
from app.modules.examples.module import spec as examples
from app.modules.knowledge_diy.module import spec as knowledge_diy
from app.modules.registry import ModuleSpec
from app.modules.supervisor_agent.module import spec as supervisor_agent

ALL_MODULES: tuple[ModuleSpec, ...] = (
    examples,
    knowledge_diy,
    supervisor_agent,
)


def active_modules(settings: Settings) -> list[ModuleSpec]:
    """Modules whose configuration is present."""
    return [module for module in ALL_MODULES if module.is_active(settings)]
