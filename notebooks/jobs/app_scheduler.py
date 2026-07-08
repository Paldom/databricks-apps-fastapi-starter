# Databricks notebook source
# App start/stop scheduler — the cost guardrail (cost-guardrail module).
#
# Databricks Apps compute has no scale-to-zero; an idle app bills around the
# clock. These two scheduled jobs stop the app outside working hours and
# start it before the day begins. Enable the module by uncommenting its line
# in databricks.yml's include list.

# COMMAND ----------

# MAGIC %pip install -q databricks-sdk
# MAGIC %restart_python

# COMMAND ----------

from databricks.sdk import WorkspaceClient  # noqa: E402

dbutils.widgets.text("app_name", "")  # noqa: F821
dbutils.widgets.dropdown("action", "stop", ["stop", "start"])  # noqa: F821

app_name = dbutils.widgets.get("app_name")  # noqa: F821
action = dbutils.widgets.get("action")  # noqa: F821
if not app_name:
    raise ValueError("app_name is required")

ws = WorkspaceClient()
app = ws.apps.get(app_name)
state = app.compute_status.state.value if app.compute_status else "UNKNOWN"
print(f"{app_name}: compute is {state}; requested action: {action}")

# COMMAND ----------

if action == "stop":
    if state == "ACTIVE":
        ws.apps.stop(app_name)
        print(f"Stop requested for {app_name}")
    else:
        print("Not active — nothing to stop.")
else:
    if state != "ACTIVE":
        ws.apps.start(app_name)
        print(f"Start requested for {app_name}")
    else:
        print("Already active — nothing to start.")
