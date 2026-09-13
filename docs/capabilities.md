# Optional capabilities

The golden path (upload, ingestion, chat with the knowledge specialist, traces, evaluation) is always on.
Everything else is a capability that a target switches on and that degrades to "not configured" when it is off.
The earlier module registry is gone: a capability is now one binding, one environment variable and one adapter.

## Anatomy

| Piece               | Where                                                      | Mechanism                                                       |
| ------------------- | ---------------------------------------------------------- | --------------------------------------------------------------- |
| Databricks resource | a target block in `databricks.yml`                         | app `resources` and `config.env` lists merge by `name`          |
| Backend code        | `backend/app/agents/adapters/` or `core/databricks/`       | reads its setting from `Settings`; absent setting, absent tool  |
| Chat specialist     | `backend/app/chat/registry.py`                             | a `SpecialistSpec` registers only when its settings exist       |
| Showcase route      | `backend/app/api/examples_controller.py`                   | mounted only with `ENABLE_EXAMPLES=true`; 503 when unconfigured |
| Frontend            | tool UIs in `frontend/src/components/assistant-thread.tsx` | a tool without a UI renders through the generic fallback        |

## Shipped capabilities

| Capability            | Switch                                                        | Backend                                                        |
| --------------------- | ------------------------------------------------------------- | -------------------------------------------------------------- |
| Genie specialist      | `genie-space` binding, `GENIE_SPACE_ID`                       | `core/databricks/genie.py`, `agents/adapters/genie_adapter.py` |
| Knowledge Assistant   | `knowledge-assistant` binding, `KNOWLEDGE_ASSISTANT_ENDPOINT` | `core/databricks/knowledge_assistant.py`, `chat/tools.py`      |
| Serving agent         | `deploy_serving_agent` job, then `serving-agent` binding      | `agents/adapters/serving_adapter.py`                           |
| Remote app specialist | `app-agent` binding, `APP_AGENT_NAME`                         | `agents/adapters/app_adapter.py`                               |
| Bound secret          | `app-secret` binding, `EXAMPLE_SECRET`                        | `api/examples_controller.py` (`GET /api/examples/secret`)      |
| Chat titles           | `ENABLE_CHAT_TITLE_GENERATION`, `TITLE_MODEL`                 | `chat/titles.py`                                               |
| On-behalf-of          | `ENABLE_OBO`, `forward_user_access_token`, `user_api_scopes`  | `middlewares/workspace_client.py`                              |

Without a Knowledge Assistant the knowledge specialist queries the AI Search index directly, filtered by the
caller's user id; with one, the assistant is a shared corpus by design.

## Adding one

1. A `Settings` field in `backend/app/core/config.py` (regenerate `env.example` with `make generate`).
2. A client in `core/databricks/` for the Databricks call, an adapter in `agents/adapters/` when it is a chat
   specialist, and a tool builder plus `SpecialistSpec` in `chat/`.
3. The binding and env entry as comments in `resources/fastapi_app.app.yml`, switched on in a target.
4. A test at the adapter boundary (fake the SDK object, never the framework), a row here, a README mention.

## Removing one

Delete the adapter, the spec, the setting and the comment lines; `make check` stays green. If a removal breaks
anything else, the capability was not optional.
