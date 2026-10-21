"""Relational schema. Portable between PostgreSQL (production) and SQLite (local dev).

All timestamps are naive UTC.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_public_id() -> str:
    return uuid.uuid4().hex[:12]


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(16), unique=True, default=new_public_id)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20), default="student")  # student | lecturer
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20))
    title_en: Mapped[str] = mapped_column(String(200))
    title_ms: Mapped[str] = mapped_column(String(200))
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("course_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Squad(Base):
    __tablename__ = "squads"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    name: Mapped[str] = mapped_column(String(80))
    project_en: Mapped[str] = mapped_column(String(200), default="")
    project_ms: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    members: Mapped[list["SquadMember"]] = relationship(cascade="all, delete-orphan")


class SquadMember(Base):
    __tablename__ = "squad_members"
    __table_args__ = (UniqueConstraint("squad_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    squad_id: Mapped[int] = mapped_column(ForeignKey("squads.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    user: Mapped[User] = relationship()


class Challenge(Base):
    """An auto-gradable coding task. `tests` is a list of {args, expected, hidden}."""

    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    title_en: Mapped[str] = mapped_column(String(200))
    title_ms: Mapped[str] = mapped_column(String(200))
    prompt_en: Mapped[str] = mapped_column(Text)
    prompt_ms: Mapped[str] = mapped_column(Text)
    function_name: Mapped[str] = mapped_column(String(60))
    starter_code: Mapped[str] = mapped_column(Text)
    tests: Mapped[list] = mapped_column(JSON)
    skill_tag: Mapped[str] = mapped_column(String(40))


class Bounty(Base):
    """A claimable project deliverable. kind=code is graded by the AI Referee sandbox,
    kind=artifact (diagram, report, slides) is pre-checked then approved by the lecturer."""

    __tablename__ = "bounties"

    id: Mapped[int] = mapped_column(primary_key=True)
    squad_id: Mapped[int] = mapped_column(ForeignKey("squads.id"), index=True)
    title_en: Mapped[str] = mapped_column(String(200))
    title_ms: Mapped[str] = mapped_column(String(200))
    description_en: Mapped[str] = mapped_column(Text, default="")
    description_ms: Mapped[str] = mapped_column(Text, default="")
    points: Mapped[int] = mapped_column(Integer, default=10)
    skill_tag: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(20), default="code")  # code | artifact
    challenge_id: Mapped[int | None] = mapped_column(ForeignKey("challenges.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | claimed | submitted | verified
    claimed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    challenge: Mapped[Challenge | None] = relationship()
    claimed_by: Mapped[User | None] = relationship()


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    bounty_id: Mapped[int] = mapped_column(ForeignKey("bounties.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    verdict: Mapped[str] = mapped_column(String(20))  # pass | fail | pending_review | approved | rejected
    feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Module(Base):
    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    position: Mapped[int] = mapped_column(Integer)
    title_en: Mapped[str] = mapped_column(String(200))
    title_ms: Mapped[str] = mapped_column(String(200))

    sections: Mapped[list["Section"]] = relationship(order_by="Section.position")


class Section(Base):
    """One micro-lesson. Its checkpoint question is the 'proof' a rushing student must give."""

    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id"))
    position: Mapped[int] = mapped_column(Integer)
    heading_en: Mapped[str] = mapped_column(String(200))
    heading_ms: Mapped[str] = mapped_column(String(200))
    body_en: Mapped[str] = mapped_column(Text)
    body_ms: Mapped[str] = mapped_column(Text)
    question_en: Mapped[str] = mapped_column(Text)
    question_ms: Mapped[str] = mapped_column(Text)
    options: Mapped[dict] = mapped_column(JSON)  # {"en": [...], "ms": [...]}
    answer: Mapped[int] = mapped_column(Integer)
    explanation_en: Mapped[str] = mapped_column(Text, default="")
    explanation_ms: Mapped[str] = mapped_column(Text, default="")


class SectionProgress(Base):
    __tablename__ = "section_progress"
    __table_args__ = (UniqueConstraint("user_id", "section_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"))
    served_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    gate_open: Mapped[bool] = mapped_column(Boolean, default=False)
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    method: Mapped[str | None] = mapped_column(String(20), nullable=True)  # read | checkpoint
    rush_count: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    first_try_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class LedgerEntry(Base):
    """Append-only, HMAC-chained merit ledger: the Permanent Developer Transcript."""

    __tablename__ = "ledger_entries"
    __table_args__ = (UniqueConstraint("user_id", "seq"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(30))  # bounty | section_read | checkpoint
    points: Mapped[int] = mapped_column(Integer)
    skill_tag: Mapped[str] = mapped_column(String(40))
    ref: Mapped[str] = mapped_column(String(80))
    note: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
