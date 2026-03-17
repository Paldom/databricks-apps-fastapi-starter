from pydantic import BaseModel, Field


class GenieQuestion(BaseModel):
    content: str = Field(..., min_length=1, max_length=8192)
