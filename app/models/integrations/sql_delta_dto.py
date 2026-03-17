from pydantic import BaseModel, Field


class DeltaTodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
