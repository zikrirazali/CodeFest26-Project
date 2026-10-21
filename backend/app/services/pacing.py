"""Adaptive Pace Gate.

The server (acting as BFF) never sends a section's content until the previous one is
unlocked. A section unlocks either by genuinely reading it, or, if the student rushed,
by answering its checkpoint question correctly.

Elapsed time is measured from the server's own `served_at` timestamp, so a student
cannot fake reading time. Client telemetry (scroll depth, scroll speed, time hidden)
can only make the verdict stricter, never more lenient.
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..models import Section, SectionProgress, User

# Fraction of a full-speed read we require. Adapts to the learner's track record.
FACTOR_TRUSTED = 0.35
FACTOR_STEADY = 0.5
FACTOR_RUSHING = 0.75

FLICK_VELOCITY_PX_S = 6000  # sustained average above this is skimming, not reading


@dataclass
class Telemetry:
    scroll_depth: float = 0.0  # 0..1, furthest point reached
    avg_scroll_velocity: float = 0.0  # px/s while scrolling
    hidden_ms: int = 0  # time the tab was in the background


def pace_profile(db: Session, user: User) -> dict:
    rows = list(db.scalars(
        select(SectionProgress)
        .where(SectionProgress.user_id == user.id, SectionProgress.unlocked_at.is_not(None))
        .order_by(SectionProgress.unlocked_at.desc())
        .limit(8)
    ))
    rushes = sum(r.rush_count for r in rows)
    if len(rows) >= 4 and rushes == 0:
        return {"label": "trusted", "factor": FACTOR_TRUSTED, "recent": len(rows), "rushes": rushes}
    if rushes >= 3:
        return {"label": "rushing", "factor": FACTOR_RUSHING, "recent": len(rows), "rushes": rushes}
    return {"label": "steady", "factor": FACTOR_STEADY, "recent": len(rows), "rushes": rushes}


def word_count(section: Section) -> int:
    return len(section.body_en.split())


def min_dwell_seconds(section: Section, factor: float) -> float:
    full_read = word_count(section) / config.READING_WPM * 60
    return round(max(config.MIN_DWELL_SECONDS, full_read * factor), 1)


def evaluate(elapsed_s: float, min_dwell_s: float, t: Telemetry) -> list[str]:
    """Return the reasons a completion attempt is gated; empty means it passes."""
    reasons = []
    if elapsed_s < min_dwell_s:
        reasons.append("too_fast")
    if t.scroll_depth < 0.85:
        reasons.append("not_scrolled")
    if t.avg_scroll_velocity > FLICK_VELOCITY_PX_S:
        reasons.append("skimming")
    if elapsed_s > 0 and t.hidden_ms / 1000 > elapsed_s * 0.5:
        reasons.append("tab_away")
    return reasons
