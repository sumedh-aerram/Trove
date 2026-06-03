from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import db
from ..schemas import StarRequest
from .profile_helpers import get_or_create_profile

router = APIRouter(prefix="/artifacts", tags=["stars"])


@router.post("/{artifact_id}/star")
async def star_artifact(artifact_id: str, body: StarRequest) -> dict:
    artifact = await db.fetchrow("SELECT id FROM artifacts WHERE id = $1::uuid", artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    profile = await get_or_create_profile(body.username.strip())
    await db.execute(
        """
        INSERT INTO stars (user_id, artifact_id)
        VALUES ($1::uuid, $2::uuid)
        ON CONFLICT DO NOTHING
        """,
        str(profile["id"]),
        artifact_id,
    )
    await db.execute(
        "UPDATE profiles SET credibility_score = credibility_score + 1 WHERE id = $1::uuid",
        str(profile["id"]),
    )
    return {"ok": True, "artifact_id": artifact_id, "username": body.username}


@router.delete("/{artifact_id}/star")
async def unstar_artifact(artifact_id: str, body: StarRequest) -> dict:
    profile = await db.fetchrow("SELECT id FROM profiles WHERE username = $1", body.username)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    await db.execute(
        "DELETE FROM stars WHERE user_id = $1::uuid AND artifact_id = $2::uuid",
        str(profile["id"]),
        artifact_id,
    )
    return {"ok": True, "artifact_id": artifact_id, "username": body.username}
