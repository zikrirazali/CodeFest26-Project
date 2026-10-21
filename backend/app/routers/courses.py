"""Courses, student home stats, lecturer dashboard and competence-based squad matching."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (Bounty, Course, Enrollment, Module, Section, SectionProgress, Squad, SquadMember,
                      Submission, User)
from ..security import current_user
from ..services import accountability, ledger, pacing
from .common import get_course_for, is_course_lecturer

router = APIRouter(prefix="/api", tags=["courses"])


class MatchIn(BaseModel):
    squad_size: int = Field(3, ge=2, le=8)
    mode: str = Field("balanced", pattern="^(balanced|tiered)$")
    apply: bool = False
    label: str = Field("Next semester", max_length=40)


@router.get("/courses")
def list_courses(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role == "lecturer":
        courses = db.scalars(select(Course).where(Course.lecturer_id == user.id))
    else:
        courses = db.scalars(select(Course).join(Enrollment, Enrollment.course_id == Course.id)
                             .where(Enrollment.user_id == user.id))
    return [{"id": c.id, "code": c.code, "title_en": c.title_en, "title_ms": c.title_ms} for c in courses]


@router.get("/home")
def home(db: Session = Depends(get_db), user: User = Depends(current_user)):
    entries = ledger.entries_for(db, user)
    first_try = db.scalar(select(func.count(SectionProgress.id)).where(
        SectionProgress.user_id == user.id, SectionProgress.first_try_correct.is_(True))) or 0
    shares = []
    for squad in db.scalars(select(Squad).join(SquadMember, SquadMember.squad_id == Squad.id)
                            .where(SquadMember.user_id == user.id)):
        if len(squad.members) >= 3:
            c = accountability.contributions(db, squad)
            shares += [m["share"] for m in c["members"] if m["user_id"] == user.id]
    skills: dict[str, int] = {}
    for e in entries:
        skills[e.skill_tag] = skills.get(e.skill_tag, 0) + e.points
    return {
        "points": sum(e.points for e in entries),
        "streak": accountability.streak_days(entries),
        "badges": accountability.badges(entries, first_try, shares),
        "skills": skills,
        "pace": pacing.pace_profile(db, user),
        "recent": [{"kind": e.kind, "points": e.points, "note": e.note, "at": e.created_at.isoformat() + "Z"}
                   for e in reversed(entries[-6:])],
    }


@router.get("/courses/{course_id}/dashboard")
def dashboard(course_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    course = get_course_for(db, user, course_id)
    if not is_course_lecturer(db, user, course_id):
        raise HTTPException(403, "lecturer_only")

    squads = []
    for s in db.scalars(select(Squad).where(Squad.course_id == course_id).order_by(Squad.id)):
        c = accountability.contributions(db, s)
        pending = db.scalar(select(func.count(Bounty.id)).where(Bounty.squad_id == s.id, Bounty.status == "submitted"))
        squads.append({"id": s.id, "name": s.name, "project_en": s.project_en, "project_ms": s.project_ms,
                       "pending_reviews": pending, **c})

    modules = []
    for m in db.scalars(select(Module).where(Module.course_id == course_id).order_by(Module.position)):
        section_ids = [x.id for x in m.sections]
        rows = list(db.scalars(select(SectionProgress).where(SectionProgress.section_id.in_(section_ids))))
        done = [r for r in rows if r.unlocked_at]
        answered = [r for r in rows if r.first_try_correct is not None]
        modules.append({
            "id": m.id, "title_en": m.title_en, "title_ms": m.title_ms,
            "completions": len(done),
            "via_reading": sum(r.method == "read" for r in done),
            "via_checkpoint": sum(r.method == "checkpoint" for r in done),
            "rush_events": sum(r.rush_count for r in rows),
            "first_try_accuracy": round(sum(r.first_try_correct for r in answered) / len(answered), 2) if answered else None,
        })

    review_queue = [
        {"bounty_id": b.id, "title_en": b.title_en, "title_ms": b.title_ms, "squad_id": b.squad_id,
         "claimed_by": b.claimed_by.name if b.claimed_by else None,
         "content": db.scalar(select(Submission.content).where(Submission.bounty_id == b.id)
                              .order_by(Submission.id.desc()).limit(1))}
        for b in db.scalars(select(Bounty).join(Squad, Squad.id == Bounty.squad_id)
                            .where(Squad.course_id == course_id, Bounty.status == "submitted"))
    ]
    students = db.scalar(select(func.count(Enrollment.id)).where(Enrollment.course_id == course_id))
    return {"course": {"id": course.id, "code": course.code, "title_en": course.title_en, "title_ms": course.title_ms},
            "students": students, "squads": squads, "modules": modules, "review_queue": review_queue}


@router.post("/courses/{course_id}/match")
def match_squads(course_id: int, body: MatchIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Propose (or create) squads from verified competence on the ledger, not self-selection."""
    if not is_course_lecturer(db, user, course_id):
        raise HTTPException(403, "lecturer_only")
    students = list(db.scalars(select(User).join(Enrollment, Enrollment.user_id == User.id)
                               .where(Enrollment.course_id == course_id, User.role == "student")))
    scores = accountability.competence(db, [s.id for s in students])
    groups = accountability.form_squads([(s, scores[s.id]) for s in students], body.squad_size, body.mode)

    proposal = []
    for i, g in enumerate(groups, start=1):
        name = f"{body.label} · {'Tier' if body.mode == 'tiered' else 'Squad'} {i}"
        proposal.append({"name": name, "avg_competence": round(sum(x[1] for x in g) / len(g), 1) if g else 0,
                         "members": [{"id": u.id, "name": u.name, "competence": sc} for u, sc in g]})
        if body.apply:
            squad = Squad(course_id=course_id, name=name)
            squad.members = [SquadMember(user_id=u.id) for u, _ in g]
            db.add(squad)
    if body.apply:
        db.commit()
    return {"mode": body.mode, "applied": body.apply, "squads": proposal}
