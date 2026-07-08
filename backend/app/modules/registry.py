"""Module registry — the mechanism behind optional capabilities.

A *module* is a self-contained vertical slice of one optional capability
(see DESIGN.md): a folder under ``app/modules/`` holding its spec, an
optional API router, and an optional chat-specialist contribution, paired
with an optional bundle resource file under ``resources/modules/``.

Modules activate purely from configuration: when their settings fields are
present the router is mounted and the specialist joins the supervisor's
tool set; when absent the app runs without them. Deleting a module is one
folder + one resource file + one line in ``app/modules/__init__.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter

from app.chat.registry import SpecialistSpec
from app.core.config import Settings

# Builders share the specialist tool-builder convention from app/chat/tools.py:
# (spec, settings, *, ai_client, workspace_client, vector_index, logger, **_).
ToolBuilder = Callable[..., Any]


@dataclass(frozen=True)
class ModuleSpec:
    """One optional capability.

    ``name`` is the module slug and must match the folder name under
    ``app/modules/`` and (when present) the resource file
    ``resources/modules/<name>.yml``.
    """

    name: str
    title: str
    description: str
    #: Settings fields that must all be truthy for the module to activate.
    #: Empty tuple = always active.
    config_keys: tuple[str, ...] = ()
    router: APIRouter | None = None
    #: Optional chat-specialist contribution (registered when active).
    specialist: SpecialistSpec | None = None
    tool_builder: ToolBuilder | None = None

    def is_active(self, settings: Settings) -> bool:
        return all(getattr(settings, key, None) for key in self.config_keys)
