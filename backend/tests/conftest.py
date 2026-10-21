import os
import sys
from pathlib import Path

import pytest

os.environ["DATABASE_URL"] = "sqlite:///./_test.db"
os.environ["SEED_DEMO"] = "true"
os.environ.pop("ANTHROPIC_API_KEY", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)


def login(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": "demo1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture()
def lecturer(client):
    return login(client, "lecturer@tempa.my")


@pytest.fixture()
def ravi(client):
    return login(client, "ravi@student.tempa.my")


@pytest.fixture()
def daniel(client):
    return login(client, "daniel@student.tempa.my")
