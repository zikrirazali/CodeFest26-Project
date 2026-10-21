"""Squad contribution analytics, competence scores, squad matching, badges and streaks."""
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..models import Bounty, LedgerEntry, Squad, User, utcnow

COASTING_RATIO = 0.5  # below half of a fair share
CARRYING_RATIO = 1.5  # above one-and-a-half fair shares


def release_stale_claims(db: Session, squad_id: int) -> None:
    """A claim that sits idle past CLAIM_TTL_HOURS goes back on the board."""
    cutoff = utcnow() - timedelta(hours=config.CLAIM_TTL_HOURS)
    stale = db.scalars(select(Bounty).where(
        Bounty.squad_id == squad_id, Bounty.status == "claimed", Bounty.claimed_at < cutoff))
    for b in stale:
        b.status, b.claimed_by_id, b.claimed_at = "open", None, None
    db.flush()


def contributions(db: Session, squad: Squad) -> dict:
    """Who is actually doing the work: verified points per member and a status flag."""
    bounties = list(db.scalars(select(Bounty).where(Bounty.squad_id == squad.id)))
    total_available = sum(b.points for b in bounties)
    earned = defaultdict(int)
    active = defaultdict(int)
    for b in bounties:
        if b.status == "verified" and b.claimed_by_id:
            earned[b.claimed_by_id] += b.points
        elif b.status in ("claimed", "submitted") and b.claimed_by_id:
            active[b.claimed_by_id] += 1

    n = max(1, len(squad.members))
    total_earned = sum(earned.values())
    fair = 1 / n
    members = []
    for m in squad.members:
        share = earned[m.user_id] / total_earned if total_earned else 0.0
        status = "on_track"
        if total_earned >= 20:  # only judge once there's meaningful work done
            if share < fair * COASTING_RATIO:
                status = "coasting"
            elif share > fair * CARRYING_RATIO:
                status = "carrying"
        members.append({
            "user_id": m.user_id, "name": m.user.name, "points": earned[m.user_id],
            "share": round(share, 3), "active_claims": active[m.user_id], "status": status,
        })
    members.sort(key=lambda x: -x["points"])
    return {
        "fair_share": round(fair, 3), "total_earned": total_earned, "total_available": total_available,
        "progress": round(total_earned / total_available, 3) if total_available else 0.0, "members": members,
    }


def competence(db: Session, user_ids: list[int]) -> dict[int, int]:
    """Verified competence = lifetime points from the ledger (bounties weigh double)."""
    rows = db.execute(
        select(LedgerEntry.user_id, LedgerEntry.kind, func.sum(LedgerEntry.points))
        .where(LedgerEntry.user_id.in_(user_ids)).group_by(LedgerEntry.user_id, LedgerEntry.kind)
    )
    score = {uid: 0 for uid in user_ids}
    for uid, kind, pts in rows:
        score[uid] += pts * (2 if kind == "bounty" else 1)
    return score


def form_squads(scored: list[tuple[User, int]], size: int, mode: str) -> list[list[tuple[User, int]]]:
    """balanced: snake draft so every squad gets a mix of strong and developing members.
    tiered: group by similar competence (challenge squads for top performers)."""
    ranked = sorted(scored, key=lambda x: -x[1])
    n_squads = max(1, round(len(ranked) / max(2, size)))
    if mode == "tiered":
        per = -(-len(ranked) // n_squads)
        return [ranked[i:i + per] for i in range(0, len(ranked), per)]
    squads = [[] for _ in range(n_squads)]
    for i, item in enumerate(ranked):
        rnd, pos = divmod(i, n_squads)
        squads[pos if rnd % 2 == 0 else n_squads - 1 - pos].append(item)
    return squads


def streak_days(entries: list[LedgerEntry], today: date | None = None) -> int:
    today = today or utcnow().date()
    days = {e.created_at.date() for e in entries}
    if not days:
        return 0
    cursor = today if today in days else today - timedelta(days=1)
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def badges(entries: list[LedgerEntry], first_try_correct: int, squad_shares: list[float]) -> list[str]:
    kinds = defaultdict(int)
    for e in entries:
        kinds[e.kind] += 1
    earned = []
    if kinds["bounty"] >= 1:
        earned.append("first_bounty")
    if kinds["bounty"] >= 5:
        earned.append("bounty_hunter")
    if kinds["section_read"] >= 5:
        earned.append("deep_reader")
    if first_try_correct >= 3:
        earned.append("gate_breaker")
    if any(s >= 0.4 for s in squad_shares):
        earned.append("squad_anchor")
    s = streak_days(entries)
    if s >= 3:
        earned.append("streak_3")
    if s >= 7:
        earned.append("streak_7")
    return earned
