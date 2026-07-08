# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Register the supervisor prompt (MLflow Prompt Registry)
# MAGIC
# MAGIC Last stop in the lifecycle: manage a prompt as a **versioned, aliased
# MAGIC Unity Catalog asset** instead of a string in code. We register the chat
# MAGIC supervisor preamble from `backend/app/chat/registry.py`
# MAGIC (`_SUPERVISOR_PREAMBLE`), load it back by alias, and walk one
# MAGIC version-bump + promote + rollback cycle.
# MAGIC
# MAGIC **Honest scope**: the app currently builds its supervisor prompt in code
# MAGIC (preamble + routing lines from enabled specialists) and does **not** load
# MAGIC from the registry yet. This notebook showcases the registry workflow; if
# MAGIC you edit the preamble here, mirror it in `registry.py` (or wire the app
# MAGIC to `load_prompt` as a follow-up).
# MAGIC
# MAGIC **Prereqs**: UC prompts need a catalog.schema where you have `USE` +
# MAGIC `CREATE` — parameterize below. Requires MLflow >= 3.6.

# COMMAND ----------

# MAGIC %pip install -U "mlflow[databricks]>=3.6"
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# ── Parameters ──────────────────────────────────────────────────────────────
dbutils.widgets.text("uc_catalog", "main")  # noqa: F821
dbutils.widgets.text("uc_schema", "default")  # noqa: F821
dbutils.widgets.text("prompt_name", "chat_supervisor_prompt")  # noqa: F821
dbutils.widgets.text("prompt_alias", "production")  # noqa: F821

CATALOG = dbutils.widgets.get("uc_catalog").strip()  # noqa: F821
SCHEMA = dbutils.widgets.get("uc_schema").strip()  # noqa: F821
FULL_NAME = f"{CATALOG}.{SCHEMA}.{dbutils.widgets.get('prompt_name').strip()}"  # noqa: F821
ALIAS = dbutils.widgets.get("prompt_alias").strip()  # noqa: F821
PROMPT_URI = f"prompts:/{FULL_NAME}@{ALIAS}"
print(f"Prompt: {FULL_NAME} (alias @{ALIAS})")

# COMMAND ----------

import mlflow

# Order matters: set_tracking_uri("databricks") internally reconfigures the
# registry client, which would override a later set_registry_uri call.
mlflow.set_registry_uri("databricks-uc")
mlflow.set_tracking_uri("databricks")

# COMMAND ----------

# ── The prompt under management ─────────────────────────────────────────────
# Source of truth today: _SUPERVISOR_PREAMBLE in backend/app/chat/registry.py.
SUPERVISOR_PROMPT = """\
You are the chat supervisor for a Databricks application.

Choose the smallest number of tools needed to answer correctly.
If the request is trivial and no tool is needed, answer directly.
When you use tools, synthesize a final answer for the user.
Do not expose internal routing details unless helpful.
"""

# COMMAND ----------

# ── Register ────────────────────────────────────────────────────────────────
# Idempotent in the right way: first run creates version 1; every re-run with
# a changed template creates the next version. Nothing is ever overwritten.
prompt = mlflow.genai.register_prompt(
    name=FULL_NAME,
    template=SUPERVISOR_PROMPT,
    tags={"source": "backend/app/chat/registry.py", "purpose": "supervisor_preamble"},
)
print(f"Registered {prompt.name} -> version {prompt.version}")

# Aliases are mutable pointers to immutable versions — deployments reference
# the alias so promoting/rolling back never touches app code.
mlflow.genai.set_prompt_alias(name=FULL_NAME, alias=ALIAS, version=prompt.version)
print(f"Alias @{ALIAS} -> v{prompt.version}")

# COMMAND ----------

# ── Load it back exactly as a consumer would ────────────────────────────────
loaded = mlflow.genai.load_prompt(PROMPT_URI)
print(f"Loaded {loaded.name} v{loaded.version} via {PROMPT_URI}\n")
print(loaded.template)
assert loaded.template == SUPERVISOR_PROMPT

# COMMAND ----------

# ── Versioning in action: draft v(N+1), promote, roll back ──────────────────
# A tightened preamble becomes a NEW version; @production keeps serving the
# old one until explicitly promoted — prompt changes get the same
# review-then-release flow as code.
DRAFT_PROMPT = SUPERVISOR_PROMPT + (
    "\nPrefer a single specialist per question; explain briefly when no "
    "specialist fits.\n"
)
draft = mlflow.genai.register_prompt(name=FULL_NAME, template=DRAFT_PROMPT)
served = mlflow.genai.load_prompt(PROMPT_URI)
print(f"Draft is v{draft.version}; @{ALIAS} still serves v{served.version}")

# Promote the draft…
mlflow.genai.set_prompt_alias(name=FULL_NAME, alias=ALIAS, version=draft.version)
print(f"Promoted: @{ALIAS} -> v{draft.version}")

# …and roll back instantly (old versions remain addressable forever, e.g.
# f"prompts:/{FULL_NAME}/{prompt.version}" pins an exact version).
mlflow.genai.set_prompt_alias(name=FULL_NAME, alias=ALIAS, version=prompt.version)
print(f"Rolled back: @{ALIAS} -> v{prompt.version}")
# Next iteration loop: tweak template -> re-run 02_evaluate.py -> promote.
