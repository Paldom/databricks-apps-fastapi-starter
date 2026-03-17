from pydantic import BaseModel, Field


class GenericRow(BaseModel):
    id: str = Field(..., max_length=255)
    data: str = Field(..., max_length=65_536)
