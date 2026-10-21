# Tempa · *Tempa kemahiran, bukan sekadar slaid*

**Forge skills, not slides.** Tempa is a gamified accountability and active-learning platform that replaces passive content consumption with proof of work.

> UTP CodeFest'26 · **Track 2: Education and Human Development**
> Innovation areas covered: adaptive learning pacing engine · AI-powered peer study companion · gamified behavioural engagement tracker · smart career-trajectory evidence

---

## The problem

- **Passive consumption.** Students scroll through long slides and PDFs and click "next" without reading. Nothing checks whether they understood.
- **Free-riders in group work.** One or two people carry the project, everyone gets the same mark, and lecturers can't see who did what.
- **Grades don't prove skills.** A 3.57 CGPA tells an employer nothing about whether this student can actually write working code.

## The solution: four mechanics

| | Mechanic | What it does |
|---|---|---|
| 🔐 | **Adaptive Pace Gate** | Lessons arrive one micro-section at a time. The server (acting as BFF) doesn't send the next section until the current one is unlocked. If you rush (too fast for your reading speed, didn't scroll to the end, skimming, tab in the background), you must answer a checkpoint question to proceed. A wrong answer closes the gate and restarts the reading clock, so guessing doesn't work. The required pace adapts: careful readers become *trusted* and the gate relaxes; repeat rushers face a stricter one. |
| 🎯 | **Academic Bounty Board** | Group projects are split into claimable bounties (code tasks and artifacts such as UML diagrams and READMEs). Each student claims work explicitly, can hold at most two active claims, and loses idle claims after 72h. A live contribution chart compares each member to a fair share and flags *coasting* and *carrying* members for everyone, including the lecturer. |
| 🤖 | **AI Referee** | Code bounties are graded by an isolated sandbox against visible **and hidden** tests, so a pass is objective and doesn't depend on who submitted. When a submission fails, an AI coach (Claude) gives a Socratic hint in BM or English. It never gives the answer. Artifacts are routed to the lecturer for review. The lecturer can also form next semester's squads from *verified* competence (balanced or tiered). |
| 📜 | **Permanent Developer Transcript** | Every merit point is written to an append-only, HMAC-chained ledger that doesn't reset at the end of a semester. Students share a public link employers can open; it shows skills earned from verified work and an integrity check. Editing even one row in the database breaks the chain visibly. |

Fully **bilingual (Bahasa Melayu + English)**, installable as a **PWA**, works on phones.

## Screens

| Student | Lecturer |
|---|---|
| Home: points, streak, badges, pace profile | Squad accountability (coasting / carrying flags) |
| Module reader with Pace Gate checkpoint | Pace Gate analytics per module |
| Squad Bounty Board + contribution chart | Artifact review queue |
| Code bounty with referee results + AI hint | Competence-based squad matching |
| Verifiable transcript + public share link | Interactive API docs at `/docs` |

## Quick start (zero setup, SQLite)

Requires Python 3.11+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload
```

Open **http://localhost:8000**. Demo data loads automatically. All accounts use the password `demo1234`:

| Account | Role | Story |
|---|---|---|
| `lecturer@tempa.my` | Lecturer | Dashboard, review queue, squad matching |
| `ravi@student.tempa.my` | Student | Flagged as **coasting** in Squad Alpha |
| `amir@student.tempa.my` | Student | **Carrying** Squad Alpha, trusted reader |
| `daniel@student.tempa.my` | Student | Fresh start, good for trying the Pace Gate |

Swagger/OpenAPI docs: **http://localhost:8000/docs**. Click *Authorize* and paste a token from `POST /api/auth/login`.

### With PostgreSQL (production-like)

```bash
docker compose up --build
```

### Enable the AI coach (optional)

Set `ANTHROPIC_API_KEY` (see [.env.example](.env.example)). Without a key, the referee falls back to deterministic rule-based hints, so the platform works fully offline.

### Run tests

```bash
cd backend
pytest -q
```

15 tests cover JWT protection, the BFF cut-off for locked content, rushing → checkpoint → unlock, brute-force protection, why faked telemetry doesn't help, sandbox escape attempts and timeouts, hidden-test secrecy, claim limits, lecturer-only review, coasting detection, squad matching, and ledger tamper detection.

## Architecture

```
┌──────────── PWA (vanilla JS, BM/EN, offline shell) ────────────┐
│ Reader + scroll/visibility telemetry · Bounty Board · Transcript│
└───────────────▲──────────────────────────────┬─────────────────┘
                │ JSON over HTTPS, JWT bearer  │
┌───────────────┴──────────────────────────────▼─────────────────┐
│ FastAPI BFF                                                    │
│  auth ─ learn (Pace Gate) ─ bounties ─ courses/dashboard ─ transcript │
│  services: pacing · sandbox referee · AI coach · accountability · ledger│
└──────┬───────────────────────┬──────────────────────┬──────────┘
       │ SQLAlchemy            │ subprocess (isolated) │ HTTPS
┌──────▼───────┐      ┌────────▼────────┐     ┌───────▼────────┐
│ PostgreSQL   │      │ Python sandbox  │     │ Claude API     │
│ (SQLite dev) │      │ AST allow-list, │     │ hints only,    │
│              │      │ timeout, rlimit │     │ never grades   │
└──────────────┘      └─────────────────┘     └────────────────┘
```

Details, data model and security notes: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Pitch-deck outline and 3-minute demo script: [docs/PITCH.md](docs/PITCH.md).

| Layer | Tech |
|---|---|
| Frontend | HTML/CSS/vanilla JS PWA (no build step), service worker, i18n |
| Backend / BFF | Python 3.12, FastAPI, Pydantic, SQLAlchemy 2 |
| Database | PostgreSQL 16 (SQLite for local dev) |
| Auth | Stateless JWT (HS256), PBKDF2-SHA256 password hashing |
| AI | Anthropic Claude (`claude-opus-5-5`) for Socratic hints, with a rule-based fallback |
| Integrity | HMAC-SHA256 hash-chained merit ledger |
| Deploy | Docker, docker-compose |

## Repository layout

```
backend/
  app/
    main.py            FastAPI app, static PWA hosting
    models.py          Relational schema
    security.py        JWT + password hashing
    seed.py            Bilingual demo course, challenges, squads
    routers/           auth · learn · bounties · courses · transcript
    services/          pacing · sandbox · ai_coach · accountability · ledger
  tests/               pytest suite
frontend/              PWA (index.html, styles.css, js/, sw.js)
docs/                  Architecture + pitch materials
```

## AI tools disclosure

As required by the competition guidelines:

- **Development:** Large parts of this codebase (backend, frontend, tests and documentation) were written with **Claude Code** (Anthropic), working from our team's concept brief. Team members reviewed, ran and tested the output.
- **In the product:** The AI coach calls the **Anthropic Claude API** to write short hints for failed code submissions. The AI never decides pass/fail; deterministic tests do.

## References

- Ministry of Education Malaysia (2024) and Kementerian Pendidikan (2025), as cited in the CodeFest'26 Track 2 brief, on engagement, retention and one-size-fits-all digital materials.
- UNESCO (2024), as cited in the Track 2 brief, on the school-to-work transition and the need for active learning ecosystems.
- FastAPI, SQLAlchemy, PyJWT and the Anthropic Python SDK are used under their respective open-source licences.
