# Pitch materials

Outline follows the required CodeFest'26 slide structure. Fill in team details before submitting.

## 1. Project & Team
- **Project:** Tempa: *Forge skills, not slides / Tempa kemahiran, bukan sekadar slaid*
- **Team name:** _TODO_
- **Members & roles:** _TODO (e.g. backend/BFF, frontend/UX, AI & sandbox, pitch & research)_

## 2. Problem & Track
- **Track 2: Education and Human Development**
- **Problem:** Passive content consumption (long slides, PDFs) and free-riding in group work produce students with grades but no proven skills.
- **Target users:** University and pre-university students in Malaysia, their lecturers, and employers hiring graduates.
- **Why it matters:** One-size-fits-all digital material contributes to declining retention (MOE 2024). Without structured progression and reinforcement, students abandon courses (Kementerian Pendidikan 2025). The school-to-work transition suffers when academic progress doesn't translate into demonstrable skills (UNESCO 2024).
- **Current limitations:** LMS "mark as complete" buttons; peer evaluations at the end of the semester, when it's too late; transcripts that show grades, not evidence.

## 3. Solution & Value
- **Description:** Four connected mechanics: the Adaptive Pace Gate, the Academic Bounty Board, the AI Referee and the Permanent Developer Transcript.
- **Unique value:** Accountability is enforced by the system, not by peer complaints: the server controls content release, deterministic tests verify work, and an HMAC-chained ledger can't be edited without detection.
- **Core features:** checkpoint-gated micro-lessons · claimable bounties with anti-hoarding · coasting/carrying flags · sandboxed auto-grading with hidden tests · Socratic AI hints in BM/EN · lecturer review queue · competence-based squad matching · public verifiable transcript · badges and streaks · PWA.

## 4. Technical Implementation
- **Stack:** Vanilla-JS PWA → FastAPI BFF (Python) → PostgreSQL; JWT auth; Claude API; Docker.
- **Architecture:** see [ARCHITECTURE.md](ARCHITECTURE.md) (sequence diagram + anti-gaming table).
- **Integrations:** Anthropic Claude API (hints), SQLAlchemy, PyJWT; OpenAPI/Swagger auto-generated.

## 5. UX & Design
User journey (student):
1. Log in → home shows points, streak, badges and pace profile.
2. Open a module → read a micro-section → "continue".
3. Rushed? The Pace Gate asks a checkpoint question; correct unlocks, wrong closes the gate.
4. Open squad → see who's doing the work → claim a bounty.
5. Write code → run visible tests → submit → hidden tests + AI hint → verified, points land on the transcript.
6. Share the transcript link with an employer.

Lecturer: dashboard → spot coasting members and rush-heavy modules → approve artifacts → form next semester's squads from verified competence.

_Screenshots: run the app and capture home, Pace Gate, Bounty Board, referee result, transcript, dashboard (desktop + mobile)._

## 6. Feasibility & Impact
- **Sustainability:** Runs on a single small container + managed PostgreSQL; the AI coach is optional (rule-based fallback), so running costs stay near zero for institutions.
- **Scalability:** Stateless API scales horizontally; grading moves to a queue of isolated workers; per-course caching.
- **Measurable outcomes to track in a pilot:**
  - % of sections unlocked by genuine reading vs checkpoint (engagement)
  - first-try checkpoint accuracy per module (comprehension; tells lecturers which content to fix)
  - Gini coefficient of contribution within squads (fairness of group work)
  - share of graduates with ≥ N verified bounties (employability evidence)

---

## 3-minute demo script

| Time | Screen | Say |
|---|---|---|
| 0:00 | Login | "Students click through slides without reading, and one person carries the group project. Tempa makes both impossible." |
| 0:15 | Daniel → module → click continue immediately | "The server releases one section at a time. Daniel rushed, and the server clock knows it, so the Pace Gate asks him to prove it." |
| 0:40 | Answer wrong, then right | "A wrong answer closes the gate. Right answer: unlocked, points on the ledger." |
| 1:00 | Ravi → Squad Alpha board | "Group work is a bounty board. Everyone sees Amir carrying and Ravi coasting, in real time, not at the end of semester." |
| 1:20 | Ravi claims the keyword counter, submits a buggy solution | "Code is graded in a sandbox against hidden tests. It failed, and the AI coach gives a hint in Bahasa Melayu without giving away the answer." |
| 1:50 | Submit the fix → verified | "Verified. Points go to Ravi, and only Ravi." |
| 2:05 | Transcript + public link; toggle BM | "Points never reset. This public link is HMAC-chained, so editing one row in the database breaks it." |
| 2:25 | Lecturer dashboard | "Lecturers see coasting flags, which modules students rush, a review queue, and can form next semester's squads from verified competence." |
| 2:50 | Close | "Tempa: forge skills, not slides." |

Fixed solution for the demo:

```python
def word_count(text):
    c = {}
    for w in text.lower().split():
        w = w.strip('.,!?')
        if w:
            c[w] = c.get(w, 0) + 1
    return c
```
