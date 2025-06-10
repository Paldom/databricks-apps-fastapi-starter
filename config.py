import os
from typing import Optional
from workspace import w

def get_secret(key: str, *, scope: Optional[str] = None,
               allow_env: bool = True) -> Optional[str]:
    if allow_env and (val := os.getenv(key)) is not None:
        return val
    if scope:
        try:
            return w().secrets.get_secret(scope=scope, key=key).value
        except Exception:
            return None
    return None