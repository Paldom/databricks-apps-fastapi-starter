from typing import Any, Dict, Optional

from pydantic import BaseModel


class JobRunRequest(BaseModel):
    params: Optional[Dict[str, Any]] = None
