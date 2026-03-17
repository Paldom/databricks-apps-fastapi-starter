from pydantic import BaseModel, Field


class Message(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096)
