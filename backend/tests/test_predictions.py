import io
import pandas as pd
import numpy as np


def test_upload_valid_csv(client, auth_headers, valid_csv_bytes):
    resp = client.post(
        "/predictions/upload",
        headers=auth_headers,
        files={"file": ("flows.csv", valid_csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_flows"] == 5
    assert data["threat_count"] + data["benign_count"] == 5
    assert "label_distribution" in data
    assert "model_version" in data
    assert "inference_time_ms" in data
    assert len(data["per_row"]) == 5
    assert "label" in data["per_row"][0]
    assert "confidence" in data["per_row"][0]


def test_upload_saves_to_history(client, auth_headers, valid_csv_bytes):
    client.post(
        "/predictions/upload",
        headers=auth_headers,
        files={"file": ("flows.csv", valid_csv_bytes, "text/csv")},
    )
    resp = client.get("/predictions/history", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["filename"] == "flows.csv"


def test_upload_non_csv(client, auth_headers):
    resp = client.post(
        "/predictions/upload",
        headers=auth_headers,
        files={"file": ("data.txt", b"not a csv", "text/plain")},
    )
    assert resp.status_code == 400
    assert "CSV" in resp.json()["detail"]


def test_upload_empty_csv(client, auth_headers):
    from app.ml.preprocess import FEATURE_COLUMNS
    empty = pd.DataFrame(columns=FEATURE_COLUMNS).to_csv(index=False).encode()
    resp = client.post(
        "/predictions/upload",
        headers=auth_headers,
        files={"file": ("empty.csv", empty, "text/csv")},
    )
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


def test_upload_wrong_columns(client, auth_headers):
    bad_csv = b"col1,col2,col3\n1,2,3\n4,5,6\n"
    resp = client.post(
        "/predictions/upload",
        headers=auth_headers,
        files={"file": ("bad.csv", bad_csv, "text/csv")},
    )
    assert resp.status_code == 400
    assert "missing" in resp.json()["detail"].lower()
    assert "CICFlowMeter" in resp.json()["detail"]


def test_upload_requires_auth(client, valid_csv_bytes):
    resp = client.post(
        "/predictions/upload",
        files={"file": ("flows.csv", valid_csv_bytes, "text/csv")},
    )
    assert resp.status_code == 401


def test_history_empty(client, auth_headers):
    resp = client.get("/predictions/history", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_history_requires_auth(client):
    resp = client.get("/predictions/history")
    assert resp.status_code == 401


def test_history_isolated_per_user(client, valid_csv_bytes):
    # User A uploads a file
    client.post("/auth/register", json={"email": "a@test.com", "password": "pass"})
    token_a = client.post("/auth/login", data={"username": "a@test.com", "password": "pass"}).json()["access_token"]
    client.post(
        "/predictions/upload",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"file": ("flows.csv", valid_csv_bytes, "text/csv")},
    )

    # User B should see empty history
    client.post("/auth/register", json={"email": "b@test.com", "password": "pass"})
    token_b = client.post("/auth/login", data={"username": "b@test.com", "password": "pass"}).json()["access_token"]
    resp = client.get("/predictions/history", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.json() == []
