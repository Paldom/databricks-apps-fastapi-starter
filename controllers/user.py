from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/userInfo")
async def get_user_info(request: Request):
    user_info = getattr(request.state, "user_info", None)
    if user_info is None:
        return {}
    return user_info.model_dump()
