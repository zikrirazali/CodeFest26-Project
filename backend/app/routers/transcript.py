"""Permanent Developer Transcript: private view and public, employer-verifiable view."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import current_user
from ..services import ledger

router = APIRouter(prefix="/api", tags=["transcript"])


def _transcript(user: User, db: Session) -> dict:
    entries = ledger.entries_for(db, user)
    skills: dict[str, dict] = {}
    for e in entries:
        s = skills.setdefault(e.skill_tag, {"points": 0, "bounties": 0})
        s["points"] += e.points
        s["bounties"] += e.kind == "bounty"
    return {
        "student": {"name": user.name, "public_id": user.public_id, "member_since": user.created_at.date().isoformat()},
        "total_points": sum(e.points for e in entries),
        "verified_bounties": sum(e.kind == "bounty" for e in entries),
        "skills": dict(sorted(skills.items(), key=lambda kv: -kv[1]["points"])),
        "integrity": ledger.verify_chain(user, entries),
        "entries": [{"seq": e.seq, "kind": e.kind, "points": e.points, "skill_tag": e.skill_tag, "note": e.note,
                     "at": e.created_at.isoformat() + "Z", "hash": e.hash} for e in reversed(entries)],
    }


@router.get("/transcript/me")
def my_transcript(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _transcript(user, db)


@router.get("/public/transcript/{public_id}")
def public_transcript(public_id: str, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.public_id == public_id, User.role == "student"))
    if user is None:
        raise HTTPException(404, "not_found")
    return _transcript(user, db)
