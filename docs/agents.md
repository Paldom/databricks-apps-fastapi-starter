# Agents: supervisor, specialists, stream protocol

## One contract

Every specialist implements `AgentAdapter` (`backend/app/agents/contracts.py`) on the MLflow `ResponsesAgent`
request and response types, so the same adapter serves the chat tool, `POST /api/agents/{backend}/invocations`
and the evaluation job. The Model Serving agent in `notebooks/serving/agent.py` implements the same contract on
the endpoint side.

| Backend            | Adapter                              | Talks to                                            |
| ------------------ | ------------------------------------ | --------------------------------------------------- |
| `supervisor`       | `chat/orchestrator.py`               | the LangGraph supervisor with every configured tool |
| `app`              | `agents/adapters/app_adapter.py`     | another Databricks App through the Apps ingress     |
| `serving_endpoint` | `agents/adapters/serving_adapter.py` | a Model Serving endpoint (Responses API)            |
| `genie`            | `agents/adapters/genie_adapter.py`   | a Genie space through `core/databricks/genie.py`    |

## The supervisor

`chat/agent.py` builds a `create_react_agent` graph over the supervisor model (a Foundation Model endpoint bound
with `CAN_QUERY`) and the tools from `chat/tools.py`: `app_agent`, `serving_endpoint`, `genie`,
`knowledge_assistant` (Knowledge Assistant endpoint when bound, otherwise the AI Search index filtered by the
caller). There is no checkpointer: the controller loads the stored transcript (up to 200 messages), appends the
new user message and runs one turn. Identity travels in the run config (`ChatContext.configurable()`), never in
tool arguments.

Limits live in `Settings`: a per-tool deadline (45 s, inside a span), a turn deadline (90 s, the Apps ingress
cuts requests at about two minutes), three concurrent turns per instance and one turn per chat. A tool failure
reaches the model and the client as a fixed public text; the cause stays in the log with the trace id.

## Stream protocol

`POST /api/chat/stream` takes an owned chat id and the new user message and answers NDJSON, one event per line:

| Event             | Payload                                                             |
| ----------------- | ------------------------------------------------------------------- |
| `text-delta`      | `delta`                                                             |
| `tool-call-begin` | `tool_call_id`, `tool_name`                                         |
| `tool-call-delta` | `tool_call_id`, `args_delta`                                        |
| `tool-result`     | `tool_call_id`, `result`, `is_error`                                |
| `heartbeat`       | every 15 s while a tool runs                                        |
| `done`            | `thread_id`, `trace_id`                                             |
| `error`           | `code` (`busy`, `timeout`, `internal_error`), `message`, `trace_id` |

The assistant message (text plus ordered content parts) is stored before `done` is sent, so a client that stops
at `done` finds the answer on reload. The schema is exported to `backend/openapi.yaml`; the frontend runtime in
`frontend/src/lib/assistant/` consumes it.
