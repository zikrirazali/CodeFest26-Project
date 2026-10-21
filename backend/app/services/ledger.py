"""Permanent Developer Transcript: an append-only, HMAC-chained merit ledger.

Each entry's hash covers its own fields plus the previous entry's hash, signed with
LEDGER_SECRET. Editing, deleting or reordering any row (even directly in PostgreSQL)
breaks the chain from that point on, and nobody without the secret can re-forge it.
Points never reset at the end of a semester; they accumulate across courses.
"""
import hashlib
import hmac
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..models import LedgerEntry, User, utcnow

GENESIS = "0" * 64


def _digest(user: User, seq: int, kind: str, points: int, skill_tag: str, ref: str,
            created_at: datetime, prev_hash: str) -> str:
    payload = json.dumps(
        [user.public_id, seq, kind, points, skill_tag, ref, created_at.isoformat(timespec="seconds"), prev_hash],
        separators=(",", ":"),
    )
    return hmac.new(config.LEDGER_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def has_entry(db: Session, user: User, kind: str, ref: str) -> bool:
    stmt = select(LedgerEntry.id).where(LedgerEntry.user_id == user.id, LedgerEntry.kind == kind, LedgerEntry.ref == ref)
    return db.scalar(stmt) is not None


def append(db: Session, user: User, kind: str, points: int, skill_tag: str, ref: str,
           note: str = "", created_at: datetime | None = None) -> LedgerEntry | None:
    """Award points once per (kind, ref). Returns None if already awarded."""
    if has_entry(db, user, kind, ref):
        return None
    last = db.scalar(select(LedgerEntry).where(LedgerEntry.user_id == user.id).order_by(LedgerEntry.seq.desc()).limit(1))
    seq = (last.seq + 1) if last else 1
    prev_hash = last.hash if last else GENESIS
    created_at = (created_at or utcnow()).replace(microsecond=0)
    entry = LedgerEntry(
        user_id=user.id, seq=seq, kind=kind, points=points, skill_tag=skill_tag, ref=ref, note=note,
        created_at=created_at, prev_hash=prev_hash,
        hash=_digest(user, seq, kind, points, skill_tag, ref, created_at, prev_hash),
    )
    db.add(entry)
    db.flush()
    return entry


def entries_for(db: Session, user: User) -> list[LedgerEntry]:
    return list(db.scalars(select(LedgerEntry).where(LedgerEntry.user_id == user.id).order_by(LedgerEntry.seq)))


def verify_chain(user: User, entries: list[LedgerEntry]) -> dict:
    prev = GENESIS
    for i, e in enumerate(entries, start=1):
        expected = _digest(user, e.seq, e.kind, e.points, e.skill_tag, e.ref, e.created_at, prev)
        if e.seq != i or e.prev_hash != prev or not hmac.compare_digest(expected, e.hash):
            return {"valid": False, "broken_at_seq": e.seq, "head": None}
        prev = e.hash
    return {"valid": True, "broken_at_seq": None, "head": prev}
