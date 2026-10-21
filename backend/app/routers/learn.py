"""Adaptive Pace Gate endpoints. Content is released one section at a time."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Module, Section, SectionProgress, User, utcnow
from ..security import current_user
from ..services import ledger, pacing
from .common import get_course_for

router = APIRouter(prefix="/api", tags=["learn"])

READ_POINTS = 2
CHECKPOINT_POINTS = 3


class TelemetryIn(BaseModel):
    scroll_depth: float = Field(0, ge=0, le=1)
    avg_scroll_velocity: float = Field(0, ge=0)
    hidden_ms: int = Field(0, ge=0)


class CheckpointIn(BaseModel):
    choice: int = Field(ge=0, le=9)


def _progress(db: Session, user: User, section: Section) -> SectionProgress | None:
    return db.scalar(select(SectionProgress).where(
        SectionProgress.user_id == user.id, SectionProgress.section_id == section.id))


def _status_map(db: Session, user: User, module: Module) -> dict[int, str]:
    """done | current | locked for every section in the module."""
    ids = [s.id for s in module.sections]
    unlocked = set(db.scalars(select(SectionProgress.section_id).where(
        SectionProgress.user_id == user.id, SectionProgress.section_id.in_(ids),
        SectionProgress.unlocked_at.is_not(None))))
    statuses, current_given = {}, False
    for s in module.sections:
        if s.id in unlocked:
            statuses[s.id] = "done"
        elif not current_given:
            statuses[s.id] = "current"
            current_given = True
        else:
            statuses[s.id] = "locked"
    return statuses


def _load_section(db: Session, user: User, section_id: int) -> tuple[Section, Module, str]:
    section = db.get(Section, section_id)
    if section is None:
        raise HTTPException(404, "section_not_found")
    module = db.get(Module, section.module_id)
    get_course_for(db, user, module.course_id)
    status = _status_map(db, user, module)[section.id]
    if status == "locked" and user.role != "lecturer":
        # BFF cut-off: locked content is never serialised to the client.
        raise HTTPException(423, "section_locked")
    return section, module, status


def _checkpoint_payload(s: Section) -> dict:
    return {"question_en": s.question_en, "question_ms": s.question_ms, "options": s.options}


@router.get("/courses/{course_id}/modules")
def list_modules(course_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    get_course_for(db, user, course_id)
    modules = db.scalars(select(Module).where(Module.course_id == course_id).order_by(Module.position))
    out = []
    for m in modules:
        statuses = _status_map(db, user, m)
        out.append({"id": m.id, "title_en": m.title_en, "title_ms": m.title_ms,
                    "sections": len(statuses), "done": sum(v == "done" for v in statuses.values())})
    return out


@router.get("/modules/{module_id}")
def get_module(module_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    module = db.get(Module, module_id)
    if module is None:
        raise HTTPException(404, "module_not_found")
    get_course_for(db, user, module.course_id)
    statuses = _status_map(db, user, module)
    return {
        "id": module.id, "course_id": module.course_id, "title_en": module.title_en, "title_ms": module.title_ms,
        "pace": pacing.pace_profile(db, user),
        "sections": [{"id": s.id, "position": s.position, "heading_en": s.heading_en,
                      "heading_ms": s.heading_ms, "status": statuses[s.id]} for s in module.sections],
    }


@router.get("/sections/{section_id}")
def get_section(section_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    section, _, status = _load_section(db, user, section_id)
    prog = _progress(db, user, section)
    if prog is None:
        prog = SectionProgress(user_id=user.id, section_id=section.id)
        db.add(prog)
    if status == "current" and prog.served_at is None:
        prog.served_at = utcnow()  # the server's clock starts here, not the client's
    db.commit()
    profile = pacing.pace_profile(db, user)
    return {
        "id": section.id, "module_id": section.module_id, "position": section.position, "status": status,
        "heading_en": section.heading_en, "heading_ms": section.heading_ms,
        "body_en": section.body_en, "body_ms": section.body_ms,
        "suggested_seconds": pacing.min_dwell_seconds(section, profile["factor"]),
        "gate": _checkpoint_payload(section) if prog.gate_open else None,
    }


@router.post("/sections/{section_id}/complete")
def complete_section(section_id: int, body: TelemetryIn, db: Session = Depends(get_db),
                     user: User = Depends(current_user)):
    section, _, status = _load_section(db, user, section_id)
    if status == "done":
        return {"unlocked": True, "already": True, "points": 0}
    prog = _progress(db, user, section)
    if prog is None or prog.served_at is None:
        raise HTTPException(409, "section_not_served")

    profile = pacing.pace_profile(db, user)
    elapsed = (utcnow() - prog.served_at).total_seconds()
    min_dwell = pacing.min_dwell_seconds(section, profile["factor"])
    reasons = pacing.evaluate(elapsed, min_dwell, pacing.Telemetry(**body.model_dump()))

    if reasons:
        prog.rush_count += 1
        prog.gate_open = True
        db.commit()
        return {"unlocked": False, "reasons": reasons, "elapsed": round(elapsed, 1),
                "required": min_dwell, "gate": _checkpoint_payload(section)}

    prog.unlocked_at, prog.method, prog.gate_open = utcnow(), "read", False
    entry = ledger.append(db, user, "section_read", READ_POINTS, "reading", f"section:{section.id}",
                          note=section.heading_en)
    db.commit()
    return {"unlocked": True, "method": "read", "points": entry.points if entry else 0}


@router.post("/sections/{section_id}/checkpoint")
def answer_checkpoint(section_id: int, body: CheckpointIn, db: Session = Depends(get_db),
                      user: User = Depends(current_user)):
    section, _, status = _load_section(db, user, section_id)
    if status == "done":
        return {"correct": True, "unlocked": True, "points": 0}
    prog = _progress(db, user, section)
    if prog is None or not prog.gate_open:
        raise HTTPException(409, "no_open_gate")

    prog.attempts += 1
    correct = body.choice == section.answer
    if prog.first_try_correct is None:
        prog.first_try_correct = correct

    if not correct:
        # Wrong answer: gate closes and the reading clock restarts. No brute-forcing.
        prog.gate_open = False
        prog.served_at = utcnow()
        db.commit()
        return {"correct": False, "unlocked": False,
                "explanation_en": "Re-read the section, then try again.",
                "explanation_ms": "Baca semula bahagian ini, kemudian cuba lagi."}

    prog.unlocked_at, prog.method, prog.gate_open = utcnow(), "checkpoint", False
    points = CHECKPOINT_POINTS if prog.attempts == 1 else 1
    entry = ledger.append(db, user, "checkpoint", points, "reading", f"section:{section.id}",
                          note=section.heading_en)
    db.commit()
    return {"correct": True, "unlocked": True, "points": entry.points if entry else 0,
            "explanation_en": section.explanation_en, "explanation_ms": section.explanation_ms}
