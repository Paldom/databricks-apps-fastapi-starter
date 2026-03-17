from pydantic import BaseModel


class UploadResponse(BaseModel):
    uploaded: str
    bytes: int
