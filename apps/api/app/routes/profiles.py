from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import db
from ..models import record_to_profile
from ..schemas import LeaderboardEntry, LeaderboardResponse, ProfileResponse

router = APIRouter(tags=["profiles"])


@router.get("/profiles/{username}", response_model=ProfileResponse)
async def get_profile(username: str) -> ProfileResponse:
    row = await db.fetchrow("SELECT * FROM profiles WHERE username = $1", username)
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")

    star_count_row = await db.fetchrow(
        "SELECT COUNT(*)::int AS c FROM stars WHERE user_id = $1::uuid",
        str(row["id"]),
    )
    starred_count = int(star_count_row["c"]) if star_count_row else 0

    return ProfileResponse(
        profile=record_to_profile(row),
        starred_artifacts_count=starred_count,
    )


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def leaderboard(limit: int = 20) -> LeaderboardResponse:
    rows = await db.fetch(
        """
        SELECT username, display_name, credibility_score
        FROM profiles
        ORDER BY credibility_score DESC
        LIMIT $1
        """,
        limit,
    )
    profiles = [
        LeaderboardEntry(
            username=r["username"],
            display_name=r["display_name"],
            credibility_score=float(r["credibility_score"] or 0),
        )
        for r in rows
    ]
    return LeaderboardResponse(profiles=profiles)
