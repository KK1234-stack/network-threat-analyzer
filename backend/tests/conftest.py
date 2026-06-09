import os

# Must be set before any app imports so Settings() picks them up
os.environ["DATABASE_URL"]         = "sqlite:///:memory:"
os.environ["SECRET_KEY"]           = "test-secret-key-for-pytest"
os.environ["ALGORITHM"]            = "HS256"
os.environ["ADMIN_EMAIL"]          = "admin@test.com"
os.environ["MLFLOW_TRACKING_URI"]  = "/tmp/mlruns-test"

import io
import pytest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.core.database as _db_module
from app.core.database import Base, get_db

# Patch the module-level engine with an in-memory SQLite before app.main is imported
_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
_db_module.engine = _test_engine
_db_module.SessionLocal = _TestSession

from app.main import app  # import after patching

Base.metadata.create_all(bind=_test_engine)


def override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


# --- Fixtures ---

@pytest.fixture(autouse=True)
def reset_db():
    """Wipe and recreate all tables before every test for full isolation."""
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def valid_csv_bytes():
    """Minimal valid CSV with all 65 FEATURE_COLUMNS."""
    from app.ml.preprocess import FEATURE_COLUMNS
    df = pd.DataFrame(
        np.random.rand(5, len(FEATURE_COLUMNS)) * 100,
        columns=FEATURE_COLUMNS,
    )
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode()


@pytest.fixture
def registered_user(client):
    client.post("/auth/register", json={"email": "user@test.com", "password": "password123"})
    return {"email": "user@test.com", "password": "password123"}


@pytest.fixture
def auth_token(client, registered_user):
    resp = client.post(
        "/auth/login",
        data={"username": registered_user["email"], "password": registered_user["password"]},
    )
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def admin_token(client):
    client.post("/auth/register", json={"email": "admin@test.com", "password": "adminpass"})
    resp = client.post("/auth/login", data={"username": "admin@test.com", "password": "adminpass"})
    return resp.json()["access_token"]


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
