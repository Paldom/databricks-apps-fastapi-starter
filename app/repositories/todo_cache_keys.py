"""Cache key construction for Todo entities.

Key schema
----------
- Detail:       ``todo:detail:{user_id}:{todo_id}``
- List version: ``todo:list_version:{user_id}``
- List data:    ``todo:list:{user_id}:v{version}``

All keys are **user-scoped** so that one user's cache never leaks into
another's.
"""


def detail_key(user_id: str, todo_id: str) -> str:
    return f"todo:detail:{user_id}:{todo_id}"


def list_version_key(user_id: str) -> str:
    return f"todo:list_version:{user_id}"


def list_data_key(user_id: str, version: int) -> str:
    return f"todo:list:{user_id}:v{version}"
