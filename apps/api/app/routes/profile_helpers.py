from __future__ import annotations

from .. import db


async def get_or_create_profile(username: str) -> dict:
    row = await db.fetchrow("SELECT * FROM profiles WHERE username = $1", username)
    if row:
        return dict(row)
    row = await db.fetchrow(
        """
        INSERT INTO profiles (username, display_name)
        VALUES ($1, $2)
        RETURNING *
        """,
        username,
        username,
    )
    return dict(row)
