from fastapi import Request

from core.auth import UserInfo


async def user_info_middleware(request: Request, call_next):
    """Extract user info from headers and attach to request state."""
    user_info = UserInfo(
        preferred_username=request.headers.get("X-Forwarded-Preferred-Username"),
        user_id=request.headers.get("X-Forwarded-User"),
        email=request.headers.get("X-Forwarded-Email"),
    )
    request.state.user_info = user_info
    response = await call_next(request)
    return response
