from fastapi import Request

from app.core.runtime import get_app_runtime
from app.models.user_dto import CurrentUser
from app.repositories.user_repository import get_or_create_user


async def user_info_middleware(request: Request, call_next):
    """Extract Databricks forwarded identity headers, upsert local user, set request state.

    Uses its own session so the user upsert commits independently
    of the request handler's transaction.
    """
    user_id = request.headers.get("X-Forwarded-User")
    email = request.headers.get("X-Forwarded-Email")
    preferred_username = request.headers.get("X-Forwarded-Preferred-Username")

    if user_id:
        request.state.user = CurrentUser(
            id=user_id,
            email=email,
            name=preferred_username or email or user_id,
            preferred_username=preferred_username,
        )
        request.state.user_id = user_id

        runtime = get_app_runtime(request.app)
        session_factory = runtime.session_factory
        if session_factory is not None:
            try:
                async with session_factory() as session:
                    async with session.begin():
                        db_user = await get_or_create_user(
                            session,
                            user_id=user_id,
                            email=email,
                            preferred_username=preferred_username,
                        )
                        request.state.user = CurrentUser(
                            id=db_user.id,
                            email=db_user.email,
                            name=db_user.display_name,
                            preferred_username=db_user.preferred_username,
                        )
                        request.state.user_id = db_user.id
            except Exception:
                pass
    else:
        request.state.user = None
        request.state.user_id = None

    response = await call_next(request)
    return response
