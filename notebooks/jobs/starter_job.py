# ruff: noqa
# mypy: ignore-errors
# Databricks notebook source
dbutils.widgets.text("input", "", label="path")

# COMMAND ----------

input_path = dbutils.widgets.get("input")

# COMMAND ----------

res = {}

# COMMAND ----------

dbutils.notebook.exit(res)
