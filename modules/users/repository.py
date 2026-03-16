import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from .models import AppUser


async def get_or_create_user(
    session: AsyncSession,
    *,
    user_id: str,
    email: str | None = None,
    preferred_username: str | None = None,
) -> AppUser:
    """Look up a local user by PK; create or update as needed."""
    user = await session.get(AppUser, user_id)
    name = preferred_username or email or user_id

    if user is not None:
        changed = False
        if email is not None and user.email != email:
            user.email = email
            changed = True
        if preferred_username is not None and user.preferred_username != preferred_username:
            user.preferred_username = preferred_username
            changed = True
        if user.name != name:
            user.name = name
            changed = True
        user.last_seen_at = dt.datetime.utcnow()
        if changed:
            user.updated_at = dt.datetime.utcnow()
        await session.commit()
        return user

    user = AppUser(
        id=user_id,
        email=email,
        preferred_username=preferred_username,
        name=name,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
