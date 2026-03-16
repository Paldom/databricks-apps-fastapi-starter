from pydantic import BaseModel


class CurrentUser(BaseModel):
    id: str
    email: str | None = None
    name: str | None = None
    preferred_username: str | None = None
