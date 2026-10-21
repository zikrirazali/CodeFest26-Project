"""Runtime configuration, read from environment variables (see .env.example)."""
import os

from dotenv import load_dotenv

load_dotenv()

# PostgreSQL in production, e.g. postgresql+psycopg://tempa:tempa@localhost:5432/tempa
# Falls back to a local SQLite file so the prototype runs with zero setup.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tempa.db")

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me-please-32-bytes!")
JWT_TTL_MINUTES = int(os.getenv("JWT_TTL_MINUTES", "720"))

# Signs every merit-ledger entry so edits made directly in the database are detectable.
LEDGER_SECRET = os.getenv("LEDGER_SECRET", "dev-ledger-secret-change-me")

SEED_DEMO = os.getenv("SEED_DEMO", "true").lower() == "true"

# Pace Gate
READING_WPM = int(os.getenv("READING_WPM", "230"))
MIN_DWELL_SECONDS = float(os.getenv("MIN_DWELL_SECONDS", "6"))

# Bounty Board
CLAIM_TTL_HOURS = int(os.getenv("CLAIM_TTL_HOURS", "72"))
MAX_ACTIVE_CLAIMS = int(os.getenv("MAX_ACTIVE_CLAIMS", "2"))

# AI Referee
SANDBOX_TIMEOUT_SECONDS = float(os.getenv("SANDBOX_TIMEOUT_SECONDS", "4"))
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5")
AI_COACH_ENABLED = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))
