from fastapi import APIRouter, Depends

from core.deps import get_current_user
from modules.users.schemas import CurrentUser

router = APIRouter()


@router.get("/userInfo")
async def get_user_info(user: CurrentUser = Depends(get_current_user)):
    return user.model_dump()
