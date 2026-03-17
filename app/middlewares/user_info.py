from fastapi import Request

from app.models.user_dto import CurrentUser
from app.repositories.user_repository import get_or_create_user


async def user_info_middleware(request: Request, call_next):
    """Extract Databricks forwarded identity headers, upsert local user, set request state."""
    user_id = request.headers.get("X-Forwarded-User")
    email = request.headers.get("X-Forwarded-Email")
    preferred_username = request.headers.get("X-Forwarded-Preferred-Username")

    if user_id:
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            db_user = await get_or_create_user(
                session,
                user_id=user_id,
                email=email,
                preferred_username=preferred_username,
            )
            request.state.user = CurrentUser(
                id=db_user.id,
                email=db_user.email,
                name=db_user.name,
                preferred_username=db_user.preferred_username,
            )
            request.state.user_id = db_user.id
    else:
        request.state.user = None
        request.state.user_id = None

    response = await call_next(request)
    return response
