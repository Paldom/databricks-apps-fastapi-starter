import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_model import AppUser


async def get_or_create_user(
    session: AsyncSession,
    *,
    user_id: str,
    email: str | None = None,
    preferred_username: str | None = None,
) -> AppUser:
    """Upsert an AppUser: create if new, update fields if changed.

    The function flushes but does **not** commit — the caller owns the
    transaction lifecycle.
    """
    user = await session.get(AppUser, user_id)
    display_name = preferred_username or email or user_id

    if user is None:
        user = AppUser(
            id=user_id,
            email=email,
            preferred_username=preferred_username,
            display_name=display_name,
        )
        session.add(user)
    else:
        if email is not None:
            user.email = email
        if preferred_username is not None:
            user.preferred_username = preferred_username
        user.display_name = display_name
    user.last_seen_at = dt.datetime.now(dt.UTC)
    await session.flush()
    await session.refresh(user)
    return user
