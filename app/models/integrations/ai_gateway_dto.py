from pydantic import BaseModel, Field


class EmbedRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
