"""Access-control helpers shared by routers."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Course, Enrollment, Squad, SquadMember, User


def get_course_for(db: Session, user: User, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(404, "course_not_found")
    if user.role == "lecturer" and course.lecturer_id == user.id:
        return course
    enrolled = db.scalar(select(Enrollment.id).where(Enrollment.course_id == course_id, Enrollment.user_id == user.id))
    if not enrolled:
        raise HTTPException(403, "not_enrolled")
    return course


def get_squad_for(db: Session, user: User, squad_id: int) -> Squad:
    squad = db.get(Squad, squad_id)
    if squad is None:
        raise HTTPException(404, "squad_not_found")
    course = db.get(Course, squad.course_id)
    if user.role == "lecturer" and course.lecturer_id == user.id:
        return squad
    if not db.scalar(select(SquadMember.id).where(SquadMember.squad_id == squad_id, SquadMember.user_id == user.id)):
        raise HTTPException(403, "not_in_squad")
    return squad


def is_course_lecturer(db: Session, user: User, course_id: int) -> bool:
    course = db.get(Course, course_id)
    return course is not None and user.role == "lecturer" and course.lecturer_id == user.id
