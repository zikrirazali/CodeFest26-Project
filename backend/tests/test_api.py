from datetime import timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import LedgerEntry, SectionProgress, User
from app.services import accountability, ledger, sandbox

FAST = {"scroll_depth": 1.0, "avg_scroll_velocity": 300, "hidden_ms": 0}


# --- auth -------------------------------------------------------------------

def test_protected_routes_need_jwt(client):
    assert client.get("/api/courses").status_code == 401
    assert client.get("/api/courses", headers={"Authorization": "Bearer forged"}).status_code == 401


def test_register_creates_student_only(client):
    r = client.post("/api/auth/register", json={"name": "New Kid", "email": "new@x.my", "password": "longenough"})
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "student"


# --- Pace Gate ----------------------------------------------------------------

def test_locked_section_payload_is_never_sent(client, daniel):
    module = client.get("/api/modules/1", headers=daniel).json()
    locked = [s for s in module["sections"] if s["status"] == "locked"]
    r = client.get(f"/api/sections/{locked[0]['id']}", headers=daniel)
    assert r.status_code == 423
    assert "body_en" not in r.text


def test_rushing_triggers_checkpoint_then_correct_answer_unlocks(client, daniel):
    s = client.get("/api/sections/1", headers=daniel).json()
    r = client.post(f"/api/sections/{s['id']}/complete", json=FAST, headers=daniel).json()
    assert r["unlocked"] is False and "too_fast" in r["reasons"]
    assert "answer" not in r["gate"]  # never leak the answer

    r = client.post(f"/api/sections/{s['id']}/checkpoint", json={"choice": 2}, headers=daniel).json()
    assert r["correct"] and r["unlocked"] and r["points"] == 3
    assert client.get("/api/sections/2", headers=daniel).status_code == 200


def test_wrong_answer_closes_gate_and_restarts_clock(client, daniel):
    client.get("/api/sections/1", headers=daniel)
    client.post("/api/sections/1/complete", json=FAST, headers=daniel)
    r = client.post("/api/sections/1/checkpoint", json={"choice": 0}, headers=daniel).json()
    assert r["correct"] is False
    # Brute force blocked: the gate is closed until they try to complete again.
    assert client.post("/api/sections/1/checkpoint", json={"choice": 2}, headers=daniel).status_code == 409


def test_genuine_reading_unlocks_on_server_time(client, daniel):
    client.get("/api/sections/1", headers=daniel)
    with SessionLocal() as db:  # simulate the student having read for 3 minutes
        uid = db.scalar(select(User.id).where(User.email == "daniel@student.tempa.my"))
        p = db.scalar(select(SectionProgress).where(SectionProgress.user_id == uid, SectionProgress.section_id == 1))
        p.served_at -= timedelta(minutes=3)
        db.commit()
    r = client.post("/api/sections/1/complete", json=FAST, headers=daniel).json()
    assert r == {"unlocked": True, "method": "read", "points": 2}


def test_lying_telemetry_cannot_beat_server_clock(client, daniel):
    client.get("/api/sections/1", headers=daniel)
    honest_looking = {"scroll_depth": 1.0, "avg_scroll_velocity": 1, "hidden_ms": 0}
    r = client.post("/api/sections/1/complete", json=honest_looking, headers=daniel).json()
    assert r["unlocked"] is False and r["reasons"] == ["too_fast"]


# --- Bounty Board + AI Referee ------------------------------------------------

def _open_code_bounty(client, headers, title):
    squad = client.get("/api/courses/1/my-squads", headers=headers).json()[0]
    board = client.get(f"/api/squads/{squad['id']}/board", headers=headers).json()
    return next(b for b in board["bounties"] if b["title_en"] == title)


def test_claim_submit_fail_then_pass_awards_points(client, ravi):
    b = _open_code_bounty(client, ravi, "Feedback keyword counter")
    assert client.post(f"/api/bounties/{b['id']}/claim", headers=ravi).status_code == 200

    buggy = "def word_count(text):\n    c = {}\n    for w in text.split():\n        c[w] = c.get(w, 0) + 1\n    return c\n"
    r = client.post(f"/api/bounties/{b['id']}/submit", json={"content": buggy, "lang": "ms"}, headers=ravi).json()
    assert r["verdict"] == "fail" and r["hint"]["source"] == "rules"
    assert all("args" not in c for c in r["result"]["cases"] if c["hidden"])  # hidden inputs never leak

    good = ("def word_count(text):\n    c = {}\n    for w in text.lower().split():\n"
            "        w = w.strip('.,!?')\n        if w:\n            c[w] = c.get(w, 0) + 1\n    return c\n")
    r = client.post(f"/api/bounties/{b['id']}/submit", json={"content": good}, headers=ravi).json()
    assert r["verdict"] == "pass" and r["bounty"]["status"] == "verified"
    assert client.get("/api/home", headers=ravi).json()["points"] >= 20


def test_cannot_submit_someone_elses_bounty_or_hoard(client, ravi):
    b = _open_code_bounty(client, ravi, "Input sanitiser check")
    r = client.post(f"/api/bounties/{b['id']}/submit", json={"content": "x"}, headers=ravi)
    assert r.status_code == 409
    for title in ["Input sanitiser check", "Feedback keyword counter"]:
        client.post(f"/api/bounties/{_open_code_bounty(client, ravi, title)['id']}/claim", headers=ravi)
    third = _open_code_bounty(client, ravi, "README and user guide (BM + EN)")
    assert client.post(f"/api/bounties/{third['id']}/claim", headers=ravi).json()["detail"] == "too_many_claims"


def test_artifact_needs_lecturer_review(client, lecturer, ravi):
    queue = client.get("/api/courses/1/dashboard", headers=lecturer).json()["review_queue"]
    bid = queue[0]["bounty_id"]
    assert client.post(f"/api/bounties/{bid}/review", json={"approve": True}, headers=ravi).status_code == 403
    r = client.post(f"/api/bounties/{bid}/review", json={"approve": True}, headers=lecturer).json()
    assert r["status"] == "verified"


def test_sandbox_blocks_escape_attempts():
    for code in ["import os\ndef f(): pass", "def f(): return open('x').read()",
                 "def f(): return ().__class__.__bases__", "def f(): return eval('1')"]:
        assert sandbox.run_tests(code, "f", [{"args": [], "expected": None}])["error"]


def test_sandbox_timeout():
    r = sandbox.run_tests("def f():\n    while True: pass\n", "f", [{"args": [], "expected": 1}])
    assert r["error"] == "timeout"


# --- Accountability + transcript ---------------------------------------------

def test_dashboard_flags_coasting_member(client, lecturer):
    squads = client.get("/api/courses/1/dashboard", headers=lecturer).json()["squads"]
    alpha = next(s for s in squads if s["name"] == "Squad Alpha")
    status = {m["name"]: m["status"] for m in alpha["members"]}
    assert status["Ravi Kumar"] == "coasting" and status["Amir Hakimi"] == "carrying"


def test_balanced_matching_mixes_strong_and_weak():
    groups = accountability.form_squads([(f"u{i}", s) for i, s in enumerate([90, 80, 30, 20, 10, 5])], 3, "balanced")
    totals = sorted(sum(x[1] for x in g) for g in groups)
    assert totals[1] - totals[0] < 40
    tiered = accountability.form_squads([(f"u{i}", s) for i, s in enumerate([90, 80, 70, 20, 10, 5])], 3, "tiered")
    assert [x[1] for x in tiered[0]] == [90, 80, 70]


def test_transcript_is_public_and_tamper_evident(client, ravi):
    me = client.get("/api/transcript/me", headers=ravi).json()
    assert me["integrity"]["valid"]
    public = client.get(f"/api/public/transcript/{me['student']['public_id']}").json()
    assert public["total_points"] == me["total_points"]

    with SessionLocal() as db:  # someone inflates points directly in the database
        user = db.scalar(select(User).where(User.public_id == me["student"]["public_id"]))
        entry = db.scalar(select(LedgerEntry).where(LedgerEntry.user_id == user.id).limit(1))
        entry.points = 999
        db.commit()
        assert ledger.verify_chain(user, ledger.entries_for(db, user))["valid"] is False
    assert client.get("/api/transcript/me", headers=ravi).json()["integrity"]["valid"] is False
