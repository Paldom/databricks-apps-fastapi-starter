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
    """Upsert an AppUser: create if new, update fields if changed."""
    user = await session.get(AppUser, user_id)
    # Derive display name from best available identifier
    name = preferred_username or email or user_id

    if user is None:
        user = AppUser(
            id=user_id,
            email=email,
            preferred_username=preferred_username,
            name=name,
        )
        session.add(user)
    else:
        if email is not None:
            user.email = email
        if preferred_username is not None:
            user.preferred_username = preferred_username
        user.name = name
    user.last_seen_at = dt.datetime.utcnow()
    await session.commit()
    await session.refresh(user)
    return user
