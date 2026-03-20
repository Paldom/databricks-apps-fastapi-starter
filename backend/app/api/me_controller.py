from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.models.user_dto import CurrentUser

router = APIRouter(tags=["me"])


@router.get(
    "/me",
    operation_id="getMe",
    response_model=CurrentUser,
)
async def get_me(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    return user
