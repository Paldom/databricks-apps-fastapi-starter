from pydantic import BaseModel, Field


class VectorStoreRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class VectorQueryRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
