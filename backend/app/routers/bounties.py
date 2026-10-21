"""Academic Bounty Board: claim, deliver, verify."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import Bounty, Challenge, Squad, SquadMember, Submission, User, utcnow
from ..security import current_user
from ..services import accountability, ai_coach, ledger, sandbox
from .common import get_squad_for, is_course_lecturer

router = APIRouter(prefix="/api", tags=["bounties"])


class SubmitIn(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    lang: str = Field("en", pattern="^(en|ms)$")


class RunIn(BaseModel):
    code: str = Field(min_length=1, max_length=20_000)


class ReviewIn(BaseModel):
    approve: bool
    feedback: str = Field("", max_length=2000)


class BountyIn(BaseModel):
    title_en: str = Field(min_length=3, max_length=200)
    title_ms: str = Field(min_length=3, max_length=200)
    description_en: str = ""
    description_ms: str = ""
    points: int = Field(10, ge=1, le=100)
    skill_tag: str = Field(min_length=2, max_length=40)
    kind: str = Field("artifact", pattern="^(code|artifact)$")
    challenge_slug: str | None = None


def bounty_out(b: Bounty, detail: bool = False) -> dict:
    out = {
        "id": b.id, "squad_id": b.squad_id, "title_en": b.title_en, "title_ms": b.title_ms,
        "points": b.points, "skill_tag": b.skill_tag, "kind": b.kind, "status": b.status,
        "claimed_by": {"id": b.claimed_by.id, "name": b.claimed_by.name} if b.claimed_by else None,
        "claimed_at": b.claimed_at.isoformat() + "Z" if b.claimed_at else None,
        "verified_at": b.verified_at.isoformat() + "Z" if b.verified_at else None,
    }
    if detail:
        out.update(description_en=b.description_en, description_ms=b.description_ms)
        if b.challenge:
            c = b.challenge
            out["challenge"] = {
                "slug": c.slug, "title_en": c.title_en, "title_ms": c.title_ms, "prompt_en": c.prompt_en,
                "prompt_ms": c.prompt_ms, "function_name": c.function_name, "starter_code": c.starter_code,
                "visible_tests": [{"args": t["args"], "expected": t["expected"]} for t in c.tests if not t.get("hidden")],
                "hidden_count": sum(1 for t in c.tests if t.get("hidden")),
            }
    return out


def _load_bounty(db: Session, user: User, bounty_id: int) -> tuple[Bounty, Squad]:
    b = db.get(Bounty, bounty_id)
    if b is None:
        raise HTTPException(404, "bounty_not_found")
    return b, get_squad_for(db, user, b.squad_id)


def _verify(db: Session, b: Bounty) -> None:
    b.status, b.verified_at = "verified", utcnow()
    ledger.append(db, b.claimed_by, "bounty", b.points, b.skill_tag, f"bounty:{b.id}", note=b.title_en)


@router.get("/courses/{course_id}/my-squads")
def my_squads(course_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    stmt = select(Squad).where(Squad.course_id == course_id)
    if not is_course_lecturer(db, user, course_id):
        stmt = stmt.join(SquadMember, SquadMember.squad_id == Squad.id).where(SquadMember.user_id == user.id)
    return [{"id": s.id, "name": s.name, "project_en": s.project_en, "project_ms": s.project_ms,
             "members": [{"id": m.user.id, "name": m.user.name} for m in s.members]} for s in db.scalars(stmt)]


@router.get("/squads/{squad_id}/board")
def board(squad_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    squad = get_squad_for(db, user, squad_id)
    accountability.release_stale_claims(db, squad.id)
    db.commit()
    bounties = db.scalars(select(Bounty).where(Bounty.squad_id == squad.id).order_by(Bounty.id))
    return {
        "squad": {"id": squad.id, "name": squad.name, "project_en": squad.project_en, "project_ms": squad.project_ms},
        "bounties": [bounty_out(b) for b in bounties],
        "contributions": accountability.contributions(db, squad),
        "claim_ttl_hours": config.CLAIM_TTL_HOURS,
    }


@router.post("/squads/{squad_id}/bounties")
def create_bounty(squad_id: int, body: BountyIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    squad = get_squad_for(db, user, squad_id)
    if not is_course_lecturer(db, user, squad.course_id):
        raise HTTPException(403, "lecturer_only")
    challenge = None
    if body.kind == "code":
        challenge = db.scalar(select(Challenge).where(Challenge.slug == body.challenge_slug))
        if challenge is None:
            raise HTTPException(400, "code_bounty_needs_challenge")
    b = Bounty(squad_id=squad.id, **body.model_dump(exclude={"challenge_slug"}),
               challenge_id=challenge.id if challenge else None)
    db.add(b)
    db.commit()
    return bounty_out(b, detail=True)


@router.get("/bounties/{bounty_id}")
def get_bounty(bounty_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    b, _ = _load_bounty(db, user, bounty_id)
    subs = db.scalars(select(Submission).where(Submission.bounty_id == b.id).order_by(Submission.id.desc()).limit(10))
    out = bounty_out(b, detail=True)
    out["submissions"] = [{"id": s.id, "user_id": s.user_id, "verdict": s.verdict, "passed": s.passed, "total": s.total,
                           "feedback": s.feedback, "created_at": s.created_at.isoformat() + "Z",
                           "content": s.content if (s.user_id == user.id or user.role == "lecturer") else None}
                          for s in subs]
    return out


@router.post("/bounties/{bounty_id}/claim")
def claim(bounty_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    b, squad = _load_bounty(db, user, bounty_id)
    accountability.release_stale_claims(db, squad.id)
    if user.role != "student":
        raise HTTPException(403, "students_only")
    if b.status != "open":
        raise HTTPException(409, "not_open")
    active = db.scalar(select(func.count(Bounty.id)).where(
        Bounty.claimed_by_id == user.id, Bounty.status.in_(("claimed", "submitted"))))
    if active >= config.MAX_ACTIVE_CLAIMS:
        raise HTTPException(409, "too_many_claims")  # no hoarding work you won't do
    b.status, b.claimed_by_id, b.claimed_at = "claimed", user.id, utcnow()
    db.commit()
    return bounty_out(b)


@router.post("/bounties/{bounty_id}/release")
def release(bounty_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    b, _ = _load_bounty(db, user, bounty_id)
    if b.claimed_by_id != user.id or b.status != "claimed":
        raise HTTPException(409, "not_your_claim")
    b.status, b.claimed_by_id, b.claimed_at = "open", None, None
    db.commit()
    return bounty_out(b)


@router.post("/challenges/{slug}/run")
def practice_run(slug: str, body: RunIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Run against visible tests only. Free, unlimited, no points."""
    c = db.scalar(select(Challenge).where(Challenge.slug == slug))
    if c is None:
        raise HTTPException(404, "challenge_not_found")
    return sandbox.run_tests(body.code, c.function_name, c.tests, include_hidden=False)


@router.post("/bounties/{bounty_id}/submit")
def submit(bounty_id: int, body: SubmitIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    b, _ = _load_bounty(db, user, bounty_id)
    if b.claimed_by_id != user.id or b.status not in ("claimed", "submitted"):
        raise HTTPException(409, "claim_it_first")

    if b.kind == "code":
        c = b.challenge
        result = sandbox.run_tests(body.content, c.function_name, c.tests, include_hidden=True)
        passed = result["error"] is None and result["passed"] == result["total"]
        coach = None if passed else ai_coach.hint(c, body.content, result, body.lang)
        db.add(Submission(bounty_id=b.id, user_id=user.id, content=body.content, passed=result["passed"],
                          total=result["total"], verdict="pass" if passed else "fail",
                          feedback=coach["text"] if coach else ""))
        if passed:
            _verify(db, b)
        db.commit()
        return {"verdict": "pass" if passed else "fail", "result": result, "hint": coach, "bounty": bounty_out(b)}

    db.add(Submission(bounty_id=b.id, user_id=user.id, content=body.content, verdict="pending_review"))
    b.status = "submitted"
    db.commit()
    return {"verdict": "pending_review", "bounty": bounty_out(b)}


@router.post("/bounties/{bounty_id}/review")
def review(bounty_id: int, body: ReviewIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    b, squad = _load_bounty(db, user, bounty_id)
    if not is_course_lecturer(db, user, squad.course_id):
        raise HTTPException(403, "lecturer_only")
    if b.status != "submitted":
        raise HTTPException(409, "nothing_to_review")
    sub = db.scalar(select(Submission).where(Submission.bounty_id == b.id).order_by(Submission.id.desc()).limit(1))
    sub.verdict, sub.feedback = ("approved" if body.approve else "rejected"), body.feedback
    if body.approve:
        _verify(db, b)
    else:
        b.status = "claimed"  # back to the claimant to fix
        b.claimed_at = utcnow()
    db.commit()
    return bounty_out(b)
