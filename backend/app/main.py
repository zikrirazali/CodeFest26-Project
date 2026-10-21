"""Tempa API: the Backend-for-Frontend that serves the PWA and gatekeeps content."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import config
from .db import Base, SessionLocal, engine
from .routers import auth, bounties, courses, learn, transcript

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    if config.SEED_DEMO:
        from .seed import seed
        with SessionLocal() as db:
            seed(db)
    yield


app = FastAPI(
    title="Tempa API",
    version="0.1.0",
    description="Gamified accountability & active-learning platform · UTP CodeFest'26 Track 2 (Education). "
                "Interactive Swagger docs for every endpoint are below; authenticate with a JWT from /api/auth/login.",
    lifespan=lifespan,
)

for r in (auth.router, courses.router, learn.router, bounties.router, transcript.router):
    app.include_router(r)


@app.get("/api/health", tags=["meta"])
def health():
    return {"ok": True, "ai_coach": config.AI_COACH_ENABLED, "model": config.ANTHROPIC_MODEL}


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
