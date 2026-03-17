from pydantic import BaseModel


class GenericRow(BaseModel):
    id: str
    data: str
