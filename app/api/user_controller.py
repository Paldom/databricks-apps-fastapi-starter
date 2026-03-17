from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.models.user_dto import CurrentUser

router = APIRouter(tags=["User"])


@router.get("/userInfo")
async def get_user_info(user: Annotated[CurrentUser, Depends(get_current_user)]):
    return user.model_dump()
