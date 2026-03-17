from pydantic import BaseModel


class GenieQuestion(BaseModel):
    content: str
