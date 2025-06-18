from pydantic import BaseModel

class UserInfo(BaseModel):
    preferred_username: str | None = None
    user_id: str | None = None
    email: str | None = None
